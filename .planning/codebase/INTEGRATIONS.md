# External Integrations

**Analysis Date:** 2026-03-28

## APIs & External Services

**Large Language Model (LLM):**
- **Status:** Not yet integrated (stub implementation)
- **Architecture:** Backend connects to LLM over network (separate from audio pipe)
- **Pipeline stages requiring LLM:**
  - Stage 1: Study type classification - identify imaging modality from draft
  - Stage 3: Findings extraction and mapping - extract radiological findings, map to template fields
  - Stage 4: Report rendering - populate template skeleton with findings
  - Stage 5: Impression generation - generate clinical impression/conclusion
- **Implementation location:** `python-backend/lib/pipeline.py` - LLMPipeline class (all methods currently NotImplementedError)
- **SDK/Client:** Not yet determined (TBD - will depend on chosen LLM provider: OpenAI, Anthropic, local model, etc.)
- **Auth:** Environment variables TBD (API keys, tokens)

## Data Storage

**Databases:**
- **Not used** - No persistent database currently implemented
- Architecture is stateless: reports are processed immediately and returned; no data persists

**File Storage:**
- **Local filesystem only**
  - Templates: Markdown files containing study names, anatomical field definitions, and report skeletons
    - Location TBD (to be indexed at startup per `pipeline.py` comments)
  - Logs: `backend_log.txt` (Python backend), `ggwave_log.txt` (AHK frontend)

**Caching:**
- **Template alias index:** Built at LLMPipeline startup (in-memory lookup from study aliases to template file paths)
  - Status: Not yet implemented (TODO in `python-backend/lib/pipeline.py`)
- **No distributed caching** - Single process per deployment

## Authentication & Identity

**Auth Provider:**
- **None** - System operates in air-gapped mode (audio pipe only)
- No user login required
- No API authentication for LLM integration yet implemented
- Audio communication is unencrypted (design constraint: ggwave data-over-sound, audio cables only)

## Monitoring & Observability

**Error Tracking:**
- **None** - No external error tracking service
- Errors are logged locally only

**Logs:**
- **File-based logging (UTF-8)**
  - **Backend:** `python-backend/backend_log.txt`
    - Framework: Python logging module (`logging.Logger`)
    - Format: `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] message`
    - Handlers: File (DEBUG level) + console (INFO level)
    - Truncation: Messages >500 chars are truncated for logging (LOG_MAX_CONTENT_LENGTH)
    - Controlled by: LOG_ENABLED flag in `python-backend/lib/config.py`
  - **Frontend:** `AHK/ggwave_log.txt`
    - Entries include timestamps with millisecond precision
    - Controlled by: LOG_ENABLED global in `AHK/include/config.ahk`
    - Truncation: LOG_MAX_CONTENT_LENGTH=500 chars
- **Log points:**
  - Session start/end with separators
  - All received messages (raw bytes + decoded content)
  - Chunk reception and reassembly
  - Processing status (success/error)
  - Retransmission requests
  - Device enumeration and initialization

## CI/CD & Deployment

**Hosting:**
- **Raspberry Pi (or equivalent Linux SBC)** - Backend runs continuously, listening for audio
- **Windows PC** - Frontend runs as GUI application
- **No cloud deployment** - Air-gapped system with audio pipe only

**CI Pipeline:**
- **None** - Manual build and deployment
- CMake required for building `ggwave-wrapper/ggwave_simple.dll`

## Environment Configuration

**Required env vars:**
- **Currently:** None required (hardcoded configuration)
- **Future (when LLM integrated):** Will require LLM API credentials (API_KEY, API_URL, MODEL_NAME, etc. - TBD)

**Secrets location:**
- **None currently** - No secrets management system in place
- **Future:** When LLM is integrated, API credentials will need secure storage (environment variables or config file)

## Webhooks & Callbacks

**Incoming:**
- None - System is pull-based (frontend sends draft, backend processes, sends response)
- No webhook endpoints exposed

**Outgoing:**
- None - No outbound callbacks to external services
- LLM requests will be synchronous (backend calls LLM API directly during pipeline stages)

## Audio Hardware Integration

**Input/Output:**
- **USB Audio Interface (planned)** or USB speaker/microphone
- **Sample rate:** 48 kHz (mono, configurable in PyAudio kwargs at `python-backend/backend.py:102-104`)
- **Device enumeration:** PyAudio API
  - Backend lists devices via `python-backend/lib/audio.py:list_devices()`
  - Frontend enumerates via DLL calls to `ggwave_simple_get_playback_device_count()`, `ggwave_simple_get_capture_device_name()`
  - User selects devices at startup via GUI dialog (frontend)

**Volume Control:**
- Backend: `--volume` flag (1-100, default 50) passed to `ggwave.encode()` call
- Frontend: Windows audio settings (system mixer) + DLL transmission volume

## Data Flow

**Message Format:**
- **Encoding:** JSON
  - Keys: `id` (message ID), `fn` (function name), `ct` (content), optional: `ci` (chunk index), `cc` (chunk count)
- **Compression:** LZNT1 (via Windows ntdll on frontend, pure Python implementation on backend)
  - Applied to messages >100 characters
  - Base64-encoded for transport
- **Transport:** ggwave audio encoding (Audible Fast protocol)
- **Chunking:** Messages split into ~70-char base64 chunks when exceeding ~140-byte ggwave limit

**Round-Trip:**
1. Frontend: User enters draft in multiline edit control
2. Frontend: Generates message ID (Base62-encoded, 7 chars), builds JSON dict
3. Frontend: Compresses if >100 chars, Base64-encodes
4. Frontend: Chunks message, adds header (id, fn, ci, cc)
5. Frontend: Sends chunks via ggwave audio
6. Backend: Receives audio, decodes with ggwave, parses JSON
7. Backend: Buffers chunks, reassembles when complete
8. Backend: Processes through pipeline (TestPipeline or LLMPipeline)
9. Backend: Chunks response, sends back via ggwave
10. Frontend: Receives chunks, reassembles, decompresses
11. Frontend: Displays formatted report for review

**Retransmission:**
- If chunk missing after 30-second timeout, frontend sends `{"fn": "retx", "id": msgID, "ci": chunkIndex}` request
- Backend resends specific chunk on request

---

*Integration audit: 2026-03-28*
