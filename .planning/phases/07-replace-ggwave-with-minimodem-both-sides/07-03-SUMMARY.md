---
phase: 07-replace-ggwave-with-minimodem-both-sides
plan: 03
subsystem: frontend-transport
tags: [ahk, minimodem, dllcall, crc32, single-frame, transport, frontend, baud]

# Dependency graph
requires:
  - phase: 07-replace-ggwave-with-minimodem-both-sides
    plan: 02
    provides: "minimodem_simple.dll with all 12 minimodem_simple_* API bodies (init/devices/send/is_transmitting/process/receive/set_baud/cleanup/get_error), newline-framed RX queue, and the proven cross-language CRC32 vector (crc_vector_test.ahk, 0xCBF43926)"
provides:
  - "AHK frontend loads minimodem_simple.dll and calls minimodem_simple_init/send/is_transmitting/process/receive/cleanup/get_error (no ggwave_simple_* calls remain in main_dll.ahk or chunking.ahk)"
  - "config.ahk: BAUD_RATE global (default 1200); ggwaveDll renamed to minimodemDll; chunking constants marked dormant"
  - "compression.ahk: Crc32Str(str) via ntdll!RtlComputeCrc32 over UTF-8 bytes, copied verbatim from the proven CRC vector (matches Python zlib.crc32)"
  - "chunking.ahk: single-frame (ci=0, cc=1) + crc send path via ChunkMessage; CRC-verified receive with full-message retransmit on mismatch (never surfaces a corrupt report); dormant ChunkMessageSplit/ReassembleChunks retained for v2"
affects:
  - "07-04 (Python ctypes binding + chunking.py single-frame + crc32_str must mirror this framing/CRC exactly)"
  - "07-05 (cross-machine cutover + retire ggwave/SDL2)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-frame + message-level CRC32 transport (v1): every message is one newline-terminated JSON frame (ci=0, cc=1) carrying crc=Crc32Str(ct); CRC mismatch -> discard + full-message retransmit (ci=[0]), never surface a partial report (medico-legal)"
    - "Stable public send entry points: MainLoop's ChunkMessage/SendChunkedMessage call site is unchanged; ChunkMessage now returns a 1-element array holding the single CRC frame and SendChunkedMessage sends it via minimodem and caches it in lastSentChunks for retx"
    - "Dormant-by-rename: legacy multi-chunk split preserved as ChunkMessageSplit; ReassembleChunks/CheckChunkTimeouts kept intact for v2 chunking"

key-files:
  created: []
  modified:
    - "AHK/include/config.ahk (BAUD_RATE := 1200; minimodemDll; dormant chunking constants)"
    - "AHK/include/dll_manager.ahk (LoadMinimodemDll/UnloadMinimodemDll/GetMinimodemError -> minimodem_simple.dll)"
    - "AHK/include/compression.ahk (Crc32Str via ntdll!RtlComputeCrc32; LZNT1/Base64 untouched)"
    - "AHK/include/chunking.ahk (single-frame + crc send; CRC-verified receive + full retransmit; all transport DllCalls repointed to minimodem_simple\\*; dormant chunking retained)"
    - "AHK/main_dll.ahk (LoadMinimodemDll; minimodem_simple_init(speaker, mic, BAUD_RATE); minimodem cleanup/error; baud in SESSION log)"

key-decisions:
  - "Crc32Str copied verbatim from minimodem-wrapper/test/crc_vector_test.ahk (the Wave 0 proven helper) so the AHK CRC equals Python zlib.crc32 byte-for-byte over UTF-8 bytes of ct (Pitfall 4)"
  - "CRC field travels as a JSON number; receive compares numerically (receivedCrc + 0) != expectedCrc to avoid string/number mismatch"
  - "retx request and resent single frame are newline-terminated to match the wrapper's newline framing; the stored frame in lastSentChunks already carries its newline, so retx resends it verbatim"
  - "Legacy multi-chunk split renamed to ChunkMessageSplit (not deleted) so the active ChunkMessage entry point unambiguously routes MainLoop through the single-frame path with no dead-code caller"
  - "config.ahk log-file name (ggwave_log.txt) and LZNT1/Base64 functions left unchanged — out of scope for this plan (transport repoint only)"

patterns-established:
  - "Pattern: integrity-gated receive — verify Crc32Str(ct) == crc BEFORE HandleCompleteMessage; on failure log RECV_FAIL and SendRetransmissionRequest(msgID, [0]), surface nothing"

requirements-completed: []

# Metrics
duration: ~25min
completed: 2026-06-17
tasks: 2
files: 5
---

# Phase 7 Plan 3: AHK Frontend Transport Swap (ggwave to minimodem) Summary

Repointed the AutoHotkey v2 frontend from ggwave to minimodem FSK single frames with CRC32 integrity: it loads `minimodem_simple.dll`, inits with a configurable `BAUD_RATE` (default 1200), attaches a `crc` field (matching Python `zlib.crc32`) to every newline-framed single frame, and discards-plus-retransmits on a CRC mismatch instead of ever surfacing a corrupt report. No `ggwave_simple_*` calls remain in the frontend's transport path, and the legacy split/reassemble code is retained dormant for v2 chunking.

## What Was Built

### Task 1 — DLL repoint + init with baud + Crc32Str (commit 76d9272)
- `config.ahk`: added `global BAUD_RATE := 1200`; renamed `ggwaveDll` -> `minimodemDll`; annotated `GGWAVE_PAYLOAD_LIMIT`/`CHUNK_DATA_SIZE`/`INTER_CHUNK_DELAY`/`CHUNK_REASSEMBLY_TIMEOUT` as dormant (single-frame v1).
- `dll_manager.ahk`: `LoadMinimodemDll`/`UnloadMinimodemDll`/`GetMinimodemError` loading `minimodem_simple.dll` (script-dir then current-dir fallback), error via `minimodem_simple\minimodem_simple_get_error`.
- `main_dll.ahk`: `Main()` now calls `LoadMinimodemDll()`, inits via `DllCall("minimodem_simple\minimodem_simple_init", "Int", speaker, "Int", mic, "Int", BAUD_RATE, "Int")` (the old protocol-1 arg is now baud), cleanup via `minimodem_simple_cleanup`, errors via `GetMinimodemError`; SESSION log line now includes baud.
- `compression.ahk`: added `Crc32Str(str)` copied verbatim from the proven `crc_vector_test.ahk` (StrPut UTF-8 buffer excluding NUL; `ntdll\RtlComputeCrc32(0, ptr, len)`; returns 0 for empty). LZNT1/Base64 untouched.

### Task 2 — Single-frame + CRC send and CRC-verified receive (commit 45fb639)
- `ChunkMessage(msgDict)` is now the v1 single-frame builder: copies caller fields, sets `ci=0, cc=1`, drops the legacy `z` flag, sets `crc = Crc32Str(ct)`, and returns `[Jxon_Dump(single) . "\n"]` (newline-framed). MainLoop's `ChunkMessage`/`SendChunkedMessage` call site is unchanged.
- Legacy split preserved as `ChunkMessageSplit` (dormant); `ReassembleChunks`/`CheckChunkTimeouts` retained.
- `SendChunkedMessage` sends the single frame via `minimodem_simple_send` (volume 50), waits on `minimodem_simple_is_transmitting`, and caches it in `lastSentChunks[msgID]` for retx.
- `ProcessAudio` receive path: pumps `minimodem_simple_process`, drains `minimodem_simple_receive`; on a parsed frame with `cc == 1` it computes `expected := Crc32Str(ct)` and compares numerically. Match -> `HandleCompleteMessage` (crc stripped). Mismatch (or absent crc) -> `RECV_FAIL` log, no content surfaced, `SendRetransmissionRequest(msgID, [0])`.
- Dormant branches retained: `cc == 0` legacy single, and `cc > 1` multi-chunk buffering + `ReassembleChunks`.
- `SendRetransmissionRequest` and `HandleRetransmissionRequest` repointed to `minimodem_simple\*`; retx request is newline-framed; the stored single frame already carries its newline so retx resends it verbatim.
- All log tags preserved (CHUNK/SEND/SEND_OK/RECV_RAW/RECV_OK/RECV_FAIL/RETX_SEND/RETX/RETX_FAIL); `Jxon_Load` stays wrapped in the existing `try/catch as e` so noise-decoded garbage is discarded (Security V5).

## Verification

Source-level acceptance (grep, all PASS):
- Task 1: `BAUD_RATE := 1200` in config.ahk; `minimodem_simple.dll` in dll_manager.ahk; `minimodem_simple_init` + `BAUD_RATE` in main_dll.ahk; `RtlComputeCrc32` in compression.ahk; no `ggwave_simple_init` in main_dll.ahk.
- Task 2: `Crc32Str` + `minimodem_simple_send` + `minimodem_simple_receive` in chunking.ahk; no `ggwave_simple_send` in chunking.ahk.
- Cross-file: zero `ggwave_simple_*` occurrences across `AHK/main_dll.ahk` and `AHK/include/chunking.ahk`.
- Dormant retained: `ChunkMessageSplit` and `ReassembleChunks` present in chunking.ahk.
- MainLoop send call site (`ChunkMessage` line 92, `SendChunkedMessage` line 95) unchanged and routes through the single-frame path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Newline framing on retx request frame**
- **Found during:** Task 2
- **Issue:** The minimodem wrapper splits the FSK byte stream on `\n`, but `SendRetransmissionRequest` emitted `Jxon_Dump(retxDict)` with no newline. Without it, a retx request would never be delimited and the peer could never frame it — defeating the integrity loop the plan requires.
- **Fix:** Appended `. "\`n"` to the retx JSON (mirrors `ChunkMessage`'s framing). The resent single frame in `lastSentChunks` already carries its newline, so `HandleRetransmissionRequest` resends it verbatim.
- **Files modified:** AHK/include/chunking.ahk
- **Commit:** 45fb639

**2. [Rule 2 - Correctness] Numeric CRC comparison**
- **Found during:** Task 2
- **Issue:** `crc` arrives as a JSON number; a naive `==` against the AHK integer `Crc32Str` result risks a string/number type mismatch that would 100%-fail valid messages.
- **Fix:** Compare with `(receivedCrc + 0) != expectedCrc` and treat an absent crc as a mismatch (request retransmit). Documents intent and avoids the silent retransmit loop.
- **Files modified:** AHK/include/chunking.ahk
- **Commit:** 45fb639

## Checkpoints / Developer Follow-up (runtime not executed)

AutoHotkey v2 is not installed on this build box, so the AHK script could not be executed here (same situation as Wave 2's AHK CRC vector). The source-level work and all grep acceptance checks are complete and pass. The developer must run, on a Windows box with AutoHotkey v2 + the built `minimodem_simple.dll` in `AHK/`:

1. `minimodem-wrapper/test/crc_vector_test.ahk` against the real `ntdll` — confirm `crc_result.txt` reports `CRC OK` (canonical `0x CBF43926`, the UTF-8 vector `0xBF16E982`). This re-proves `Crc32Str` on the developer box.
2. Launch `AHK/main_dll.ahk`, select the audio devices, confirm it initializes minimodem at `BAUD_RATE` (check `ggwave_log.txt` SESSION line includes `Baud: 1200`), and that a typed message transmits as a single CRC frame.

The cross-machine AHK<->Pi round trip (induced-corruption CRC + full retransmit, baud sweep) is Wave 4 / hardware regardless and is out of scope for this plan.

## Known Stubs

None. No placeholder/empty-data stubs were introduced; the transport path is fully wired.

## Self-Check: PASSED
- Files exist: config.ahk, dll_manager.ahk, compression.ahk, chunking.ahk, main_dll.ahk — all FOUND.
- Commits exist: 76d9272 (Task 1), 45fb639 (Task 2) — both in git log.
- Acceptance greps: all PASS; zero `ggwave_simple_*` in main_dll.ahk and chunking.ahk; dormant ChunkMessageSplit/ReassembleChunks retained.
- Runtime AHK execution: deferred to developer checkpoint above (interpreter unavailable on this box; not fabricated).
