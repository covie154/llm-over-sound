---
phase: 07-replace-ggwave-with-minimodem-both-sides
plan: 01
subsystem: infra
tags: [minimodem, fsk, winmm, fftw, cmake, mingw, ctypes, audio, dll, transport]

# Dependency graph
requires:
  - phase: 06-pipeline-integration
    provides: existing transport layer (ggwave wrapper) + JSON message protocol that this transport swap preserves above the wire
provides:
  - "minimodem-wrapper/ CMake project mirroring quiet-wrapper/ (build_deps.sh, build_wrapper.sh, collect_dlls.sh)"
  - "minimodem_simple.h public API header mirroring ggwave_simple.h (12 exports; protocolId->baud, set_protocol->set_baud) — declarations only"
  - "minimodem_internal.h minimodem_ctx struct hoisting all config + TX + RX loop-carried state (carrier_band de-staticed)"
  - "mm_core.c: mm_build_config / mm_tx_bytes / mm_rx_step / mm_destroy / mm_fsk_transmit_frame / mm_build_expect_bits_string"
  - "simpleaudio-winmm.c: WinMM simpleaudio_backend (open/read/write/close) + device enumeration helpers"
  - "SA_BACKEND_WINAUDIO enum + USE_WINAUDIO-guarded dispatch case in vendored simpleaudio"
  - "dependency-free minimodem_simple.dll built under MSYS2 MinGW64 (static fftw3f), copied to AHK/"
affects:
  - "07-02 (public API bodies + RX thread + queue + loopback gate — consumes mm_core + winmm backend)"
  - "07-03/04/05 (AHK + Python ctypes binding + CRC + cutover)"

# Tech tracking
tech-stack:
  added:
    - "minimodem FSK core (vendored: fsk.c, simple-tone-generator.c, databits_ascii.c, simpleaudio dispatch)"
    - "static single-precision FFTW (libfftw3f.a) linked into the DLL"
    - "WinMM (waveOut*/waveIn*) audio backend"
  patterns:
    - "context-struct decomposition of CLI main() into reusable library functions (no statics, no stdin/stdout/signals)"
    - "one-read-and-scan-pass-per-call RX step driving a future background thread"
    - "self-contained DLL via -static -static-libgcc + static fftw3f, gated by an objdump/ntldd direct-import check"

key-files:
  created:
    - "minimodem-wrapper/CMakeLists.txt"
    - "minimodem-wrapper/build_deps.sh"
    - "minimodem-wrapper/build_wrapper.sh"
    - "minimodem-wrapper/collect_dlls.sh"
    - "minimodem-wrapper/minimodem_simple.h"
    - "minimodem-wrapper/minimodem_internal.h"
    - "minimodem-wrapper/mm_core.c"
    - "minimodem-wrapper/simpleaudio-winmm.c"
    - "minimodem-wrapper/vendor/ (fsk.c/.h, simple-tone-generator.c, databits_ascii.c, databits.h, simpleaudio.c/.h/_internal.h, simpleaudio-alsa.c, simpleaudio-pulse.c, mm_strings_compat.h)"
    - "AHK/minimodem_simple.dll (built artifact)"
  modified:
    - ".gitattributes (*.sh eol=lf)"

key-decisions:
  - "carrier_band hoisted from minimodem.c's function-static into minimodem_ctx (thread/instance safety, Pitfall 1)"
  - "RX float format with S16->float fallback on WAVERR_BADFORMAT; TX/RX both 48k mono"
  - "WAVEHDR ring depth N=4 with CALLBACK_EVENT (never callback-thread waveX calls); immediate waveInAddBuffer recycle"
  - "vendored upstream sources kept verbatim; MinGW bzero gap solved via force-included compat shim, not by editing vendored files"
  - "dependency gate uses DIRECT imports (objdump -p / ntldd), not recursive ntldd -R (which walks the whole system DLL tree)"

patterns-established:
  - "Pattern: minimodem.c main() -> mm_build_config/mm_tx_bytes/mm_rx_step/mm_destroy context-struct library"
  - "Pattern: WinMM blocking simpleaudio backend matching the ALSA/Pulse synchronous read/write contract"
  - "Pattern: zero-redistributable DLL verified by a build-time direct-import dependency gate"

requirements-completed: []

# Metrics
duration: ~20min
completed: 2026-06-17
---

# Phase 7 Plan 01: minimodem-wrapper foundation + WinMM backend Summary

**Decomposed minimodem.c's `main()` TX/RX loops into a context-struct C library (`mm_core.c`), implemented a new WinMM `simpleaudio` backend, and produced a dependency-free `minimodem_simple.dll` (static fftw3f, only KERNEL32/WINMM/msvcrt imports) under MSYS2 MinGW64.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-17T11:22Z (approx)
- **Completed:** 2026-06-17T11:40Z (approx)
- **Tasks:** 3
- **Files modified/created:** 19 (project scaffold + vendored core + 3 new C/H files + built DLL)

## Accomplishments
- Scaffolded `minimodem-wrapper/` mirroring `quiet-wrapper/`, vendored the minimodem core DSP (fsk, tone gen, ascii-8 databits, simpleaudio dispatch + Linux backends), and added `SA_BACKEND_WINAUDIO` with a `USE_WINAUDIO`-guarded dispatch case (ALSA/Pulse retained for Linux).
- Wrote `minimodem_simple.h` mirroring `ggwave_simple.h` exactly (12 exports; `protocolId`->`baud`, `set_protocol`->`set_baud`, `init(int,int,int baud)`).
- Refactored `minimodem.c`'s fused 1000-line `main()` into `minimodem_ctx` + `mm_build_config` (baud->mark/space/band_width derivation + RX plan/buffer prep) + `mm_tx_bytes` (leader/8-N-1/trailer, no stdin/select/itimer/signals) + `mm_rx_step` (one read-and-scan pass per call, bounded byte output) + `mm_destroy`. Every loop-carried RX local — including the former function-static `carrier_band` — now lives in the ctx (Pitfall 1 / Anti-Patterns).
- Implemented `simpleaudio-winmm.c`: the 4-function `simpleaudio_backend_winaudio` over `waveOut*`/`waveIn*` with synchronous blocking read/write, `CALLBACK_EVENT`, a WAVEHDR ring (N=4), immediate `waveInAddBuffer` recycle (Pitfall 2), 48k mono, IEEE_FLOAT with S16 fallback, and `waveXxxGetNumDevs`/`GetDevCaps` device enumeration (`-1`->`WAVE_MAPPER`).
- Built `minimodem_simple.dll` end-to-end under MSYS2 MinGW64 and verified it is self-contained.

## Task Commits

1. **Task 1: Scaffold project + vendor core sources** - `d66411a` (feat)
2. **Task 2: Refactor minimodem.c main() into mm_core.c** - `73b354f` (feat)
3. **Task 3: WinMM backend + build dependency-free DLL** - `b02b94a` (feat)

## Build / Dependency-Gate Evidence (real output, Task 3)

Full chain run under MSYS2 MinGW64 (gcc 15.2.0, cmake 4.2.3, static `/c/msys64/mingw64/lib/libfftw3f.a`):

```
########## build_deps.sh ##########
=== Verification ===
  [OK] libfftw3f.a (/c/msys64/mingw64/lib/libfftw3f.a)
  [OK] fftw3.h (/c/msys64/mingw64/include/fftw3.h)
All dependencies present. Run build_wrapper.sh to build minimodem_simple.dll.

########## build_wrapper.sh ##########
[1/7] Building C object .../vendor/databits_ascii.c.obj
[2/7] Building C object .../vendor/simpleaudio.c.obj
[3/7] Building C object .../vendor/simple-tone-generator.c.obj
[4/7] Building C object .../vendor/fsk.c.obj
[5/7] Building C object .../mm_core.c.obj
[6/7] Building C object .../simpleaudio-winmm.c.obj
[7/7] Linking C shared library minimodem_simple.dll
Build succeeded: .../build/minimodem_simple.dll      (5,347,648 bytes)

########## collect_dlls.sh ##########
--- Imported DLLs ---
KERNEL32.dll
WINMM.dll
msvcrt.dll
PASS: only Windows system DLLs are imported. DLL is self-contained.
Copied minimodem_simple.dll -> AHK/
```

`objdump -p minimodem_simple.dll | grep "DLL Name"` direct imports = `KERNEL32.dll`, `WINMM.dll`, `msvcrt.dll` only. No `libgcc*`/`libwinpthread*`/`libstdc++*`/`libfftw3f*` (Pitfall 5 avoided — FFTW-01 smoke gate green). `ntldd` (installed via pacman) and `objdump` agree.

## Files Created/Modified
- `minimodem-wrapper/CMakeLists.txt` - two targets (DLL + optional loopback stub gated on source existence), PREFIX "", static fftw3f + winmm + `-static -static-libgcc -static-libstdc++` on Windows; fftw3f + ALSA/Pulse + pthread on Linux; force-includes the bzero compat shim
- `minimodem-wrapper/build_deps.sh` - MSYS2 package install (with pacman fallback) + verifies `libfftw3f.a`/`fftw3.h` under `/mingw64` or `/c/msys64/mingw64`, prints source-build fallback (A1)
- `minimodem-wrapper/build_wrapper.sh` - cmake configure (Ninja or MSYS Makefiles) + build
- `minimodem-wrapper/collect_dlls.sh` - copies DLL to AHK/ and FAILs on any non-system direct import (objdump/ntldd)
- `minimodem-wrapper/minimodem_simple.h` - public API (declarations) mirroring ggwave_simple.h
- `minimodem-wrapper/minimodem_internal.h` - `minimodem_ctx` + core function declarations
- `minimodem-wrapper/mm_core.c` - decomposed FSK TX/RX engine (compiles clean -Wall -Wextra)
- `minimodem-wrapper/simpleaudio-winmm.c` - WinMM backend + device enumeration
- `minimodem-wrapper/vendor/*` - vendored minimodem core (databits.h trimmed of baudot include; simpleaudio.c/.h/_internal.h get SA_BACKEND_WINAUDIO; mm_strings_compat.h added)
- `AHK/minimodem_simple.dll` - the built, verified dependency-free artifact
- `.gitattributes` - `*.sh eol=lf`

## Decisions Made
- **carrier_band de-staticed into ctx** — upstream had it as a function-static at minimodem.c:1180; promoting it is required for the future RX thread and any multi-instance use.
- **Verbatim vendoring + force-included compat shim** — rather than editing `fsk.c`/`simple-tone-generator.c` to fix MinGW's missing `bzero`, a `-include vendor/mm_strings_compat.h` keeps the upstream sources byte-for-byte, easing future minimodem updates.
- **Direct-import dependency gate** — `ntldd -R` recurses into the entire Windows system DLL tree (api-ms-*/ext-ms-* sets), which is noise; the gate checks the DLL's own import table via `objdump -p` (ntldd non-recursive fallback). This is the meaningful "is THIS dll self-contained" test.
- **WAVEHDR ring N=4, ~rate/4 frames per header** — Claude's-discretion starting point per CONTEXT; tuned for no-underrun at low baud first, to be validated empirically in the Plan 02 loopback gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MinGW `<strings.h>` does not declare `bzero`**
- **Found during:** Task 3 (DLL build)
- **Issue:** Vendored `fsk.c` and `simple-tone-generator.c` call `bzero` (a BSD/glibc-ism); MinGW's `strings.h` omits it, so the build failed with `implicit declaration of function 'bzero'`.
- **Fix:** Added `vendor/mm_strings_compat.h` (`bzero -> memset`) and force-included it on the Windows build via `target_compile_options(... -include ...)`. Vendored sources left untouched. (A function-like `-D` macro was tried first but CMake drops parenthesized definitions, so the force-include shim is the robust path.)
- **Files modified:** minimodem-wrapper/vendor/mm_strings_compat.h, minimodem-wrapper/CMakeLists.txt
- **Verification:** Clean build; DLL links.
- **Committed in:** b02b94a

**2. [Rule 3 - Blocking] `WAVE_FORMAT_IEEE_FLOAT` not declared via `<mmsystem.h>`**
- **Found during:** Task 3
- **Issue:** `simpleaudio-winmm.c` failed to compile — `WAVE_FORMAT_IEEE_FLOAT` undeclared.
- **Fix:** Added `#include <mmreg.h>` and a `#ifndef`-guarded `#define WAVE_FORMAT_IEEE_FLOAT 0x0003` fallback.
- **Files modified:** minimodem-wrapper/simpleaudio-winmm.c
- **Verification:** Clean compile -Wall -Wextra.
- **Committed in:** b02b94a

**3. [Rule 1 - Bug] Invalid C placeholder in winmm malloc-failure paths**
- **Found during:** Task 3 (self-review before build)
- **Issue:** Initial draft used a nonsense `sa_winmm_close(sa_pre:;)` placeholder for malloc-failure cleanup.
- **Fix:** Replaced with real cleanup (free partial buffers, close wave handle + event, free state, return 0).
- **Files modified:** minimodem-wrapper/simpleaudio-winmm.c
- **Committed in:** b02b94a

**4. [Rule 3 - Blocking] CRLF line endings break MSYS bash for build scripts**
- **Found during:** Task 3 (running scripts)
- **Issue:** With `* text=auto`, `*.sh` got CRLF in the Windows working tree; MSYS/MinGW bash mis-parses CRLF scripts.
- **Fix:** Added `*.sh text eol=lf` to `.gitattributes` and normalized the working-tree scripts to LF.
- **Files modified:** .gitattributes, minimodem-wrapper/*.sh
- **Committed in:** b02b94a

**5. [Rule 3 - Blocking] build_deps.sh assumed pacman on PATH and /mingw64 mount**
- **Found during:** Task 3
- **Issue:** Launched from Git Bash, `pacman` and the `/mingw64` prefix aren't visible; `set -e` aborted and the fftw3f verify reported missing.
- **Fix:** Added a pacman locator (falls back to `/c/msys64/usr/bin/pacman.exe`, or skips install) and a prefix-search across `/mingw64` and `/c/msys64/mingw64`. No new packages are auto-installed beyond the documented toolchain set (Rule-3-excluded installs are toolchain, not registry packages).
- **Files modified:** minimodem-wrapper/build_deps.sh
- **Committed in:** b02b94a

---

**Total deviations:** 5 auto-fixed (4 blocking, 1 bug)
**Impact on plan:** All necessary to compile/link/run on the developer's MSYS2 MinGW64 box. No scope creep — the public API bodies, RX thread, and loopback gate remain Plan 02 as designed.

## Issues Encountered
- `fsk.h` has no include guard; including it both directly and via `minimodem_internal.h` caused a `struct fsk_plan` redefinition. Resolved by including only `minimodem_internal.h` (which pulls in `fsk.h` once) in `mm_core.c`.
- The build had to be driven directly (PATH=/c/msys64/mingw64/bin) since this session runs from Git Bash rather than the MSYS2 MinGW64 shell; the committed scripts themselves were verified to run clean once line endings were normalized.

## Environment / Worktree Note
- Phase-07 planning files and the `minimodem/` upstream source are **untracked** in the main repo, so they were not present on this isolated worktree branch. They were copied into the worktree to vendor from and to write the SUMMARY. `minimodem/` itself remains untracked (external upstream) and is intentionally NOT committed; only the vendored copies under `minimodem-wrapper/vendor/` are committed.

## Next Phase Readiness
- `mm_core.c` (decomposed FSK engine) and `simpleaudio-winmm.c` (backend) compile and link into a self-contained DLL — ready for Plan 02 to add the public API bodies, the background RX thread + newline-framed queue, and the byte-exact loopback gate (Wave 0).
- ASSUMPTION A2 (high-baud tones may exceed device passband) and A4 (USB interface 48k mono float support) remain to be validated on real hardware during the Plan 02 loopback / Plan 05 cross-machine tests.
- `mm_build_config` already returns a clean error (not a crash) when `fsk_plan_new` rejects high-baud tones, so the high-baud failure mode is surfaced, not fatal.

## Self-Check: PASSED

All 13 claimed files exist on disk (project scaffold, vendored core, mm_core.c,
simpleaudio-winmm.c, build scripts, AHK/minimodem_simple.dll, this SUMMARY).
All 3 task commits exist in git history: `d66411a`, `73b354f`, `b02b94a`.

---
*Phase: 07-replace-ggwave-with-minimodem-both-sides*
*Completed: 2026-06-17*
