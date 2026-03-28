# Project: LLM Over Sound — Radiology Report Formatting System

## Overview
This system uses ggwave (data-over-sound) to pipe messages between an AutoHotkey v2
frontend (Windows GUI) and a Python backend running on a Raspberry Pi or equivalent SBC (Assume it's running linux).
The backend connects to an LLM over the network. The audio channel is the sole IPC
mechanism — messages are transmitted as sound over a direct USB audio interface cable
connection between the two machines [1]. No shared filesystem or network link exists
between the frontend and backend other than the audio pipe.

The primary use case is AI-powered radiology report formatting. A radiologist writes
draft findings (structured point form, brief notes, or incomplete drafts) on the AHK
frontend. The draft is transmitted over ggwave to the Python backend, which classifies
the study type, selects the appropriate report template, extracts and maps findings to
anatomical fields using the LLM, and transmits the formatted report back over ggwave
for review and completion.

## Architecture
- **AHK Frontend** (`AHK/main_dll.ahk`): Windows GUI that captures the radiologist's
  draft input via a multiline Edit control [2], encodes it, and transmits via the
  ggwave_simple DLL. Receives the formatted report back, presents __NOT_DOCUMENTED__
  fields for review, and handles final report approval. Uses LZNT1/XPRESS compression
  (via ntdll) and Base62 encoding for payload efficiency [2].
- **Python Backend** (`python-backend/backend.py`): Runs on a Raspberry Pi connected to
  the user's PC. It has not yet been determined if the connection is a speaker-microphone or wired audio connection. Listens for ggwave signals,
  decodes messages, orchestrates the LLM-powered report formatting pipeline, and
  transmits results back over ggwave [3]. Connects to the LLM over the network.
- **ggwave Wrapper** (`ggwave-wrapper/`): C/C++ DLL wrapper around the ggwave library,
  built with CMake. Provides a simplified interface for the AHK frontend. Completed as of Feb 2026.
- **ggwave** (`ggwave/`): The upstream ggwave library (data-over-sound).
- **Templates** (markdown files): Each template file contains a study name with aliases
  for matching, a list of expected anatomical fields, and the report template skeleton
  with placeholder tokens.

## Structure of a Radiology Report
- A radiology report generally consists of give main sections.
  1. Clinical history: This is the reason for ordering the scan. Ideally, this should include what the referring clinician is looking for on the scan
    including their differentials
  2. Technique: A technical section detailing how the study was performed. Usually, the imaging modality is indicated here, along with other factors like 
    phase of the study and whether contrast was administered.
  3. Comparison: The presence/absence of prior comparison study/studies, if available.
  4. Findings: This section details radiological observations (e.g. a rim-enhancing collection around the appendix). It should not include recommendations, which
    should go to the conclusion. Some reports organise the findings by body system, while others organise the findings by abnormal-first (with normal findings summed up below).
  5. Conclusion/Impression/Comment: This section provides a very brief summary of the report. It should answer the clinical question. The next points can detail important
    incidental findings (e.g. incidental cancers). Recommendations will go here (e.g. histological correlation is suggested).

## Report Formatting Pipeline
The backend runs a five-stage pipeline. Only stages 1, 3, 4 and 5 involve the LLM.

1. **Study type classification** (LLM): Identify imaging modality and body region from
   the draft. Output is constrained to the closed set of known study types extracted
   from template file metadata. 
   TODO: If ambiguous, return a clarification request rather than guessing.
2. **Template retrieval** (deterministic): Load and parse the matching markdown template
   file by study type. Not an LLM call. An index of study aliases to template file
   paths is built at startup for fast lookup.
3. **Findings extraction and mapping** (LLM): Extract findings from the draft and assign
   to anatomical fields defined in the template. Output is structured JSON keyed by
   field name. Fields not mentioned in the draft are marked __NOT_DOCUMENTED__ — the
   LLM must NOT fabricate findings. The model must
   preserve the radiologist's clinical language and intent. In other words, if a full sentence is provided in a finding, preserve it and do not alter it in any way.
   Log every input-output pair for audit trail and medico-legal traceability.
4. **Report rendering** (LLM): Populate the template skeleton with extracted
   findings. You may only add normal findings if assume_normal is set to True.
5. **Impression generation** (LLM): Generate the impression/conclusion of the report. 

## Audio Channel Constraints
- The ggwave audio pipe is bandwidth-limited. The default protocol is Audible Fast
  (protocol ID 1). Payload ceiling is approximately 140 bytes per transmission.
- Messages are compressed above COMPRESSION_THRESHOLD (100 chars) using LZNT1 [2].
- For payloads exceeding the per-transmission limit (especially formatted reports
  returning to the frontend), chunking is required. Compress the entire report first
  as a single block for best compression ratio, then chunk the compressed output.
  Each chunk includes a sequencing header (message ID, chunk index "ci", chunk
  count "cc"). Target pre-compression chunk input of ~200 characters as a safe
  starting point.
- The AHK frontend must buffer incoming chunks by message ID and reassemble only when
  all chunks for a given ID have arrived. Implement a timeout for missing chunks and
  request retransmission rather than silently producing an incomplete report.
- All data must travel over ggwave. No shared filesystem or secondary network channel
  between frontend and backend.

## Hardware Setup
- Testing currently is with a USB speaker/microphone. 
- Eventually, the plan is to use a class-compliant USB audio interface for both input and output. Do not use the Pi's onboard 3.5mm jack.
- The PC uses a second USB audio interface or built-in line-in/line-out if available. If audio cables are used, two 1/4" TRS cables connect the devices: Pi line-out to PC line-in, PC line-out to
  Pi line-in. This provides a full-duplex dedicated audio path.
- Volume calibration is critical. Use --volume on the backend and Windows audio settings
  on the PC side. Test each direction independently before running ggwave.

## Key Constraints
- AHK scripts require AutoHotkey v2.0. Do not use v1 syntax [2].
- If you modify message encoding, compression, framing, or chunking on one side, the
  other side MUST be updated to match or the pipe will break.
- The LLM must never fabricate radiology findings. The extraction prompt must constrain
  the model to only surface information present in the draft input.
- All logging is file-based: `ggwave_log.txt` for AHK [2], `backend_log.txt` for
  Python [3].

## Build
- The C++ wrapper is built via CMake from `ggwave-wrapper/`. Output goes to `build/`.
- The Python backend has its own dependencies (see `python-backend/`).

## Conventions
- AHK global config variables are ALL_CAPS_SNAKE_CASE [2].

<!-- GSD:project-start source:PROJECT.md -->
## Project

**LLM Report Templates — Radiology Report Formatting System**

A template-driven radiology report formatting system. Markdown templates with YAML frontmatter define the structure, fields, and normal-text defaults for each imaging study type. The LLM extracts findings from a radiologist's draft input, maps them to template fields, and renders a formatted freetext report. Templates are composable — combined studies (e.g. CT TAP) concatenate sections from constituent templates.

**Core Value:** The LLM must never fabricate findings. Every extracted finding must trace to the radiologist's draft input, and fields not mentioned must be marked `__NOT_DOCUMENTED__` or filled with the template's default normal text only when explicitly permitted.

### Constraints

- **Template format**: Markdown with YAML frontmatter — must be human-readable and editable by radiologists
- **Field granularity**: Organ-level groupings that match natural reporting patterns (e.g. "spleen, adrenals and pancreas" grouped together when all normal)
- **Composability**: Combined templates must concatenate sections, not interleave — thorax findings block followed by abdomen/pelvis findings block
- **Audio bandwidth**: Templates themselves are not transmitted over ggwave, but the rendered reports are — keep report output concise
- **No fabrication**: Fields without input findings must use `__NOT_DOCUMENTED__` or the template's stored normal text (only when interpolate_normal is enabled)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- **Python 3** - Backend server on Raspberry Pi/Linux SBC (`python-backend/backend.py`)
- **AutoHotkey v2.0** - Windows GUI frontend (`AHK/main_dll.ahk`, strict v2 syntax required)
- **C++17** - ggwave wrapper DLL for audio I/O (`ggwave-wrapper/ggwave_simple.cpp`)
- **C** - ggwave core library (upstream dependency, `ggwave/src/ggwave.cpp`)
## Runtime
- **Python 3.x** - Runs on Raspberry Pi or equivalent SBC (Linux)
- **AutoHotkey v2.0** - Runs on Windows (tested on Windows 11 Pro)
- **Windows NTDLL APIs** - Required on frontend for compression (RtlCompressBuffer, RtlDecompressBuffer)
- **pip** - Python package management
- **CMake 3.10+** - C++ build system for wrapper and ggwave
## Frameworks
- **ggwave** - Data-over-sound library for audio-based IPC. Uses protocol ID 1 (Audible Fast, ~140 bytes/transmission limit)
- **PyAudio** - Python bindings for audio device I/O and stream management (both input and output at 48kHz mono)
- **SDL2** - Audio backend for ggwave (vendor copy at `ggwave/SDL2/`)
- Manual testing (no automated harness) - Integration tests via round-trip message integrity with USB audio cable between Windows PC and Pi
- **CMake** - Cross-platform build for C++ wrapper
- **C++17 Standard** - Compilation target for wrapper DLL
## Key Dependencies
- **ggwave** (`ggwave/`) - Upstream library providing data-over-sound encoding/decoding. Protocol ID 1 is default (Audible Fast).
- **PyAudio** - Python bindings for cross-platform audio I/O
- **SDL2** - Underlying audio implementation for ggwave
- **ntdll.dll** (Windows system) - LZNT1 compression/decompression via RtlCompressBuffer/RtlDecompressBuffer
- **Crypt32.dll** (Windows system) - Base64 encoding via CryptBinaryToStringW (used for payload encoding in frontend)
## Configuration
- No environment file (`.env`) currently required
- LLM integration TBD - pipeline stages 1, 3, 4, 5 have stub implementations (NotImplementedError)
- Configuration is hardcoded in:
- **CMakeLists.txt** in `ggwave-wrapper/` - Configures C++ compilation, finds SDL2, links against ggwave source
- SDL2_DIR configured to `ggwave/SDL2/cmake` for CMake discovery
- Output directory: `build/` (created by CMake)
## Platform Requirements
- **Windows 11 Pro** (tested; Windows 10+ expected to work)
- **Linux (Raspberry Pi or SBC)**
- **Deployment target:** Raspberry Pi 4B or equivalent SBC running Linux (full duplex USB audio interface)
- **Windows PC:** Audio interface with line-out to Pi line-in; USB audio input for receiving from Pi
- **Audio specs:**
## Audio Channel Specifications
- ggwave Audible Fast (protocol ID 1)
- Payload ceiling: ~140 bytes per transmission
- Compression threshold: Messages >100 characters are compressed using LZNT1
- Chunking: Messages exceeding per-transmission limit are split with sequencing headers (message ID, chunk index "ci", chunk count "cc")
- Chunk reassembly timeout: 30 seconds before requesting retransmission
- Target: Class-compliant USB audio interface on both sides
- Current testing: USB speaker/microphone
- Future: Dedicated USB audio interface with separate line-out to Pi line-in and line-in from Pi line-out (full duplex)
- Volume calibration: Configurable via `--volume` flag on backend (default 50, range 1-100) and Windows audio settings
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Global variables: `ALL_CAPS_SNAKE_CASE` (e.g., `COMPRESSION_THRESHOLD`, `isInitialized`, `selectedSpeakerIndex`)
- Functions: `PascalCase` (e.g., `Main()`, `ProcessAudio()`, `ChunkMessage()`, `SendChunkedMessage()`)
- Local variables: `camelCase` (e.g., `result`, `errorMsg`, `msgID`, `editCtrl`, `speakerNames`)
- JSON key names in messages: lowercase with underscores (e.g., `"id"`, `"fn"`, `"ct"`, `"ci"`, `"cc"`, `"st"`, `"z"`)
- Functions and variables: `snake_case` (e.g., `lznt1_compress()`, `handle_received_chunk()`, `chunk_receive_buffer`)
- Classes: `PascalCase` (e.g., `ReportPipeline`, `TestPipeline`, `LLMPipeline`)
- Constants: `ALL_CAPS_SNAKE_CASE` (e.g., `COMPRESSION_THRESHOLD`, `LOG_MAX_CONTENT_LENGTH`, `INTER_CHUNK_DELAY`)
- Private functions (internal use): prefix with `_` (e.g., `_lznt1_compress_chunk()`)
- JSON key names: lowercase with underscores (e.g., `"id"`, `"fn"`, `"ct"`, `"ci"`, `"cc"`, `"st"`)
## File Organization
- Main entrypoint: `AHK/main_dll.ahk` — initializes, loads DLL, runs main loop
- Include files in `AHK/include/`:
- Main entrypoint: `python-backend/backend.py` — parse args, initialize ggwave, main loop
- Library modules in `python-backend/lib/`:
## Code Style
- AutoHotkey v2.0 strict syntax (NOT v1.1)
- Indentation: 4 spaces
- String concatenation: use `.` operator (e.g., `"Error: " . errorMsg`)
- Control flow: `if` with parentheses around conditions: `if (condition) { ... }`
- Loops: `Loop` for fixed iterations, `while` for conditions
- No implicit type conversions; explicit casts where needed
- Comments: `;` single-line comments, section headers with `; ==== ====`
- Functions: declared with `FunctionName() { ... }` syntax, no return type annotation
- Maps/Arrays: use square bracket indexing `map[key]` or `.Get()`, `.Push()`, `.Delete()` methods
- Error handling: `try { ... } catch as e { ... }` for JSON parsing and decompression
- Python 3.9+
- Indentation: 4 spaces
- Type hints: used in function signatures (e.g., `def chunk_message(msg_dict: dict) -> list[str]:`)
- Docstrings: used for modules, classes, and public functions (description of purpose and return value)
- String formatting: f-strings preferred (e.g., `f"[CHUNK] ID: {msg_id} | ...`)
- Comments: `#` for explanatory comments; `# ===== =====` for section headers
- Error handling: `try/except` for fallible operations (compression, JSON parsing, I/O)
- Logging: use module-level `logger` from `lib.config` (not `print()`)
## Import Organization
- All includes at the top of the file after `#Requires AutoHotkey v2.0`
- Order: third-party/vendored first (`_JXON.ahk`), then project modules (alphabetical)
- Example from `main_dll.ahk`:
- Standard library imports first
- Third-party imports second (ggwave, pyaudio)
- Project imports last
- Example from `backend.py`:
## Message Protocol
- `id` (str, len 7): Unique message ID (Base62-encoded)
- `fn` (str): Function name or command (e.g., `"test"`, `"retx"` for retransmission)
- `ct` (str): Content (payload text, usually the actual data or response)
- `st` (str): Status code (e.g., `"S"` for success, `"E"` for error)
- `ci` (int): Chunk index (0-based), 0 if single frame
- `cc` (int): Total chunk count, 0 if single frame
- `z` (bool, optional): Legacy compression flag (removed before sending)
## Error Handling
- DLL errors: retrieve via `GetGGWaveError()` and display in `MsgBox()`
- JSON parsing errors: caught with `try { chunkDict := Jxon_Load(&message) } catch as e { LogMessage("RECV_FAIL", ...) }`
- Validation: check return values from DLL calls (e.g., `if (result < 0) { ... }`)
- Failures log with prefix `*_FAIL` (e.g., `"CHUNK_FAIL"`, `"SEND_FAIL"`, `"RETX_FAIL"`)
- User-facing errors: `MsgBox()` with appropriate icon flag
- Recovery: retry is not automatic; user must intervene or restart
- General exceptions: `try/except Exception as e` for broad catching, log with `logger.error()`
- Specific exceptions: catch specific types (e.g., `except IOError`, `except json.JSONDecodeError`)
- I/O errors on compression: return empty buffer or None on failure; log and continue
- Pipeline errors: return error response dict `{"id": msg_id, "st": "E", "ct": error_text}`
- Session errors: log to both file and console via `logger` instance from `lib.config`
- Missing data gracefully degraded: e.g., default device enumeration skips missing devices with `except Exception: pass`
## Logging
- Controlled by `LOG_ENABLED` and `LOG_FILE` globals (file path: `ggwave_log.txt`)
- `LogMessage(logType, content)` — logs timestamp, type tag, and message to file
- Timestamp format: `[YYYY-MM-DD HH:mm:ss.mmm] [logType] message`
- Log types: `SESSION`, `CHUNK`, `SEND`, `SEND_OK`, `SEND_FAIL`, `RECV_RAW`, `RECV_OK`, `RECV_FAIL`, `REASSEMBLE`, `RETX_SEND`, `RETX`, etc.
- Long messages truncated to `LOG_MAX_CONTENT_LENGTH` (500 chars) with indicator
- Content with newlines: escaped as `\n` in log output
- Module-level `logger` instance initialized with `setup_logging()`
- Both file output (`backend_log.txt`) and console output configured
- Timestamp format: `[YYYY-MM-DD HH:mm:ss.mmm] [LEVEL] message` (milliseconds added by formatter)
- Log levels: `DEBUG` (file only), `INFO` (file + console)
- Log types (prefixes): `[CHUNK]`, `[SEND]`, `[SEND_OK]`, `[RECV_RAW]`, `[RECV_FAIL]`, `[REASSEMBLE]`, `[TIMEOUT]`, `[RETX]`, etc.
- Content truncation: `truncate_for_log(text)` limits to `LOG_MAX_CONTENT_LENGTH` (500 chars)
- Session markers: `log_session_start()` and `log_session_end(reason)` wrap execution
## Comments and Documentation
- Inline comments explain WHY (e.g., `; Protocol 1 = AUDIBLE_FAST (good balance of speed and reliability)`)
- Section headers: `; ==================== Section Name ====================`
- Function comments: brief description above function before declaration
- Complex logic: comment block above code explaining approach
- JSON key comments: inline dict initialization (e.g., `"id", msgID, "fn", "test", "ct", result.text`)
- Module docstring: brief description of module purpose
- Function docstrings: description + Args + Returns (e.g., in `chunking.py`)
- Inline comments: explain non-obvious logic or implementation details
- Section headers: `# ===== Section Name =====` in module
- Logging statements: act as audit trail; prefer over comments for state tracking
## Function Design
- Size: typically 20-100 lines; chunking.ahk functions are longer (30-100 lines) due to complex protocol logic
- Parameters: passed as individual arguments or via Map when complex
- Return values: explicit `return` statements with data (strings, dicts, booleans, integers)
- Side effects: global state modifications documented in header comments
- Cleanup: resource cleanup (DLL unload, stream close) handled in dedicated cleanup functions
- Size: typically 10-50 lines; chunking and compression functions 30-60 lines
- Parameters: named parameters with type hints; use dict or dataclass for complex args
- Return values: dict, list, or None; type hints indicate possible None (e.g., `dict | None`)
- Side effects: global module state (buffers, logger) modified explicitly; documented in docstring
- Context managers: PyAudio streams use context managers or explicit close calls
## Module Exports
- No explicit export mechanism; included files contribute to global namespace
- Configuration globals and functions intended for use by main script
- `lib/__init__.py`: explicitly exports public API (config, compression, chunking, audio, pipeline)
- Private modules/functions: not exported (e.g., `_lznt1_compress_chunk()`)
- Import style: `from lib import function_name` or `from lib.module import function_name`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Distributed**: Frontend (Windows AHK) and backend (Raspberry Pi/Linux Python) communicate exclusively via ggwave audio signals over a USB cable
- **Message-based**: All communication uses JSON-encoded dictionary messages with unique IDs, routing through a chunking/reassembly layer
- **Bandwidth-constrained**: ~140 bytes per ggwave transmission; messages exceeding this are compressed (LZNT1) and split across chunks
- **Pluggable pipeline**: Backend uses abstract ReportPipeline base class allowing swappable implementations (TestPipeline echo mode, LLMPipeline with 5 stages)
- **Medico-legal logging**: All processing is logged to file for audit trail and traceability
## Layers
- Purpose: Send/receive data-over-sound via ggwave
- Location: `AHK/include/dll_manager.ahk` (AHK side), `python-backend/lib/audio.py` (Python side)
- Contains: DLL loading, device enumeration, audio stream management, protocol selection
- Depends on: ggwave library, PyAudio (Python), Windows DLLs (AHK)
- Used by: Message transport layer for byte-level transmission
- Purpose: Chunk large messages into ≤140 byte frames, reassemble received chunks, handle retransmission
- Location: `AHK/include/chunking.ahk`, `python-backend/lib/chunking.py`
- Contains: Message framing (ci/cc headers), chunk buffering by message ID, timeout detection, retransmission requests
- Depends on: Compression layer, DLL/audio layer
- Used by: Encoding layer and application logic
- Purpose: Compress and encode message content to fit payload constraints
- Location: `AHK/include/compression.ahk` (Windows NTDLL LZNT1), `python-backend/lib/compression.py` (pure Python LZNT1)
- Contains: LZNT1 compression/decompression, Base64 encoding/decoding, compression threshold logic
- Depends on: None (compression is self-contained)
- Used by: Message transport layer
- Purpose: Structure JSON messages with metadata (id, fn, ct, st, ci, cc, z flags)
- Location: Implicit across chunking layers
- Contains: Message ID generation, JSON serialization, field routing
- Depends on: Encoding layer
- Used by: Application layer
- Purpose: GUI for radiologist draft input, receives and displays formatted reports
- Location: `AHK/main_dll.ahk`, `AHK/include/gui.ahk`
- Contains: Audio device selection GUI, multiline input dialog, report review interface
- Depends on: Message transport, encoding, DLL manager
- Used by: User interaction
- Purpose: Process messages through radiology report pipeline, return formatted reports
- Location: `python-backend/backend.py`, `python-backend/lib/pipeline.py`
- Contains: Main event loop, message dispatching, pipeline invocation
- Depends on: Message transport, pipeline implementations
- Used by: Network (via Python client talking to LLM)
## Data Flow
## State Management
- `selectedSpeakerIndex`, `selectedMicrophoneIndex`: Audio device indices (set once during init)
- `messageCounter`: 8-bit counter for message ID uniqueness
- `chunkReceiveBuffer[msgID]`: Incoming chunk reassembly buffer keyed by message ID
- `lastSentChunks[msgID]`: Outbound chunk JSON array for retransmission
- `chunk_receive_buffer`: Incoming chunks keyed by message ID with ci→ct mapping, cc count, timestamp
- `last_sent_chunks`: Outbound chunk JSON strings cached by message ID
- `pipeline`: Active ReportPipeline instance (TestPipeline or LLMPipeline)
## Key Abstractions
- Purpose: JSON-encoded dict representing request, response, or chunk
- Structure: Mandatory fields (id, ct/ci/cc), optional fields (fn, st, z)
- Pattern: Dict → JSON encode/decode at transmission boundaries
- Purpose: Single audio transmission unit (≤140 bytes)
- Structure: `{id, ci, cc, ct, ...metadata}` where ct is base64-encoded compressed content
- Pattern: Content chunked outbound, reassembled inbound
- Purpose: Abstract interface for message processing
- Implementations:
- Pattern: `process(msg_dict) → response_dict`
- Purpose: Markdown file defining study type, anatomical fields, and report skeleton
- Structure: Frontmatter (study name/aliases, field list) + body (template with `{token}` placeholders)
- Pattern: Loaded by study type string, indexed by alias at startup (planned)
- Purpose: Formatted radiology report text ready for radiologist review
- Structure: Sections (Clinical history, Technique, Comparison, Findings, Impression)
- Pattern: Template body with field tokens replaced by extracted findings JSON
## Entry Points
- Location: `AHK/main_dll.ahk`
- Triggers: User runs script via AutoHotkey v2 interpreter
- Responsibilities:
- Location: `python-backend/backend.py`
- Triggers: `python backend.py [options]` invoked on Raspberry Pi
- Responsibilities:
## Error Handling
- **Audio Device Errors** (AHK):
- **Message Encoding/Decoding** (both sides):
- **Chunk Reassembly** (both sides):
- **Pipeline Execution** (backend):
## Cross-Cutting Concerns
- AHK: File-based, manual FileAppend to `ggwave_log.txt`, timestamps with millisecond precision
- Python: logging module, both file and console, to `backend_log.txt`
- Pattern: Entries tagged by type (SESSION, CHUNK, RECV_RAW, PROCESS_OK, etc.)
- Long messages truncated in log to 500 chars to keep logs readable
- Message IDs: 7-char Base62, generated via 40-bit combination
- Chunk indices: 0 ≤ ci < cc, validated during reassembly
- Compression flag: z=1 indicates content was compressed; z=0 or absent means plain
- JSON structure: Required keys (id, ct or ci/cc) checked before processing
- Protocol: AUDIBLE_FAST (ID 1) default, negotiated during init; supports alternatives
- Bandwidth: 140-byte maximum per transmission (ggwave limit for Audible Fast)
- Latency: Inter-chunk delay 200ms (AHK) to 500ms (Python) to allow receiver buffer fill
- Half-duplex: Only one side transmits at a time; receiver processes while sender waits
- Message ID uniqueness: Frontend generates unique IDs; backend echoes them in responses
- Request/response pairing: Frontend waits for response from backend; backend processes in order
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
