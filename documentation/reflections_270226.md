# Session Reflection — 27 Feb 2026

## Objective

Implement the chunking subsystem described in TODO.md so that messages exceeding
ggwave's 140-byte payload ceiling can be transmitted reliably between the AHK
frontend and the Python backend.

---

## What was done

### 1. Chunk protocol schema design

Defined a JSON framing convention that both sides share:

| Field | Type   | Purpose                                        |
|-------|--------|------------------------------------------------|
| `id`  | string | 7-char Base62 message ID (unchanged)           |
| `ci`  | int    | Chunk index (0-based)                          |
| `cc`  | int    | Total chunk count                              |
| `ct`  | string | Payload data (plain text or base64 slice)      |

**Single-frame shortcut:** When `cc == 0`, the message is unchunked — `ct` is
plain text, no compression overhead.  This replaces the old `z` flag approach:
short messages (under `COMPRESSION_THRESHOLD`, currently 100 chars) skip
compression and chunking entirely, saving bandwidth on the dominant case.

**Chunked messages:** Content is LZNT1-compressed as a single block, then
base64-encoded, then sliced into `CHUNK_DATA_SIZE` (70 char) pieces.  Chunk 0
carries metadata keys (`fn`, `st`, etc.); subsequent chunks carry only
`id`/`ci`/`cc`/`ct`.

**Retransmission request:** `{"id":"X","fn":"retx","ci":[0,3]}` — a list of
missing chunk indices.

### 2. Python backend changes (`python-backend/backend.py`)

- **Removed:** `decompress_json_message()` and `compress_response_dict()` — the
  old per-message compression/decompression helpers that operated on the `z` flag.
- **Added chunking functions:**
  - `chunk_message(msg_dict)` — decides single-frame vs multi-chunk, handles
    LZNT1 + base64 + slicing, warns if any chunk exceeds 140 bytes.
  - `handle_received_chunk(chunk_dict)` — buffers incoming chunks keyed by
    message ID, returns the reassembled dict once all `cc` chunks arrive, or
    `None` while waiting.
  - `reassemble_chunks(msg_id)` — concatenates base64 slices in `ci` order,
    base64-decodes, LZNT1-decompresses, reconstructs the original message dict.
  - `check_chunk_timeouts()` — polls the receive buffer; if a message's chunks
    have been incomplete for > `CHUNK_REASSEMBLY_TIMEOUT` (30 s), emits a
    retransmission request.
  - `send_chunks(chunks, stream_output, ...)` — sequential transmit with
    `INTER_CHUNK_DELAY` (0.5 s) between chunks; stores chunks in
    `last_sent_chunks` for retransmission.
  - `handle_retransmission_request(retx_dict, ...)` — resends only the chunks
    listed in the `ci` array.
- **Refactored `process_input()`:** Now accepts a `dict` directly instead of a
  raw JSON string, eliminating a redundant `json.loads()` that the caller had
  already performed.
- **Rewrote the main loop:** Chunk-aware receive path (JSON parse → retx check →
  `handle_received_chunk` → `process_input` → `chunk_message` → `send_chunks`).
  Timeout checks run on every loop iteration.

### 3. AHK frontend changes (`AHK/main_dll.ahk`)

- **Added globals:** `GGWAVE_PAYLOAD_LIMIT`, `CHUNK_DATA_SIZE`,
  `INTER_CHUNK_DELAY`, `CHUNK_REASSEMBLY_TIMEOUT`, `chunkReceiveBuffer`,
  `lastSentChunks`.
- **New send path:**
  - `ChunkMessage(msgDict)` — mirrors the backend's `chunk_message()`: builds a
    single-frame Map if the JSON fits, or LZNT1-compresses + base64-encodes +
    splits.  Falls back to single frame if compression fails.
  - `SendChunkedMessage(chunks, msgID)` — iterates through chunks, calls the DLL
    send, waits for each transmission to finish, inserts `INTER_CHUNK_DELAY` ms
    between chunks.  Stores chunks in `lastSentChunks`.
- **New receive path in `ProcessAudio()`:**
  - Parses each received JSON frame.
  - If `fn == "retx"`, delegates to `HandleRetransmissionRequest()`.
  - Otherwise feeds the chunk to the receive buffer keyed by message ID.
  - On `cc == 0`, treats as single frame and calls `HandleCompleteMessage()`.
  - When `buf["chunks"].Count == cc`, calls `ReassembleChunks()` →
    `HandleCompleteMessage()`.
- **`ReassembleChunks(msgID)`** — concatenates base64 slices in `ci` order,
  calls existing `DecompressString()` (Base64 → LZNT1 decompress via ntdll).
- **Timeout / retransmission:**
  - `CheckChunkTimeouts()` runs on every `ProcessAudio()` tick; if a message
    has been incomplete for > 30 s, calls `SendRetransmissionRequest()`.
  - `HandleRetransmissionRequest()` resends the requested chunk indices from
    `lastSentChunks`.
- **Removed:** Old `SendMessage()` function and the inline decompression /
  `z`-flag logic in the old `ProcessAudio()`.

### 4. `MainLoop()` simplification

The old `MainLoop()` manually compressed, set a `z` flag, built JSON, and
called `SendMessage()`.  The new version builds a plain `Map("id",…,"fn",…,"ct",…)`,
passes it to `ChunkMessage()`, and hands the result to `SendChunkedMessage()`.
All compression/framing concerns are encapsulated inside those two functions.

### 5. TODO.md updated

All four chunking items marked `[x]` with inline notes on the chosen schema and
constants.

---

## How it was done

1. **Context gathering first.** Read `CLAUDE.md`, `TODO.md`, both source files
   end-to-end, the ggwave wrapper header/source, and the upstream ggwave source
   (`ggwave.h`, `ggwave.cpp`) to confirm the hard payload limit
   (`kMaxLengthVariable = 140`).

2. **Schema before code.** Designed the `ci`/`cc` framing convention and the
   `cc == 0` single-frame shortcut before writing any implementation, ensuring
   both sides would agree on semantics.

3. **Backend first, then frontend.** The backend is pure Python and easier to
   reason about; implementing it first let me validate the function signatures
   and data flow, then mirror them on the AHK side.

4. **Batched edits.** Used multi-replace operations to apply several independent
   changes (imports, constants, function replacements, main loop rewrite) in a
   single tool call per file, reducing round-trips.

5. **Preserved existing compression code.** The LZNT1 compress/decompress and
   Base64 functions on both sides were kept unchanged — the chunking layer sits
   above them.

---

## Design decisions and rationale

| Decision | Rationale |
|----------|-----------|
| `CHUNK_DATA_SIZE = 70` | A chunk JSON envelope (`{"id":"XXXXXXX","ci":0,"cc":10,"ct":"..."}`) is ~45 bytes of framing.  70 + 45 = 115, well under 140, with headroom for metadata keys on chunk 0. |
| `cc == 0` means unchunked | Avoids wasting bytes on compression + base64 for short messages (the common case during interactive use).  Replaces the old `z` flag, so there's no net increase in schema complexity. |
| Metadata only on chunk 0 | Keeps subsequent chunks minimal.  The receiver stores metadata from chunk 0 and merges it into the reassembled dict. |
| `INTER_CHUNK_DELAY = 0.5 s` (backend) / `200 ms` (frontend) | The backend delay is longer because the Pi transmitter may need more time for the audio to finish and the receiver to settle.  The frontend uses the DLL's `is_transmitting` poll plus a shorter gap. |
| Retransmission by explicit request | Rather than blind retry, the receiver identifies exactly which chunks are missing and asks for them.  This is more efficient over the bandwidth-limited audio channel. |
| `last_sent_chunks` buffer | Simple dict keyed by message ID.  Not bounded — acceptable in practice because message volume is low (a handful of reports per session). |

---

## What worked

- **Reading the upstream ggwave source** to confirm `kMaxLengthVariable = 140`
  removed all guesswork about payload budgets.  The `CLAUDE.md` doc said "approximately
  140 bytes" — confirming it was an exact constant in the C++ header gave confidence
  to set tight margins.

- **Mirroring function signatures** between Python and AHK (e.g.,
  `chunk_message` / `ChunkMessage`, `handle_received_chunk` / inline in
  `ProcessAudio`) made the two sides easy to reason about in parallel.

- **The `cc == 0` shortcut** avoided a flag proliferation problem.  The old
  code had a `z` compression flag; adding `ci`/`cc` on top of that would have
  been three extra fields.  Collapsing single-frame messages into `ci=0, cc=0`
  with no compression keeps short messages lean.

- **Batched multi-replace edits** — applying 4–5 replacements in a single tool
  call per file kept the edit flow fast and reduced the chance of partial
  application leaving the file in an inconsistent state.

## What didn't work / risks

- **No empirical testing yet.** The chunk sizes and delays are theoretical.
  The 70-char `CHUNK_DATA_SIZE` should be safe, but real-world audio corruption
  rates and timing jitter could require tuning.  TODO items for hardware testing
  remain open.

- **`Jxon_Dump` output differs from `json.dumps`.**  AHK's JXON library
  escapes forward slashes (`/` → `\/`) and may order keys differently.  The
  protocol is JSON-value-level compatible (both sides parse the other's output),
  but the byte lengths will differ slightly.  This means the AHK side's
  single-frame length check (`StrLen(singleJson) <= GGWAVE_PAYLOAD_LIMIT`)
  could be a few bytes pessimistic relative to the backend's — a safe direction
  to be wrong in.

- **No cap on `last_sent_chunks` / `lastSentChunks`.**  For a high-throughput
  system this would be a memory leak.  Acceptable here because radiology report
  volume is low, but a future improvement would be to cap the buffer to the
  last N message IDs.

- **Retransmission is request-based, not ACK-based.**  If the retransmission
  request itself is lost, the receiver will simply re-request after another
  timeout cycle.  This could be slow for very large messages over a noisy
  channel.  An ACK-per-chunk scheme would be more robust but doubles the number
  of transmissions.

- **The `process_input()` signature change is a breaking internal API change.**
  It now takes a `dict` instead of a JSON string.  Any future code that calls
  it must pass a dict.  This is fine — the function's only caller is the main
  loop — but worth noting for maintainability.
