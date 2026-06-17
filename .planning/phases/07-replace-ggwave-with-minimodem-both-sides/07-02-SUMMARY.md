---
phase: 07-replace-ggwave-with-minimodem-both-sides
plan: 02
subsystem: transport
tags: [minimodem, fsk, wrapper, pthread, rx-thread, crc32, loopback, wave0-gate, dll]

# Dependency graph
requires:
  - phase: 07-replace-ggwave-with-minimodem-both-sides
    plan: 01
    provides: "mm_core.c engine (mm_build_config/mm_tx_bytes/mm_rx_step/mm_destroy), simpleaudio-winmm.c backend, minimodem_simple.h API surface, dependency-free DLL scaffold"
provides:
  - "minimodem_simple.c: all 12 minimodem_simple_* public API bodies (init/devices/send/is_transmitting/process/receive/set_baud/cleanup/get_error)"
  - "background RX thread driving mm_rx_step into a pthread-mutex-guarded newline-framed byte queue (line + queue caps; half-duplex read-and-discard during TX)"
  - "minimodem_loopback: in-process byte-exact TX->RX self-test (in-memory simpleaudio backend, no hardware) — Wave 0 gate, byte-exact at 1200/4800/9600"
  - "cross-language CRC32 agreement vector: test/crc_vector_test.py (passes) + test/crc_vector_test.ahk (developer-box checkpoint), identical UTF-8 byte sequence + baked constants"
  - "build fix: -UNDEBUG on DLL + loopback so the vendored tone generator's assert-wrapped audio write survives Release builds"
affects:
  - "07-03 (AHK ctypes/DllCall binding + chunking.ahk crc field via Crc32Str)"
  - "07-04 (Python ctypes lib/minimodem.py + compression.py crc32_str)"
  - "07-05 (cross-machine cutover + retire ggwave/SDL2)"

# Tech tracking
tech-stack:
  added:
    - "pthreads (MinGW winpthreads, statically linked) for the background RX thread + mutex"
    - "in-memory simpleaudio backend (test-only) for hardware-free byte-exact loopback"
  patterns:
    - "ggwave_simple-mirrored C API: init/send/is_transmitting/process/receive/set_baud/cleanup/get_error with the same return-contract (length / 0-if-none / negative-on-error)"
    - "producer/consumer: blocking RX thread (mm_rx_step) -> mutex-guarded ring of newline-delimited lines drained by _receive; _process is a near no-op"
    - "load-bearing-assert hazard guard: -UNDEBUG for any target compiling simple-tone-generator.c"

key-files:
  created:
    - "minimodem-wrapper/minimodem_simple.c"
    - "minimodem-wrapper/test/loopback_test.c"
    - "minimodem-wrapper/test/crc_vector_test.py"
    - "minimodem-wrapper/test/crc_vector_test.ahk"
  modified:
    - "minimodem-wrapper/CMakeLists.txt (finalize minimodem_loopback target; -UNDEBUG on DLL + loopback)"
    - "AHK/minimodem_simple.dll (rebuilt artifact, now with working API bodies + TX fix)"

key-decisions:
  - "RX thread uses pthreads (portable to the Linux .so) per RESEARCH Threading §4; one mutex guards ALL queue access (Pitfall 7)"
  - "Half-duplex (Pitfall 3): RX thread keeps mm_rx_step draining during TX but discards decoded bytes while is_transmitting"
  - "Loopback uses a self-contained in-memory simpleaudio backend (shared float FIFO) instead of a virtual audio cable — isolates the FSK refactor with zero hardware (CONTEXT: harness is Claude's discretion)"
  - "set_baud pauses+joins the RX thread, frees fskp/samplebuf, rebuilds config, reattaches the still-open streams, and restarts the thread (mm_build_config memsets the ctx)"
  - "CRC computed over UTF-8 bytes of the ct string (Pitfall 4); expected values for both vectors baked identically into the Python and AHK tests"

patterns-established:
  - "Pattern: blocking-read RX thread + newline-framed mutex queue bridging to AHK's non-blocking 10 ms poll"
  - "Pattern: -UNDEBUG guard for vendored sources that put side effects inside assert()"

requirements-completed: []

# Metrics
duration: ~40min
completed: 2026-06-17
---

# Phase 7 Plan 02: minimodem_simple API + RX thread + Wave 0 gate Summary

**Implemented all 12 `minimodem_simple_*` public API bodies (mirroring `ggwave_simple`) with a background RX thread feeding a mutex-guarded newline-framed byte queue, stood up the byte-exact `minimodem_loopback` self-test and the cross-language CRC32 agreement vector, and fixed a Release-build bug where `-DNDEBUG` stripped the vendored tone generator's assert-wrapped audio write (TX emitted silence).**

## Performance
- **Duration:** ~40 min
- **Started:** 2026-06-17T03:20Z (approx)
- **Completed:** 2026-06-17T04:00Z
- **Tasks:** 3
- **Files created/modified:** 6

## Accomplishments
- **`minimodem_simple.c` (Task 1):** All 12 exports with working bodies. `init` builds the FSK config via `mm_build_config`, opens RX/TX `simpleaudio` streams (platform default backend → WinMM on Windows), and spawns a background RX thread. The thread loops `mm_rx_step` (which blocks inside `simpleaudio_read`), and under one `pthread_mutex_t` appends decoded bytes to a line accumulator, splitting on `\n` into a ring of complete lines that `_receive` drains bounds-checked. `_process` is a near no-op (the thread does the pumping). `_send` maps `volume`→tone amplitude (`simpleaudio_tone_init`) and toggles `is_transmitting` around `mm_tx_bytes`. `set_baud` safely pauses/rebuilds/restarts. Security V5: line length (`8192`) and queue depth (`64`) caps; half-duplex read-and-discard during TX (Pitfall 3).
- **CRC32 agreement vector (Task 2):** `crc_vector_test.py` asserts `crc32("123456789") == 0xCBF43926` and the UTF-8 multibyte+newline vector `"Liver: normal.\nCRCé" == 0xBF16E982`; `crc_vector_test.ahk` asserts the same two constants via `ntdll!RtlComputeCrc32(0,...)` over the identical `StrPut` UTF-8 byte sequence. Both bake the same expected values over the same bytes (medico-legal Pitfall 4 gate).
- **`minimodem_loopback` (Task 3):** In-process byte-exact TX→RX self-test over a self-contained in-memory `simpleaudio` backend (shared float FIFO) — no audio hardware or virtual cable required. Sweeps baud {1200, 4800, 9600} with a 564-byte report-length payload.
- Rebuilt `minimodem_simple.dll` dependency-free (KERNEL32 / WINMM / msvcrt only) and copied to `AHK/`.

## Task Commits
1. **Task 1: public API + RX thread + newline queue** — `6eacb93` (feat)
2. **Task 2: cross-language CRC32 agreement vector** — `1e96210` (test)
3. **Task 3: byte-exact loopback gate + NDEBUG TX fix** — `35526e5` (test)

## Wave 0 Gate Evidence (real output)

### Byte-exact loopback (`./build/minimodem_loopback.exe`, exit 0)
```
=== minimodem_loopback: in-process byte-exact TX->RX ===
payload: 564 bytes (64 fixed + 500 random printable)

[ OK   ] baud  1200 : byte-exact (564 bytes)
[ OK   ] baud  4800 : byte-exact (564 bytes)
[ OK   ] baud  9600 : byte-exact (564 bytes)

GATE PASS: 1200-baud loopback is byte-exact.
```
All three baud rates round-trip byte-exact in the noiseless in-memory loopback (4800/9600 did **not** need a tone override in this clean path — ASSUMPTION A2 remains to be checked on real hardware in Plan 05, where the device passband matters).

### CRC32 vector — Python (`python test/crc_vector_test.py`, exit 0)
```
crc32('123456789') = 0xCBF43926 (want 0xCBF43926)
crc32('Liver: normal.\nCRCé') = 0xBF16E982 (want 0xBF16E982)
  utf-8 bytes: 4c697665723a206e6f726d616c2e0a435243c3a9
CRC OK
```

### DLL dependency gate (`objdump -p ... | grep "DLL Name"`)
```
KERNEL32.dll
msvcrt.dll
WINMM.dll
```
Self-contained — no `libgcc`/`libwinpthread`/`libfftw3f` (static link intact).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Release `-DNDEBUG` strips the tone generator's audio write — TX emits silence**
- **Found during:** Task 3 (first loopback run decoded 0 of 564 bytes — exactly Pitfall 1's warning sign).
- **Issue:** The vendored `simple-tone-generator.c:172` emits the actual audio write inside an assertion: `assert( simpleaudio_write(sa_out, buf, nsamples_dur) > 0 );`. Upstream minimodem never builds with `-DNDEBUG`, so this side effect is always present. The CMake `Release` build defines `NDEBUG`, which compiles the assert — and its `write()` call — out entirely. The result: `mm_tx_bytes` ran but produced **zero** output samples (`g_widx == 0`), so the demodulator never saw a carrier. This also meant the **shipping DLL could not transmit** at all under the Release build.
- **Fix:** Added `target_compile_options(... -UNDEBUG)` to both the `minimodem_simple` DLL target and the `minimodem_loopback` target, keeping the load-bearing assert side effects alive in every configuration. The vendored source is left verbatim (per 07-01's vendoring decision); the fix lives in the build.
- **Files modified:** minimodem-wrapper/CMakeLists.txt
- **Verification:** Loopback went from 0/564 to byte-exact 564/564 at all baud rates; DLL rebuilt and re-verified dependency-free.
- **Committed in:** 35526e5

**2. [Rule 3 - Blocking] `*/` inside a C block comment terminated the file's header comment early**
- **Found during:** Task 1 (first DLL build failed with "missing terminating ' character" cascades).
- **Issue:** A header-comment line listed the API as `.../process/receive/set_*/cleanup/...`; the `*/` in `set_*/` closed the `/* ... */` block comment prematurely, so the prose below was parsed as C.
- **Fix:** Reworded to `set_baud/cleanup`. Also guarded the `#define MINIMODEM_SIMPLE_BUILD` with `#ifndef` to silence a redefine warning (CMake also defines it).
- **Files modified:** minimodem-wrapper/minimodem_simple.c
- **Committed in:** 6eacb93

**Total deviations:** 2 auto-fixed (1 critical bug, 1 blocking). No architectural changes. No scope creep.

## Checkpoints / Manual Verification Required (developer box)

This plan contains the Wave 0 `checkpoint:human-verify` gate. The two automatable halves were **run here and are green** (byte-exact loopback + Python CRC vector). One residual item requires the developer's Windows box:

- **AHK CRC vector (`crc_vector_test.ahk`)** — AutoHotkey v2 is **not installed on this build box** (searched Program Files + LocalAppData; absent), so the `ntdll!RtlComputeCrc32` side could not be executed headlessly. Per the plan's checkpoint fallback, the expected constants were computed via Python over the **exact UTF-8 byte sequence** (`123456789` → `0xCBF43926`; `Liver: normal.\nCRCé` UTF-8 bytes `4c69...c3a9` → `0xBF16E982`) and baked identically into both test files. The AHK helper `Crc32Str` matches the verified `RtlComputeCrc32(0,...) == zlib.crc32` convention (poly `0xEDB88320`, init/xorout `0xFFFFFFFF`).
- **Developer action to close the gate:** run `crc_vector_test.ahk` with AutoHotkey v2 and confirm `crc_result.txt` reads `CRC OK`. (The Python side and the loopback already pass.) This is the only piece that cannot be machine-verified in this environment; it is low-risk (theory verified across 3 sources in RESEARCH, and the byte sequence is pinned identically).

## Known Stubs
None. The Linux device-enumeration getters return 0 / "default" by design (ALSA/Pulse are not index-addressable the same way as WinMM; the Pi selects the default device) — this is intended behavior documented inline, not a stub blocking the plan's goal.

## Self-Check: PASSED
- All 4 created files exist on disk: `minimodem_simple.c`, `test/loopback_test.c`, `test/crc_vector_test.py`, `test/crc_vector_test.ahk`.
- All 3 task commits exist in git history: `6eacb93`, `1e96210`, `35526e5`.
- DLL exports all 12 `minimodem_simple_*` symbols (verified via `objdump -p`).
- Loopback exits 0 byte-exact; Python CRC vector exits 0 `CRC OK`; DLL dependency-free.

---
*Phase: 07-replace-ggwave-with-minimodem-both-sides*
*Completed: 2026-06-17*
