# Coding Conventions

**Analysis Date:** 2026-03-28

## Naming Patterns

**AHK Files:**
- Global variables: `ALL_CAPS_SNAKE_CASE` (e.g., `COMPRESSION_THRESHOLD`, `isInitialized`, `selectedSpeakerIndex`)
  - Configuration globals: `ALL_CAPS_SNAKE_CASE` for constants: `COMPRESSION_THRESHOLD`, `GGWAVE_PAYLOAD_LIMIT`, `LOG_FILE`
  - State globals: `camelCase` for mutable state: `selectedSpeakerIndex`, `messageCounter`, `isInitialized`
  - Buffer/Map globals: `camelCase` for container objects: `chunkReceiveBuffer`, `lastSentChunks`
- Functions: `PascalCase` (e.g., `Main()`, `ProcessAudio()`, `ChunkMessage()`, `SendChunkedMessage()`)
- Local variables: `camelCase` (e.g., `result`, `errorMsg`, `msgID`, `editCtrl`, `speakerNames`)
- JSON key names in messages: lowercase with underscores (e.g., `"id"`, `"fn"`, `"ct"`, `"ci"`, `"cc"`, `"st"`, `"z"`)

**Python Files:**
- Functions and variables: `snake_case` (e.g., `lznt1_compress()`, `handle_received_chunk()`, `chunk_receive_buffer`)
- Classes: `PascalCase` (e.g., `ReportPipeline`, `TestPipeline`, `LLMPipeline`)
- Constants: `ALL_CAPS_SNAKE_CASE` (e.g., `COMPRESSION_THRESHOLD`, `LOG_MAX_CONTENT_LENGTH`, `INTER_CHUNK_DELAY`)
- Private functions (internal use): prefix with `_` (e.g., `_lznt1_compress_chunk()`)
- JSON key names: lowercase with underscores (e.g., `"id"`, `"fn"`, `"ct"`, `"ci"`, `"cc"`, `"st"`)

## File Organization

**AHK Modular Structure:**
- Main entrypoint: `AHK/main_dll.ahk` — initializes, loads DLL, runs main loop
- Include files in `AHK/include/`:
  - `config.ahk` — all global constants and state variables
  - `logging.ahk` — file-based logging functions
  - `compression.ahk` — LZNT1 and Base64 encode/decode (Windows API)
  - `dll_manager.ahk` — DLL lifecycle (load, unload, error handling)
  - `gui.ahk` — audio device selection and multiline input dialogs
  - `chunking.ahk` — message chunking, reassembly, and retransmission logic
  - `msgid.ahk` — message ID generation (Base62 encoding)
  - `_JXON.ahk` — third-party JSON parser (vendored)

**Python Modular Structure:**
- Main entrypoint: `python-backend/backend.py` — parse args, initialize ggwave, main loop
- Library modules in `python-backend/lib/`:
  - `config.py` — constants, logging setup, session helpers
  - `audio.py` — PyAudio device enumeration
  - `compression.py` — LZNT1 compression/decompression (pure Python)
  - `chunking.py` — message chunking, reassembly, retransmission, buffer management
  - `pipeline.py` — abstract pipeline class and implementations (TestPipeline, LLMPipeline stub)
  - `__init__.py` — exports all public symbols from lib modules

## Code Style

**AHK:**
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

**Python:**
- Python 3.9+
- Indentation: 4 spaces
- Type hints: used in function signatures (e.g., `def chunk_message(msg_dict: dict) -> list[str]:`)
- Docstrings: used for modules, classes, and public functions (description of purpose and return value)
- String formatting: f-strings preferred (e.g., `f"[CHUNK] ID: {msg_id} | ...`)
- Comments: `#` for explanatory comments; `# ===== =====` for section headers
- Error handling: `try/except` for fallible operations (compression, JSON parsing, I/O)
- Logging: use module-level `logger` from `lib.config` (not `print()`)

## Import Organization

**AHK:**
- All includes at the top of the file after `#Requires AutoHotkey v2.0`
- Order: third-party/vendored first (`_JXON.ahk`), then project modules (alphabetical)
- Example from `main_dll.ahk`:
  ```
  #Include "include/_JXON.ahk"
  #Include "include/config.ahk"
  #Include "include/logging.ahk"
  #Include "include/compression.ahk"
  #Include "include/dll_manager.ahk"
  #Include "include/msgid.ahk"
  #Include "include/gui.ahk"
  #Include "include/chunking.ahk"
  ```

**Python:**
- Standard library imports first
- Third-party imports second (ggwave, pyaudio)
- Project imports last
- Example from `backend.py`:
  ```python
  import sys
  import json
  import argparse
  import time

  import ggwave
  import pyaudio

  from lib import (
      logger,
      truncate_for_log,
      ...
  )
  from lib.config import INTER_CHUNK_DELAY
  ```

## Message Protocol

**Message Dictionary Structure:**
All messages (requests and responses) use a consistent JSON-encoded dictionary:
- `id` (str, len 7): Unique message ID (Base62-encoded)
- `fn` (str): Function name or command (e.g., `"test"`, `"retx"` for retransmission)
- `ct` (str): Content (payload text, usually the actual data or response)
- `st` (str): Status code (e.g., `"S"` for success, `"E"` for error)
- `ci` (int): Chunk index (0-based), 0 if single frame
- `cc` (int): Total chunk count, 0 if single frame
- `z` (bool, optional): Legacy compression flag (removed before sending)

Chunked transmission: first chunk (`ci == 0`) carries metadata (`fn`, `st`, etc.); subsequent chunks carry only `id`, `ci`, `cc`, `ct`.

## Error Handling

**AHK Patterns:**
- DLL errors: retrieve via `GetGGWaveError()` and display in `MsgBox()`
- JSON parsing errors: caught with `try { chunkDict := Jxon_Load(&message) } catch as e { LogMessage("RECV_FAIL", ...) }`
- Validation: check return values from DLL calls (e.g., `if (result < 0) { ... }`)
- Failures log with prefix `*_FAIL` (e.g., `"CHUNK_FAIL"`, `"SEND_FAIL"`, `"RETX_FAIL"`)
- User-facing errors: `MsgBox()` with appropriate icon flag
- Recovery: retry is not automatic; user must intervene or restart

**Python Patterns:**
- General exceptions: `try/except Exception as e` for broad catching, log with `logger.error()`
- Specific exceptions: catch specific types (e.g., `except IOError`, `except json.JSONDecodeError`)
- I/O errors on compression: return empty buffer or None on failure; log and continue
- Pipeline errors: return error response dict `{"id": msg_id, "st": "E", "ct": error_text}`
- Session errors: log to both file and console via `logger` instance from `lib.config`
- Missing data gracefully degraded: e.g., default device enumeration skips missing devices with `except Exception: pass`

## Logging

**AHK Logging** (`logging.ahk`):
- Controlled by `LOG_ENABLED` and `LOG_FILE` globals (file path: `ggwave_log.txt`)
- `LogMessage(logType, content)` — logs timestamp, type tag, and message to file
- Timestamp format: `[YYYY-MM-DD HH:mm:ss.mmm] [logType] message`
- Log types: `SESSION`, `CHUNK`, `SEND`, `SEND_OK`, `SEND_FAIL`, `RECV_RAW`, `RECV_OK`, `RECV_FAIL`, `REASSEMBLE`, `RETX_SEND`, `RETX`, etc.
- Long messages truncated to `LOG_MAX_CONTENT_LENGTH` (500 chars) with indicator
- Content with newlines: escaped as `\n` in log output

**Python Logging** (`lib/config.py`):
- Module-level `logger` instance initialized with `setup_logging()`
- Both file output (`backend_log.txt`) and console output configured
- Timestamp format: `[YYYY-MM-DD HH:mm:ss.mmm] [LEVEL] message` (milliseconds added by formatter)
- Log levels: `DEBUG` (file only), `INFO` (file + console)
- Log types (prefixes): `[CHUNK]`, `[SEND]`, `[SEND_OK]`, `[RECV_RAW]`, `[RECV_FAIL]`, `[REASSEMBLE]`, `[TIMEOUT]`, `[RETX]`, etc.
- Content truncation: `truncate_for_log(text)` limits to `LOG_MAX_CONTENT_LENGTH` (500 chars)
- Session markers: `log_session_start()` and `log_session_end(reason)` wrap execution

## Comments and Documentation

**AHK Comments:**
- Inline comments explain WHY (e.g., `; Protocol 1 = AUDIBLE_FAST (good balance of speed and reliability)`)
- Section headers: `; ==================== Section Name ====================`
- Function comments: brief description above function before declaration
- Complex logic: comment block above code explaining approach
- JSON key comments: inline dict initialization (e.g., `"id", msgID, "fn", "test", "ct", result.text`)

**Python Comments and Docstrings:**
- Module docstring: brief description of module purpose
- Function docstrings: description + Args + Returns (e.g., in `chunking.py`)
  ```python
  def chunk_message(msg_dict: dict) -> list[str]:
      """Split a message dict into chunk JSON strings for transmission.

      If the message content is < COMPRESSION_THRESHOLD chars and the full JSON
      fits in GGWAVE_PAYLOAD_LIMIT, sends as a single frame with ci=0, cc=0.

      Otherwise, compresses...
      """
  ```
- Inline comments: explain non-obvious logic or implementation details
- Section headers: `# ===== Section Name =====` in module
- Logging statements: act as audit trail; prefer over comments for state tracking

## Function Design

**AHK Functions:**
- Size: typically 20-100 lines; chunking.ahk functions are longer (30-100 lines) due to complex protocol logic
- Parameters: passed as individual arguments or via Map when complex
- Return values: explicit `return` statements with data (strings, dicts, booleans, integers)
- Side effects: global state modifications documented in header comments
- Cleanup: resource cleanup (DLL unload, stream close) handled in dedicated cleanup functions

**Python Functions:**
- Size: typically 10-50 lines; chunking and compression functions 30-60 lines
- Parameters: named parameters with type hints; use dict or dataclass for complex args
- Return values: dict, list, or None; type hints indicate possible None (e.g., `dict | None`)
- Side effects: global module state (buffers, logger) modified explicitly; documented in docstring
- Context managers: PyAudio streams use context managers or explicit close calls

## Module Exports

**AHK:**
- No explicit export mechanism; included files contribute to global namespace
- Configuration globals and functions intended for use by main script

**Python:**
- `lib/__init__.py`: explicitly exports public API (config, compression, chunking, audio, pipeline)
- Private modules/functions: not exported (e.g., `_lznt1_compress_chunk()`)
- Import style: `from lib import function_name` or `from lib.module import function_name`

---

*Convention analysis: 2026-03-28*
