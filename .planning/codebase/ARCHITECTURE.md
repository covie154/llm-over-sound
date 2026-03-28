# Architecture

**Analysis Date:** 2026-03-28

## Pattern Overview

**Overall:** Bidirectional audio-pipe IPC with layered message transport and optional LLM pipeline

**Key Characteristics:**
- **Distributed**: Frontend (Windows AHK) and backend (Raspberry Pi/Linux Python) communicate exclusively via ggwave audio signals over a USB cable
- **Message-based**: All communication uses JSON-encoded dictionary messages with unique IDs, routing through a chunking/reassembly layer
- **Bandwidth-constrained**: ~140 bytes per ggwave transmission; messages exceeding this are compressed (LZNT1) and split across chunks
- **Pluggable pipeline**: Backend uses abstract ReportPipeline base class allowing swappable implementations (TestPipeline echo mode, LLMPipeline with 5 stages)
- **Medico-legal logging**: All processing is logged to file for audit trail and traceability

## Layers

**Audio Transport Layer:**
- Purpose: Send/receive data-over-sound via ggwave
- Location: `AHK/include/dll_manager.ahk` (AHK side), `python-backend/lib/audio.py` (Python side)
- Contains: DLL loading, device enumeration, audio stream management, protocol selection
- Depends on: ggwave library, PyAudio (Python), Windows DLLs (AHK)
- Used by: Message transport layer for byte-level transmission

**Message Transport Layer:**
- Purpose: Chunk large messages into ≤140 byte frames, reassemble received chunks, handle retransmission
- Location: `AHK/include/chunking.ahk`, `python-backend/lib/chunking.py`
- Contains: Message framing (ci/cc headers), chunk buffering by message ID, timeout detection, retransmission requests
- Depends on: Compression layer, DLL/audio layer
- Used by: Encoding layer and application logic

**Encoding Layer:**
- Purpose: Compress and encode message content to fit payload constraints
- Location: `AHK/include/compression.ahk` (Windows NTDLL LZNT1), `python-backend/lib/compression.py` (pure Python LZNT1)
- Contains: LZNT1 compression/decompression, Base64 encoding/decoding, compression threshold logic
- Depends on: None (compression is self-contained)
- Used by: Message transport layer

**Message/Protocol Layer:**
- Purpose: Structure JSON messages with metadata (id, fn, ct, st, ci, cc, z flags)
- Location: Implicit across chunking layers
- Contains: Message ID generation, JSON serialization, field routing
- Depends on: Encoding layer
- Used by: Application layer

**Application Layer (Frontend):**
- Purpose: GUI for radiologist draft input, receives and displays formatted reports
- Location: `AHK/main_dll.ahk`, `AHK/include/gui.ahk`
- Contains: Audio device selection GUI, multiline input dialog, report review interface
- Depends on: Message transport, encoding, DLL manager
- Used by: User interaction

**Application Layer (Backend):**
- Purpose: Process messages through radiology report pipeline, return formatted reports
- Location: `python-backend/backend.py`, `python-backend/lib/pipeline.py`
- Contains: Main event loop, message dispatching, pipeline invocation
- Depends on: Message transport, pipeline implementations
- Used by: Network (via Python client talking to LLM)

## Data Flow

**Frontend → Backend (User Input):**

1. User enters draft radiologist notes in AHK multiline input dialog
2. `GenerateMessageID()` creates unique 7-char Base62 ID (40-bit: 24-bit timestamp + 8-bit counter + 8-bit random)
3. Message dict built: `{"id": "abc1234", "fn": "test", "ct": "draft text"}`
4. `ChunkMessage()` evaluates:
   - If content < 100 chars AND JSON fits in 140 bytes → send as single frame (ci=0, cc=0)
   - Else: compress content with LZNT1, Base64-encode, split into 70-char chunks, add header (id/ci/cc/fn/st)
5. Each chunk JSON serialized and sent via `ggwave_simple_send()` over audio
6. Chunks transmitted with `INTER_CHUNK_DELAY` (200ms) between them
7. AHK caches chunk JSON in `lastSentChunks[msgID]` for retransmission on demand

**Backend ← Frontend (Receiving):**

1. Backend's input stream fed to ggwave decoder in 10ms loop
2. When message received: Base64-decoded and LZNT1-decompressed (if chunked)
3. `handle_received_chunk()` buffers by message ID; awaits all chunks (ci == 0 to cc-1)
4. When all chunks arrive: reassembled, decompressed, JSON-parsed
5. Complete message dict passed to pipeline

**Backend Processing:**

1. `pipeline.process(msg_dict)` invoked with complete message
2. TestPipeline: returns echo response immediately
3. LLMPipeline (when implemented):
   - Stage 1: Classify study type against closed set from templates
   - Stage 2: Load template markdown by study type
   - Stage 3: Extract findings using LLM, map to anatomical fields
   - Stage 4: Render template with findings JSON
   - Stage 5: Generate impression
4. Response dict: `{"id": "abc1234", "st": "S", "ct": "formatted report text"}`

**Backend → Frontend (Response):**

1. Response dict passed to `chunk_message()` using same chunking logic
2. Full report compressed as single block before chunking for optimal ratio
3. Chunks sent sequentially via audio with 0.5s inter-chunk delay
4. Cached in `last_sent_chunks[msgID]` for retransmission

**Frontend ← Backend (Receiving Response):**

1. AHK receive loop calls `ProcessAudio()` every 10ms
2. Chunks buffered by message ID in `chunkReceiveBuffer[msgID]`
3. When cc chunks received for message ID: reassembled and decompressed
4. Report displayed in edit control for radiologist review
5. `__NOT_DOCUMENTED__` sentinels replaced with `[*** NOT DOCUMENTED — please complete ***]`

**Retransmission:**

1. Either side: if chunk missing after 30s → send retransmission request
2. Request dict: `{"id": "abc1234", "fn": "retx", "ci": N}` (missing chunk index)
3. Receiver responds by resending chunk from cache
4. Maximum retry window prevents infinite loops

## State Management

**Frontend State:**
- `selectedSpeakerIndex`, `selectedMicrophoneIndex`: Audio device indices (set once during init)
- `messageCounter`: 8-bit counter for message ID uniqueness
- `chunkReceiveBuffer[msgID]`: Incoming chunk reassembly buffer keyed by message ID
- `lastSentChunks[msgID]`: Outbound chunk JSON array for retransmission

**Backend State:**
- `chunk_receive_buffer`: Incoming chunks keyed by message ID with ci→ct mapping, cc count, timestamp
- `last_sent_chunks`: Outbound chunk JSON strings cached by message ID
- `pipeline`: Active ReportPipeline instance (TestPipeline or LLMPipeline)

All state is in-memory (no persistent storage). Chunks expire if not reassembled within timeout.

## Key Abstractions

**Message:**
- Purpose: JSON-encoded dict representing request, response, or chunk
- Structure: Mandatory fields (id, ct/ci/cc), optional fields (fn, st, z)
- Pattern: Dict → JSON encode/decode at transmission boundaries

**Chunk:**
- Purpose: Single audio transmission unit (≤140 bytes)
- Structure: `{id, ci, cc, ct, ...metadata}` where ct is base64-encoded compressed content
- Pattern: Content chunked outbound, reassembled inbound

**Pipeline (ReportPipeline):**
- Purpose: Abstract interface for message processing
- Implementations:
  - `TestPipeline`: Echo responder for development
  - `LLMPipeline`: 5-stage radiology report formatter (stub)
- Pattern: `process(msg_dict) → response_dict`

**Template:**
- Purpose: Markdown file defining study type, anatomical fields, and report skeleton
- Structure: Frontmatter (study name/aliases, field list) + body (template with `{token}` placeholders)
- Pattern: Loaded by study type string, indexed by alias at startup (planned)

**Report:**
- Purpose: Formatted radiology report text ready for radiologist review
- Structure: Sections (Clinical history, Technique, Comparison, Findings, Impression)
- Pattern: Template body with field tokens replaced by extracted findings JSON

## Entry Points

**AHK Frontend:**
- Location: `AHK/main_dll.ahk`
- Triggers: User runs script via AutoHotkey v2 interpreter
- Responsibilities:
  1. Load ggwave_simple.dll from script directory
  2. Show audio device selection GUI (calls ggwave API to enumerate devices)
  3. Initialize ggwave with selected devices and AUDIBLE_FAST protocol
  4. Start 10ms receive processing timer
  5. Enter main loop: prompt user for draft input → chunk → send → wait for response
  6. Display received report with incomplete field markers
  7. Cleanup on Escape key or app exit

**Python Backend:**
- Location: `python-backend/backend.py`
- Triggers: `python backend.py [options]` invoked on Raspberry Pi
- Responsibilities:
  1. Parse CLI args (device indices, volume, protocol ID, --list)
  2. Initialize PyAudio streams (input/output) on specified or default devices
  3. Initialize ggwave decoder
  4. Enter main loop:
     - Read audio frames → ggwave decode
     - On message: reassemble chunks → invoke pipeline
     - On response: chunk → send via audio
     - Check retransmission timeouts periodically
  5. Log all activity to backend_log.txt
  6. Handle KeyboardInterrupt and unexpected errors gracefully

## Error Handling

**Strategy:** Logging + graceful degradation. Errors are logged and returned as response dicts with st="E".

**Patterns:**

- **Audio Device Errors** (AHK):
  - If DLL not found: show MsgBox and ExitApp
  - If no playback/capture devices: show MsgBox and return false to exit
  - If initialization fails: log error, show MsgBox, cleanup and exit

- **Message Encoding/Decoding** (both sides):
  - If compression fails: log warning, fall back to uncompressed
  - If JSON parse fails: log error and skip message
  - If Base64 decode fails: log and request retransmission

- **Chunk Reassembly** (both sides):
  - If chunk arrives out of order: buffer and wait
  - If timeout expires: log warning, send retransmission request
  - If retransmission fails: log error (silent, do not retry forever)

- **Pipeline Execution** (backend):
  - If LLM call fails: return error response dict
  - If template not found: return error response dict
  - If rendering fails: return error response dict

## Cross-Cutting Concerns

**Logging:**
- AHK: File-based, manual FileAppend to `ggwave_log.txt`, timestamps with millisecond precision
- Python: logging module, both file and console, to `backend_log.txt`
- Pattern: Entries tagged by type (SESSION, CHUNK, RECV_RAW, PROCESS_OK, etc.)
- Long messages truncated in log to 500 chars to keep logs readable

**Validation:**
- Message IDs: 7-char Base62, generated via 40-bit combination
- Chunk indices: 0 ≤ ci < cc, validated during reassembly
- Compression flag: z=1 indicates content was compressed; z=0 or absent means plain
- JSON structure: Required keys (id, ct or ci/cc) checked before processing

**Audio Constraints:**
- Protocol: AUDIBLE_FAST (ID 1) default, negotiated during init; supports alternatives
- Bandwidth: 140-byte maximum per transmission (ggwave limit for Audible Fast)
- Latency: Inter-chunk delay 200ms (AHK) to 500ms (Python) to allow receiver buffer fill

**Synchronization:**
- Half-duplex: Only one side transmits at a time; receiver processes while sender waits
- Message ID uniqueness: Frontend generates unique IDs; backend echoes them in responses
- Request/response pairing: Frontend waits for response from backend; backend processes in order

---

*Architecture analysis: 2026-03-28*
