# Testing Patterns

**Analysis Date:** 2026-03-28

## Test Framework

**Status:** No automated test framework currently in use.

**Existing test files:**
- `python-backend/test-output-audio.py` — manual audio playback test script
- `python-backend/testing-audio.py` — manual audio device enumeration test script
- `ggwave/tests/test-ggwave.py` — upstream ggwave library tests (not part of this project)
- No AHK unit tests exist; testing is manual or through integration testing

**Recommended approach:** Manual integration testing with the audio hardware setup. No test runner configured (no pytest, unittest, or vitest).

## Test Execution

**Manual Testing:**

For Python backend:
```bash
# List audio devices
python backend.py -l

# Run with specific audio devices and protocol
python backend.py -i 5 -o 3 -v 80 -p 2

# Test audio output
python test-output-audio.py -d 3

# Test audio input/enumeration
python testing-audio.py
```

For AHK frontend:
- Run `AHK/main_dll.ahk` directly; select audio devices via GUI
- Type message in multiline dialog; send via button or Ctrl+Enter
- Observe output in message box and log file `ggwave_log.txt`

**Integration testing:** Run both frontend and backend simultaneously with USB audio cable connected between machines. Verify:
1. Message transmission and reception
2. Chunked transmission for long messages
3. Compression/decompression round-trip integrity
4. Retransmission on missing chunks (manual test by blocking audio)
5. Volume and device selection on both sides
6. Logging output in both `ggwave_log.txt` and `backend_log.txt`

## Test Coverage

**Current state:** NO AUTOMATED COVERAGE. Manual testing only.

**Not tested:**
- AHK compression/decompression logic (relies on Windows NTDLL API calls)
- AHK chunking reassembly edge cases (missing chunks, out-of-order arrival, timeout)
- AHK JSON parsing with malformed input
- Python LZNT1 compression round-trip with large payloads
- Python chunking with near-payload-limit sizes
- Pipeline error handling (TestPipeline and LLMPipeline stubs)
- Cross-platform audio device enumeration (tested only on development hardware)

**Critical missing tests:**
- Round-trip message integrity (original -> compress -> chunk -> transmit -> receive -> reassemble -> decompress -> original)
- Timeout and retransmission logic
- Compression ratio for typical report-sized payloads
- Protocol switching (Audible Fast vs. Ultrasound vs. others)

## Compression Testing

**Manual verification approach:**
1. AHK: Message entered in GUI is logged with byte count
2. Chunking debug logs show original chars vs. Base64-encoded size
3. Python backend: backend_log.txt shows compression stats on receive
4. Roundtrip: receive message back from backend, verify content matches exactly

**Example log entries:**
```
AHK (ggwave_log.txt):
[2026-03-28 13:45:22.123] [CHUNK] ID: 5a2c3k1 | Content: 1250 chars -> Base64: 1668 chars

Python (backend_log.txt):
[2026-03-28 13:45:23.456] [CHUNK] ID: 5a2c3k1 | Content: 1250 chars -> Compressed: 256 bytes -> Base64: 341 chars
```

## Chunking and Reassembly Testing

**Chunking (sending):**
- Compression happens once before chunking (best compression ratio)
- Chunks split into `CHUNK_DATA_SIZE` (70 chars base64 per chunk)
- First chunk carries metadata (`fn`, `st`, etc.); others carry only content segment
- Target example: 500-char response compresses to ~100 bytes, Base64 encodes to ~134 chars, requires ~2 chunks

**Reassembly (receiving):**
- Chunks buffered by `msg_id` in `chunkReceiveBuffer` (AHK) or `chunk_receive_buffer` (Python)
- All chunks must arrive before decompression attempted
- Timeout: `CHUNK_REASSEMBLY_TIMEOUT` (30 seconds in both)
- Missing chunk triggers retransmission request after timeout
- Malformed/invalid JSON on receive: logged and skipped

**Manual test procedure:**
1. Send long message from frontend (>200 chars to force compression)
2. Observe chunked transmission in `ggwave_log.txt`:
   ```
   [CHUNK] ID: ... | Split into N chunks
   [SEND] ID: ... | Chunk 1/N
   [SEND] ID: ... | Chunk 2/N
   ```
3. Receive from backend observes chunks arriving:
   ```
   [CHUNK_RECV] ID: ... | Chunk 1/N | Have 1/N
   [CHUNK_RECV] ID: ... | Chunk 2/N | Have 2/N
   [REASSEMBLE] ID: ... | Reassembled N chunks -> XXXX chars
   ```
4. Response returned to sender and verified intact

## Fixture and Factory Patterns

**Not used:** No test fixtures or factory pattern currently implemented. Manual message construction in both:

**AHK manual message dict:**
```autohotkey
sendDict := Map(
    "id", msgID,
    "fn", "test",
    "ct", result.text
)
```

**Python manual message dict:**
```python
complete_msg = {
    "id": msg_id,
    "fn": "test",
    "ct": content_text,
    "st": "S"
}
```

For future testing, create helper factory functions:
- AHK: `CreateTestMessage(fn, ct)` — returns properly formatted Map
- Python: `make_test_message(msg_id, fn, ct, st="S")` — returns dict

## Error Testing

**AHK Error Scenarios:**
- DLL load failure: caught in `Main()`, logged, user shown `MsgBox()` error dialog
- Invalid JSON received: `try/catch` block in `ProcessAudio()` catches and logs
- Compression failure: `CompressString()` returns `""` on error, falls back to uncompressed transmission
- Decompression failure: `DecompressString()` returns `""`, chunk reassembly returns `false`, logged as `REASSEMBLE_FAIL`
- DLL call errors: negative return values checked, error retrieved via `GetGGWaveError()`

**Example AHK error test (manual):**
1. Disconnect DLL at runtime → `ProcessAudio()` timer continues, receives nothing
2. Send gibberish JSON manually → `Jxon_Load()` throws exception, caught and logged
3. Truncate response message file → reassembly detects missing chunks, requests retransmission

**Python Error Scenarios:**
- Invalid device index: `get_device_info_by_index()` wrapped in try/except, gracefully defaults
- Malformed JSON from frontend: `json.JSONDecodeError` caught, error logged, continues to next message
- Compression error: `lznt1_compress()` returns `bytes()` on error, caught during chunking
- Pipeline not implemented: `LLMPipeline` raises `NotImplementedError` from stub methods, caught at top level, error response sent back

**Example Python error test (manual):**
1. Pass invalid JSON string to `chunk_message()` → handled by caller before chunking
2. Send compressed data with corrupted header → `lznt1_decompress()` returns empty or exception, caught in reassemble
3. Request device index that doesn't exist → device enumeration skips with try/except

## Async / Threading Patterns

**AHK:**
- Single-threaded with timer-based async: `SetTimer(ProcessAudio, 10)` processes audio every 10ms
- Blocking operations: stream read/write, DLL calls, GUI show/close
- `WinWaitClose()` blocks until dialog dismissed (acceptable for user-driven operations)
- No explicit thread management

**Python:**
- Single-threaded main loop: `while True: stream_input.read() -> process -> stream_output.write()`
- I/O blocking: PyAudio stream reads and writes block until complete or timeout
- No async/await; no threading pools
- ggwave encode/decode are synchronous

**No async test patterns:** Testing is purely sequential (send, wait for response, verify).

## Integration Testing Points

**Critical paths tested manually:**

1. **Message Send Round-trip (AHK → Python → AHK):**
   - User types draft in AHK GUI
   - Message ID generated and logged
   - Compression applied if > 100 chars
   - Chunks created and sent sequentially
   - Backend receives, parses JSON, processes via pipeline
   - Response compressed, chunked, and transmitted back
   - Frontend receives chunks, buffered and reassembled
   - Decompressed response displayed in message box

2. **Retransmission (missing chunk scenario):**
   - Frontend sends chunked message (e.g., 3 chunks)
   - Backend deliberately skips chunk 2 transmission
   - Frontend timeout triggers after 30 seconds
   - Retransmission request sent with `ci: [1]` (missing index)
   - Backend resends chunk 2
   - Frontend reassembles and displays complete message

3. **Compression Integrity:**
   - Text: "The right upper lobe demonstrates a focal pneumonic consolidation measuring 3.2 x 2.1 cm" (89 chars)
   - Below threshold, sent uncompressed
   - Text: "The right upper lobe demonstrates a focal pneumonic consolidation measuring 3.2 x 2.1 cm with associated air bronchograms. The left lung is clear. Cardiac silhouette is normal. No pleural effusions. Impression: Right upper lobe pneumonia." (245 chars)
   - Above threshold, compressed (~80 bytes), Base64 encoded (~107 chars), split into 2 chunks
   - Reassembled and decompressed on receive; must match original exactly

## Special Testing Considerations

**Hardware Setup:**
- USB audio interface (not 3.5mm jack) required for low-latency, low-noise full-duplex
- Volume calibration critical: both sides must have adequate input level without clipping
- Test with both USB speaker/mic and dedicated audio interface

**Frequency Testing:**
- Protocol 0: Audible Normal (low bandwidth, slow, reliable)
- Protocol 1: Audible Fast (default, balanced)
- Protocol 2: Audible Fastest (high bandwidth, less reliable)
- Ultrasound protocols (3, 4, 5): beyond scope of current testing

**Environmental:**
- Test in quiet environment first (no background audio interference)
- Test with typical office/clinical background noise (HVAC, alarms, etc.)
- Test with distance between devices (affects audio level)

## Coverage Gaps and Recommendations

**High Priority (missing critical tests):**
1. Compression round-trip with actual radiology report text (500+ chars)
2. Chunking boundary conditions (message exactly at payload limit, etc.)
3. Python LZNT1 decompression against Windows-compressed payloads from AHK
4. Retransmission timeout and request/response
5. Pipeline error handling (LLMPipeline exception catching)

**Medium Priority:**
1. JSON edge cases (special characters, Unicode in findings text)
2. Device enumeration with missing default input/output
3. Protocol switching during operation
4. Receiver timeout and recovery

**Low Priority (nice to have):**
1. Performance metrics (latency, throughput)
2. Power consumption on Raspberry Pi backend
3. Stress testing (rapid message sequences)

---

*Testing analysis: 2026-03-28*
