# Phase 7: Replace ggwave with minimodem (both sides) - Research

**Researched:** 2026-06-17
**Domain:** C/audio-systems port — FSK modem library extraction, Windows WinMM audio backend, static FFTW linking, cross-language CRC32, ctypes FFI
**Confidence:** HIGH (codebase + official docs verified); MEDIUM on WinMM ring-buffer tuning (must be validated empirically at low baud)

## Summary

This is a transport-layer swap, not a feature build. Every layer above transport (GUI, message protocol, LZNT1 compression, Base62 encoding, message IDs, chunking scaffolding) is preserved. The work is concentrated in a new `minimodem-wrapper/` C project that produces `minimodem_simple.dll` (Windows) and `libminimodem_simple.so` (Linux), exposing the **exact** API surface of `ggwave_simple.h` so AHK's `DllCall` model and the Python `ctypes` binding stay nearly unchanged.

The single biggest correctness risk is refactoring `minimodem.c`'s `main()` — which currently fuses argument parsing, stream setup, the TX loop, and the RX demod loop into one 1000-line function — into reusable context-struct-based functions. The RX loop (lines 1137–1463 of `minimodem.c`) is a stateful sliding-window scanner over a sample buffer that calls `fsk_find_frame`; it must be hoisted intact into a function that the background RX thread drives one iteration at a time, with all of its loop-local state (`samplebuf`, `samples_nvalid`, `advance`, `carrier`, `track_amplitude`, `peak_confidence`, `noconfidence`, `nframes_decoded`) promoted into a context struct. The TX side is much simpler: `fsk_transmit_frame` (already a standalone static function) plus the leader/preamble/data/trailer sequence extracted from `fsk_transmit_stdin`, fed bytes from a buffer instead of `read(stdin)`.

**Primary recommendation:** Build with **MSYS2/MinGW64** (the exact toolchain already proven by `quiet-wrapper/`), statically link `fftw3f` and `libwinpthread`/`libgcc`/`libstdc++` (so the DLL is self-contained), implement `simpleaudio-winmm.c` against `simpleaudio-pulse.c` as the structural template (it is the simplest blocking backend), and gate the entire port behind a **byte-exact DLL loopback test** before touching AHK or Python. Treat the CRC32 "byte-identical across AHK/Python" claim as **must-verify-with-a-test-vector**, not an assumption — `ntdll!RtlComputeCrc32(0, buf, len)` is documented to equal zlib's `crc32` (same polynomial `0xEDB88320`, same `~init`/`~result` convention), but this is a medico-legal integrity check and must be proven with a shared test vector in CI/test, not trusted blind.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| FSK modulation (bytes → tones) | Wrapper C (`simple-tone-generator.c` + extracted TX) | — | Vendored from minimodem; deterministic DSP |
| FSK demodulation (audio → bytes) | Wrapper C (`fsk.c` + extracted RX loop) | — | Vendored; needs `fftw3f` FFT |
| Audio device I/O (Windows) | Wrapper C (`simpleaudio-winmm.c`) | — | New backend over `waveIn*`/`waveOut*` |
| Audio device I/O (Linux/Pi) | Wrapper C (`simpleaudio-alsa.c`/`-pulse.c`) | — | Existing minimodem backends, reused as-is |
| Background RX thread + queue | Wrapper C (`minimodem_simple.c`) | — | Decouples continuous demod from AHK's 10ms poll |
| Device enumeration | Wrapper C (WinMM `waveXxxGetDevCaps`) | AHK GUI / Python `audio.py` | Index-based selection mirrors ggwave API |
| Message framing (JSON, id/fn/ct/st/ci/cc + crc) | AHK `chunking.ahk` / Python `chunking.py` | — | Above transport; unchanged except single-frame + crc |
| CRC32 integrity | AHK `compression.ahk` (`ntdll!RtlComputeCrc32`) / Python `compression.py` (`zlib.crc32`) | — | Must be byte-identical; verified by shared vector |
| LZNT1 compress + Base62 encode | AHK `compression.ahk` / Python `compression.py` | — | Unchanged from ggwave era |
| Baud configuration | AHK `config.ahk` (`BAUD_RATE`) / Python `backend.py` (`--baud`) | Wrapper `_set_baud` | Link parameter; both ends must match |

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scope** — Both sides move to minimodem. ggwave and minimodem are wire-incompatible; one-sided swap is not viable.

**Windows audio**
- New `simpleaudio-winmm.c` implementing the `simpleaudio_backend` 4-function struct over `waveOut*`/`waveIn*`.
- WinMM chosen for zero-install portability (`winmm.dll` ships with Windows; statically linkable → single copy-pasteable binary). No Cygwin/PulseAudio/PortAudio.
- Device enumeration via `waveOutGetNumDevs`/`waveOutGetDevCaps` and `waveInGetNumDevs`/`waveInGetDevCaps`; `backend_device` selects by integer index.

**Packaging / API**
- `minimodem_simple.dll` mirrors `ggwave_simple.h` API exactly so AHK keeps its `DllCall` model and `chunking.ahk`/`compression.ahk`/`gui.ahk`/`msgid.ahk` are reused nearly unchanged.
- API surface: `minimodem_simple_init(int playbackDeviceId, int captureDeviceId, int baud)`, device count/name getters, `_send(msg, volume)`, `_is_transmitting`, `_process`, `_receive(buf, size)`, `_set_baud(int)` (replaces `set_protocol`), `_cleanup`, `_get_error`.
- The old `protocolId` parameter becomes `baud`.
- A background RX thread runs continuous `waveIn` → `fsk_find_frame` → decoded-byte queue, so AHK's existing 10 ms `process()` poll + `receive()` drain model is preserved unchanged. `send()` modulates to `waveOut`.

**Reused minimodem core (vendored from minimodem/src/)**
- `fsk.c`/`fsk.h` (demod), `simple-tone-generator.c` (mod), `databits_ascii.c` (8-N-1), `simpleaudio.c`/`simpleaudio_internal.h` (dispatch). Linux keeps existing `simpleaudio-alsa.c`/`simpleaudio-pulse.c`.
- minimodem.c's TX and RX loops (currently in `main()`) are refactored into reusable library functions — this is the bulk of the work and the main correctness risk.

**Pi side** — Same wrapper compiled as `libminimodem_simple.so` (ALSA/Pulse backend), called from Python via a new `lib/minimodem.py` `ctypes` binding — symmetric API on both ends. Replaces the ggwave Python binding in the transport path.

**Integrity (v1)**
- Single framed message + message-level CRC32. No chunking in v1 (latency-first).
- Keep LZNT1 compression, Base62 encoding (newline-safe), and the `id`/`fn`/`ct`/`st`/`ci`/`cc` JSON schema with `ci=0`, `cc=1`.
- New `crc` field (CRC32 of `ct`) on every message: AHK via `ntdll!RtlComputeCrc32`, Python via `zlib.crc32`.
- Framing: newline-delimited JSON over the FSK byte stream.
- On CRC mismatch or timeout: full-message retransmit via the existing retransmit path. Never surface a partial/corrupt report.
- Split/reassemble code paths in `chunking.ahk`/`chunking.py` are retained but dormant, ready for v2 chunking.

**FFTW** — `fsk.c` requires single-precision `fftw3f`; statically link it so the DLL stays self-contained. Goertzel rewrite deferred to v2.

**License** — minimodem is GPLv3. A DLL built from its source is GPLv3 and loads into the AHK process. Accepted for internal/research use; noted in spec.

**Baud** — Configurable end-to-end, default 1200. AHK: `BAUD_RATE` global in `config.ahk`. Python: `--baud` CLI arg (default 1200). Baud is a link parameter — both ends MUST match. Must be tunable without recompiling.

**Build** — CMake, mirroring `ggwave-wrapper/` (`build_wrapper.sh`, `collect_dlls.sh`). Windows links `winmm.lib`; goal is zero redistributable DLLs beyond the one wrapper file. Verify dependency-free with a dependency walker.

### Claude's Discretion
- Exact WAVEHDR ring-buffer sizing/count for the WinMM backend (tune to avoid underruns at low baud first).
- Internal queue/threading primitives in the wrapper.
- Default FSK tone frequencies (use minimodem defaults unless tuning demands otherwise).
- Test harness specifics for the loopback test (virtual audio cable choice).

### Deferred Ideas (OUT OF SCOPE)
- Chunking with large (~200-word ≈ ~1 KB) chunks for long payloads; dormant split/reassemble code stays in place.
- Reed-Solomon-per-chunk FEC (e.g. RS(255,223)); fountain codes (LT/Raptor).
- Goertzel 2-tone detection to drop the FFTW dependency.
- Auto baud negotiation between ends.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

No formal REQ-XX IDs were supplied for this phase. Requirements are derived from the design contract and CONTEXT.md locked decisions. The planner should treat the locked decisions above as the requirement set. Key derived requirements:

| Derived ID | Description | Research Support |
|------------|-------------|------------------|
| TX-01 | One-shot TX of a byte buffer over `waveOut` | minimodem.c decomposition map (§ minimodem.c Decomposition); `fsk_transmit_frame` is already standalone |
| RX-01 | Continuous RX demod loop driven by background thread | RX loop hoist map; context struct fields enumerated |
| WINMM-01 | WinMM backend implementing 4-function `simpleaudio_backend` | `simpleaudio-pulse.c` template + WAVEHDR ring pattern |
| FFTW-01 | Static `fftw3f` producing dependency-free DLL | MSYS2/MinGW64 build path; `--enable-single` |
| CRC-01 | Byte-identical CRC32 across AHK and Python | `RtlComputeCrc32(0,...)` == `zlib.crc32`; shared test vector required |
| API-01 | DLL mirrors `ggwave_simple.h` exactly | Side-by-side API map provided |
| CFG-01 | Baud configurable end-to-end without recompile | `_set_baud` + AHK `BAUD_RATE` + `--baud` |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

These directives carry the same authority as locked decisions. The planner must not recommend approaches that contradict them.

- **AHK v2.0 strict syntax only.** No v1 syntax. `if (cond) { ... }`, `.` for string concat, `try/catch as e`.
- **AHK naming:** globals `ALL_CAPS_SNAKE_CASE`, functions `PascalCase`, locals `camelCase`, JSON keys lowercase-with-underscores.
- **Python naming:** functions/vars `snake_case`, classes `PascalCase`, constants `ALL_CAPS_SNAKE_CASE`, private `_prefixed`. Python 3.9+. 4-space indent. Type hints in signatures. f-strings.
- **Logging is file-based.** AHK → `ggwave_log.txt` via `LogMessage(type, content)`; Python → `backend_log.txt` via module `logger` (never `print()`). Existing log type tags must be preserved.
- **Both sides must stay in sync.** Any change to encoding, compression, framing, or chunking on one side MUST be mirrored on the other or the pipe breaks. (This is doubly true for the new `crc` field and the baud parameter.)
- **C++ wrapper built via CMake**, output to `build/`. New wrapper mirrors `ggwave-wrapper/` layout.
- **GSD workflow enforcement:** all edits go through a GSD command (already satisfied — this is a planned phase).
- **Medico-legal:** transport must never silently surface a corrupt/partial report. CRC mismatch → discard + full retransmit. (Reinforces the integrity decision.)
- **The final production frontend is a text replacer** (per MEMORY.md `user_ahk_text_replacer.md`); the current GUI is a test harness. Do not over-invest in GUI changes — `gui.ahk`/`msgid.ahk` are explicitly unchanged.

---

## Standard Stack

This phase does **not** introduce npm/PyPI packages. It vendors existing C source and links one external C library (`fftw3f`). The "stack" is the toolchain and the vendored sources.

### Core
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| MSYS2 + mingw-w64-x86_64 toolchain | current | Windows DLL build | Already proven by `quiet-wrapper/build_deps.sh`; produces native PE DLLs without Cygwin runtime dependency [VERIFIED: quiet-wrapper/build_deps.sh] |
| `fftw3f` (single-precision FFTW3) | 3.3.10 | FFT for `fsk.c` demod | Required by `fsk.h` (`#include <fftw3.h>`, `fftwf_*` calls) [VERIFIED: minimodem/src/fsk.c] |
| CMake | ≥ 3.10 | Build system | Mirrors `ggwave-wrapper/` and `quiet-wrapper/` [VERIFIED: existing CMakeLists.txt] |
| `winmm` (winmm.lib / winmm.dll) | system | Windows audio backend | Ships with every Windows; statically linkable import [CITED: learn.microsoft.com waveOutWrite] |
| ALSA or PulseAudio dev libs (Pi) | system | Linux audio backend | Already supported by minimodem `simpleaudio-alsa.c`/`-pulse.c` [VERIFIED: minimodem/src] |

### Supporting (vendored from `minimodem/src/`, no version — pinned to the in-repo copy)
| File | Purpose | Modification Needed |
|------|---------|--------------------|
| `fsk.c` / `fsk.h` | FSK demodulation core | None (use as-is); compiles against `fftw3f` |
| `simple-tone-generator.c` | FSK tone modulation (`simpleaudio_tone`) | None |
| `databits_ascii.c` / `databits.h` | 8-N-1 passthrough encode/decode | None |
| `simpleaudio.c` / `simpleaudio_internal.h` / `simpleaudio.h` | Backend dispatch + struct | Add `SA_BACKEND_WINAUDIO` enum value + dispatch case guarded by `USE_WINAUDIO` |
| `simpleaudio-alsa.c` / `simpleaudio-pulse.c` | Linux backends | None (Linux build only) |
| `minimodem.c` | Source of TX/RX loops | **Decompose** `main()` → library functions (the bulk of the work) |

### New files to author
| File | Purpose |
|------|---------|
| `minimodem-wrapper/simpleaudio-winmm.c` | New WinMM backend (4-function struct) |
| `minimodem-wrapper/minimodem_simple.c` / `.h` | Public API + background RX thread + extracted TX/RX |
| `minimodem-wrapper/CMakeLists.txt` | Build both targets |
| `minimodem-wrapper/build_deps.sh` | Build/install `fftw3f` static lib in MSYS2 |
| `minimodem-wrapper/build_wrapper.sh` | Build the DLL |
| `minimodem-wrapper/collect_dlls.sh` | Copy DLL to `AHK/` + verify deps |
| `python-backend/lib/minimodem.py` | ctypes binding (replaces ggwave binding) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MinGW64 | MSVC | MSVC cannot consume an MSYS2-built `libfftw3f.a` directly — requires `dlltool` import-lib conversion [CITED: github.com/FFTW/fftw3 issues]. MinGW64 is already the working toolchain for `quiet-wrapper`. **Recommend MinGW64.** |
| WinMM | WASAPI/PortAudio/SDL2 | All require extra redistributable DLLs or more complex code; WinMM is locked by CONTEXT.md and ships with Windows. |
| Static fftw3f | Goertzel rewrite | Goertzel drops FFTW entirely but is deferred to v2 (locked). |

**Installation (MSYS2 MinGW64 terminal):**
```bash
pacman -S --needed --noconfirm \
    mingw-w64-x86_64-gcc \
    mingw-w64-x86_64-fftw \
    mingw-w64-x86_64-cmake \
    mingw-w64-x86_64-pkgconf \
    make
```
> `mingw-w64-x86_64-fftw` provides single, double, and long-double FFTW including the **static** `libfftw3f.a` and `fftw3.h`. Confirm `libfftw3f.a` exists under `/mingw64/lib/` before building. [ASSUMED — verify the package ships the static `.a`; if not, build from source with `--enable-single --enable-static --disable-shared` per FFTW MINGW64 build script.]

**On the Pi (Debian/Raspberry Pi OS):**
```bash
sudo apt-get install libfftw3-dev libasound2-dev   # fftw3f is in libfftw3-dev; ALSA dev headers
```

## Package Legitimacy Audit

> This phase installs no language-package-manager packages (no npm/PyPI/crates). It vendors in-repo C source and links system/toolchain libraries. slopcheck is **not applicable** — there is nothing to slopcheck.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `mingw-w64-x86_64-fftw` | MSYS2 pacman | mature | n/a | fftw.org / FFTW/fftw3 | N/A | Approved (official MSYS2 repo) |
| `libfftw3-dev` | Debian apt | mature | n/a | fftw.org | N/A | Approved (Debian main) |
| `fftw3f` (source) | fftw.org | 3.3.10 (2021) | n/a | github.com/FFTW/fftw3 | N/A | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none (no registry packages).
**Packages flagged as suspicious [SUS]:** none.

> No `checkpoint:human-verify` gating is required for package legitimacy here. The only external binary dependency, FFTW, is a 25-year-old MIT-acknowledged numerical library from fftw.org. The planner SHOULD still gate the **license** acknowledgement (GPLv3) as a human checkpoint per the design spec.

---

## minimodem.c Decomposition (the core of the phase)

`minimodem.c` fuses everything into `main()` (lines 489–1481). The decomposition splits it into a context struct + a config-building function + one TX function + one RX-step function. CLI-only concerns are stripped entirely.

### What to STRIP (CLI-only, never in the library)
| Concern | Location in minimodem.c | Why strip |
|---------|------------------------|-----------|
| `getopt_long` argument parsing | lines 569–782 | Replaced by `init(baud)` + defaults |
| `usage()`, `version()` | 378–440 | CLI help |
| `benchmarks()` + `SA_BACKEND_BENCHMARK` | 305–365 | Perf harness |
| `--file` / sndfile backend | scattered, 790–800, 969–972 | No file I/O in DLL |
| `report_no_carrier()` stderr reporting | 253–291, 1300, 1469–1474 | stderr-only; replace with optional log |
| `signal(SIGINT/SIGALRM)` handlers | 60–74, 368–374, 1135, 1467 | No signals in a DLL thread; loop is driven externally |
| `read(fd, ...)` from stdin (TX) | 184 | Replace with bytes from caller's buffer |
| `write(1, ...)` to stdout (RX) | 1452, 1458 | Replace with push to thread-safe queue |
| baudot/callerid/uic/SAME/RTTY modes | 819–886 | v1 is 8-N-1 ASCII only; `databits_ascii.c` only |
| `--inverted`, `--mark`/`--space`, `--startbits`, sync-byte, msb-first | various | Use minimodem defaults; not exposed in v1 |
| carrier autodetect (`-a`) | 1179–1220 | Fixed baud/tones known; autodetect not needed (and adds latency) |

### Context struct to HOIST (replaces `main()` locals)

Create `typedef struct minimodem_ctx { ... }`. Fields, grouped by origin:

**Config (set once at `init`, derived from baud — see § Baud/Tone Params):**
```c
float    bfsk_data_rate;     // = baud
float    bfsk_mark_f, bfsk_space_f;   // derived from baud (minimodem.c 900–934)
float    band_width;        // derived from baud
unsigned bfsk_n_data_bits;  // = 8
int      bfsk_nstartbits;   // = 1
float    bfsk_nstopbits;    // = 1.0
unsigned sample_rate;       // = 48000
float    fsk_confidence_threshold;     // = 1.5  (minimodem.c:519)
float    fsk_confidence_search_limit;  // = 2.3  (minimodem.c:528)
unsigned bfsk_frame_n_bits; // = n_data + nstart + nstop = 10
char     expect_data_string[64];       // built by build_expect_bits_string()
unsigned expect_n_bits, expect_nsamples;
float    nsamples_per_bit;
unsigned nsamples_overscan, frame_nsamples;
```

**TX state (extracted from `fsk_transmit_stdin` globals at lines 49–58):**
```c
simpleaudio *sa_out;
float    tx_bfsk_mark_f;
unsigned tx_bit_nsamples;
int      tx_leader_bits_len, tx_trailer_bits_len;  // 2, 2
```
> NOTE: The TX-side file-scope globals `tx_sa_out`, `tx_bfsk_mark_f`, `tx_bit_nsamples`, `tx_transmitting` (lines 49–58) exist only to support the `SIGALRM` sighandler. Once signals are stripped, these become local/ctx fields and the sighandler-based "flush" path is replaced by an explicit trailer-emit after the data bytes.

**RX state (loop-carried locals from the main loop, lines 1056–1133) — MUST be promoted into the ctx so the thread can call one step at a time:**
```c
fsk_plan *fskp;             // from fsk_plan_new(), minimodem.c:1045
float    *samplebuf;        // malloc'd, minimodem.c:1071
size_t    samplebuf_size;
size_t    samples_nvalid;
unsigned  advance;
int       carrier;
float     confidence_total, amplitude_total;
unsigned  nframes_decoded;
size_t    carrier_nsamples;
unsigned  noconfidence;
float     track_amplitude, peak_confidence;
int       carrier_band;     // was a function-static at minimodem.c:1180 — MUST become a ctx field (statics are not thread/instance safe)
simpleaudio *sa_in;
```

### Functions to EXTRACT

1. **`minimodem_ctx *mm_build_config(int baud, unsigned sample_rate)`**
   Implements minimodem.c lines 882–965 (the baud → mark/space/bw/frame derivation) plus the RX prep at 1037–1131 (`fsk_plan_new`, samplebuf sizing, `build_expect_bits_string`, overscan). Returns a populated ctx (without open streams).
   *Reuse `build_expect_bits_string()` verbatim — it is already standalone (lines 442–487).*

2. **`int mm_tx_bytes(minimodem_ctx *ctx, const unsigned char *buf, size_t len)`**
   The TX path, extracted from `fsk_transmit_stdin` (114–250) minus stdin/select/itimer:
   - emit leader tone: `tx_leader_bits_len` × mark (lines 211–212)
   - (no sync bytes for plain ASCII; `bfsk_do_tx_sync_bytes==0`)
   - for each byte: `encode(bits, byte)` then `fsk_transmit_frame(...)` (lines 225–228, 81–112)
   - emit trailer: `tx_trailer_bits_len` × mark (the body of `tx_stop_transmit_sighandler`, 65–66)
   - `simpleaudio_tone_reset()` before starting (phase continuity)
   *`fsk_transmit_frame` (81–112) is already a clean standalone static function — lift it unchanged.*

3. **`int mm_rx_step(minimodem_ctx *ctx, char *out, size_t out_size)`**
   The body of the `while(1)` RX loop (1137–1463), refactored so **one call performs one read-and-scan pass** and returns 0..N decoded bytes (instead of looping forever and `write()`ing to stdout). The structure to preserve exactly:
   - shift `samplebuf` by `advance` (1144–1156)
   - if `samples_nvalid < samplebuf_size/2`: `simpleaudio_read(sa_in, ...)` to refill (1158–1174) — **this is the blocking call** that the WinMM backend provides
   - `fsk_find_frame(...)` (1265–1274) + the confidence/refine logic (1276–1389)
   - on success: `bit_window`, `databits_decode_ascii8` → bytes (1414–1446), append to `out`
   - set `advance` for next call (1318 on no-confidence, 1407 on success)
   - **Skip** carrier-autodetect block (1179–1220) — tones are known.
   Return decoded byte count; the thread loop in `minimodem_simple.c` repeatedly calls this and pushes bytes to the queue.

4. **`void mm_destroy(minimodem_ctx *ctx)`** — `free(samplebuf)`, `fsk_plan_destroy(fskp)`, close streams.

### Concrete "extract these" map (quick reference for the planner)
```
build_expect_bits_string()  -> reuse verbatim
fsk_transmit_frame()        -> reuse verbatim (rename mm_fsk_transmit_frame, make non-static)
fsk_transmit_stdin() body   -> mm_tx_bytes()   (strip stdin/select/itimer/sighandler)
main() lines 882–965        -> mm_build_config() (baud->tone derivation)
main() lines 1037–1131      -> mm_build_config() (RX buffer/plan prep)
main() lines 1137–1463      -> mm_rx_step()     (one pass per call; queue instead of stdout)
main() cleanup 1465–1480    -> mm_destroy()
```

---

## WinMM Backend (`simpleaudio-winmm.c`)

The new backend implements the `simpleaudio_backend` struct (`simpleaudio_internal.h` lines 41–60): four function pointers `open_stream`, `read`, `write`, `close`, plus device enumeration helpers. Use `simpleaudio-pulse.c` as the structural template — it is the simplest blocking backend and its `read`/`write` return `nframes` synchronously.

### The contract to satisfy
`simpleaudio_read(sa, buf, nframes)` and `simpleaudio_write(sa, buf, nframes)` are **synchronous/blocking**: they must not return until `nframes` frames have been read/written (see ALSA backend `sa_alsa_read`/`sa_alsa_write` which loop until `frames_read == nframes`). `mm_rx_step` depends on `read` blocking; `simpleaudio_tone` asserts `simpleaudio_write(...) > 0` (tone generator line 172).

Format/rate: **48000 Hz, mono (1 channel)**. RX uses `SA_SAMPLE_FORMAT_FLOAT` (minimodem.c:787-788 forces float for the FFT); TX uses `SA_SAMPLE_FORMAT_S16` by default (minimodem.c:533) but FLOAT also works. `WAVEFORMATEX`: `wFormatTag = WAVE_FORMAT_PCM` for S16, `WAVE_FORMAT_IEEE_FLOAT` for float; `nChannels=1`, `nSamplesPerSec=48000`, `wBitsPerSample=16 or 32`, `nBlockAlign = nChannels*wBitsPerSample/8`, `nAvgBytesPerSec = nSamplesPerSec*nBlockAlign`.

### Output (`waveOut`) — blocking write via WAVEHDR ring
- `waveOutOpen(&hwo, deviceIndex, &wfx, 0, 0, CALLBACK_NULL)` — use `CALLBACK_EVENT` with an auto-reset event, OR poll `WHDR_DONE`. Recommend **`CALLBACK_EVENT`** (cleaner than busy-polling, lower latency than `Sleep`).
- Maintain a small ring of N `WAVEHDR`s (start N=4). For each `write(buf, nframes)`:
  - copy samples into a free header's buffer, `waveOutPrepareHeader`, `waveOutWrite`.
  - if all N headers are in-flight, `WaitForSingleObject(doneEvent, ...)` until one reports `WHDR_DONE`, then `waveOutUnprepareHeader` (or reuse — Microsoft notes you may rewrite an already-prepared buffer and re-send without unprepare [CITED: learn.microsoft.com waveOutWrite]).
- `close`: drain (wait for all headers `WHDR_DONE`), `waveOutReset`, unprepare all, `waveOutClose`.

### Input (`waveIn`) — blocking read via WAVEHDR ring
- `waveInOpen(&hwi, deviceIndex, &wfx, (DWORD_PTR)event, 0, CALLBACK_EVENT)`.
- At open: allocate N `WAVEHDR`s (start N=4, each holding e.g. `samplebuf_size/2` frames worth, matching minimodem's half-buffer read of `read_nsamples = samplebuf_size/2` at minimodem.c:1160), `waveInPrepareHeader` + `waveInAddBuffer` all of them, then `waveInStart`.
- `read(buf, nframes)`: loop pulling from the **head** header once it has `WHDR_DONE` set (wait on the event), copy out frames, then **immediately `waveInAddBuffer` that header again to recycle it**, and continue until `nframes` satisfied. Convert S16→float if the device delivered S16 and minimodem asked for float (but request float format directly to avoid conversion — most class-compliant USB interfaces support `WAVE_FORMAT_IEEE_FLOAT` at 48k mono; fall back to S16 + manual convert if `waveInOpen` returns `WAVERR_BADFORMAT`).
- `close`: `waveInStop`, `waveInReset`, unprepare all, `waveInClose`.

### Device enumeration (mirror ggwave API by integer index)
```c
int  mm_playback_device_count(void)  { return waveOutGetNumDevs(); }
int  mm_capture_device_count(void)   { return waveInGetNumDevs(); }
// names via waveOutGetDevCaps(i, &caps, sizeof caps) -> caps.szPname (WAVEOUTCAPS)
//          waveInGetDevCaps(i,  &caps, sizeof caps) -> caps.szPname (WAVEINCAPS)
```
`backend_device` (the `const char *` in the struct) is parsed as an integer index for WinMM (mirror how `init` already takes int device IDs). `-1` → `WAVE_MAPPER` (system default).

### Windows gotchas (landmines)
1. **Never call waveOut/waveIn functions from inside `waveOutProc`/`waveInProc` callbacks** — `waveOutWrite`/`waveInAddBuffer` can deadlock there. Use `CALLBACK_EVENT`, not `CALLBACK_FUNCTION`. [CITED: experts-exchange / MS docs] Doing the recycle from a callback is the classic deadlock.
2. **`waveInAddBuffer` recycling is mandatory** — if you don't re-add buffers fast enough, capture silently drops samples → corrupt FSK. Keep N≥3 and re-add immediately after copying out.
3. **`WHDR_DONE` polling vs event:** prefer `CALLBACK_EVENT`. Busy-polling `dwFlags & WHDR_DONE` with `Sleep(1)` works but wastes CPU; raw spin-poll can starve the audio thread.
4. **`waveOutReset` before close** or the drain may hang if headers are stuck.
5. **`szPname` is truncated to 31 chars** in `WAVEOUTCAPS`/`WAVEINCAPS` — device names may not be unique/full. Acceptable for index-based selection.
6. **Latency floor:** WinMM has higher latency than WASAPI, but throughput is set by baud, not the API (per design spec). At 1200 baud this is irrelevant; validate at 9600.
7. **Mono requirement:** `simpleaudio.c:123-128` aborts if `sa->channels != channels`. Ensure `waveInOpen`/`waveOutOpen` get exactly 1 channel; some devices only offer stereo — if so, you must open stereo and downmix, which complicates the framesize math. Verify the target USB interface offers mono 48k first.

---

## FFTW Static Linking

### Recommendation: MinGW64 (matches `quiet-wrapper`)
The existing `quiet-wrapper` already builds its DLL in MSYS2 MinGW64 and ships MinGW runtime DLLs alongside. For minimodem the goal is *zero* redistributables, so go one step further and **static-link** the MinGW runtime too.

### Windows build (MSYS2 MinGW64)
1. Install static fftw3f: `pacman -S mingw-w64-x86_64-fftw` (provides `/mingw64/lib/libfftw3f.a` + `/mingw64/include/fftw3.h`). [ASSUMED the pacman package ships the static `.a`; if it only ships `.dll.a`, build from source:]
   ```bash
   ./configure --enable-single --enable-static --disable-shared --enable-sse2 --prefix=/mingw64
   make && make install     # yields libfftw3f.a
   ```
   FFTW's official MinGW64 build script confirms `--enable-single` for the `f` (single-precision) variant. [CITED: github.com/FFTW/fftw3 support/BUILD-MINGW64.sh]
2. In CMake link flags, force the GCC runtime static and prefer the static fftw:
   ```cmake
   target_link_options(minimodem_simple PRIVATE
       -static -static-libgcc -static-libstdc++)
   target_link_libraries(minimodem_simple PRIVATE
       /mingw64/lib/libfftw3f.a winmm)
   ```
   `-static` pulls in `libwinpthread` statically too (needed for the RX thread).
3. **Verify zero non-system deps** with `ntldd -R build/minimodem_simple.dll` (MSYS2) or Dependencies.exe / Dependency Walker. The only allowed deps are Windows system DLLs: `KERNEL32.dll`, `msvcrt.dll`, `WINMM.dll`, `USER32.dll`, `ADVAPI32.dll` (for `ntdll` it's loaded by AHK, not the wrapper). Anything starting `libgcc`/`libwinpthread`/`libfftw3f` appearing in the dep list means static linking failed — fix before shipping.

> **MSVC is NOT recommended.** An MSYS2-built `libfftw3f.a` is not directly consumable by MSVC; you'd need `dlltool` to synthesize an import lib, or build fftw3f separately with MSVC + CMake (FFTW supports a CMake build). This adds a whole second toolchain. [CITED: github.com/FFTW/fftw3 PR #161; install/windows.html] Since `quiet-wrapper` already standardized on MinGW64, stay there.

### Linux build (Pi)
```bash
sudo apt-get install libfftw3-dev libasound2-dev
# CMake: find fftw3f, link libfftw3f + libasound (ALSA) or libpulse
```
On Linux, `.so` with a dynamic `libfftw3f.so` dependency is fine (apt-installed, always present). Static linking is unnecessary on the Pi.

---

## Threading Model

### Confirmed design (works with AHK's 10ms poll)
The background-RX-thread + thread-safe-queue design is sound and is the right way to bridge minimodem's blocking `simpleaudio_read` to AHK's non-blocking 10ms `process()`/`receive()` poll.

```
RX thread (created in init):  loop { mm_rx_step(ctx, tmp, n);  // BLOCKS on waveIn read
                                     lock; queue.append(decoded_bytes); unlock; }
AHK timer (every 10ms):       _process()  // no-op or housekeeping; RX runs on its own thread
                              _receive(buf, size)  // lock; drain newline-framed message from queue; unlock
```

### Key decisions for the planner
1. **`_process()` becomes nearly a no-op.** In ggwave it pumped SDL queues; here the RX thread does the pumping. Keep `_process()` so AHK's loop and the API signature are unchanged, but it just returns 0 (or does light housekeeping). [VERIFIED: ggwave_simple.cpp `_process` is the SDL pump; the RX thread replaces it]
2. **`_receive()` drains the decoded-byte queue and extracts one newline-delimited JSON message** (framing is `\n`-delimited JSON per design spec line 158). The wrapper should accumulate decoded bytes until it sees `\n`, then hand a complete line to `_receive`. Mirrors the existing `ggwave_simple_receive` contract (return length, 0 if none).
3. **Half-duplex: pause RX during TX.** Recommended. While `_send` is modulating to `waveOut`, the device's own output may bleed into `waveIn` (especially speaker/mic rig) and the demodulator would try to decode the outgoing carrier. Set an `is_transmitting` flag the RX thread checks (skip queueing while transmitting), OR stop `waveIn` during TX. Simplest robust approach: RX thread checks `atomic is_transmitting`; if set, it still reads (to keep the buffer drained) but discards. **Validate empirically** — on a clean wired full-duplex link you may not need to pause; on speaker/mic you will. [ASSUMED — confirm on the actual rig]
4. **Locking:** a single mutex around the queue + an `is_transmitting` atomic is sufficient. The existing ggwave wrapper used `std::mutex`; since the new wrapper is C, use `pthread_mutex_t` (MinGW winpthreads) or Win32 `CRITICAL_SECTION`. `pthread` is portable to the Linux build — **prefer pthreads** for one codebase.
5. **`_is_transmitting()`** returns the atomic flag; AHK's `SendChunkedMessage` busy-waits on it (`while DllCall(...is_transmitting) Sleep(50)`). Set it true at start of `_send`, false when the `waveOut` drain completes.

---

## CRC32 — Byte-Identical Across AHK and Python

### The claim, verified
`ntdll!RtlComputeCrc32(0, data, len)` produces the **same** value as Python's `zlib.crc32(data)`:
- Same polynomial **`0xEDB88320`** (reflected CRC-32). [VERIFIED: ReactOS rtl/crc32.c source + ntdllblog disassembly + nodejs commit]
- `RtlComputeCrc32` internally does `CrcValue = ~Initial`, runs `CrcValue = CrcTable[(CrcValue ^ *Data) & 0xff] ^ (CrcValue >> 8)`, returns `~CrcValue`. With `Initial=0` this is the standard `init=0xFFFFFFFF, xorout=0xFFFFFFFF` CRC-32 — identical to zlib. [VERIFIED: ntdllblog.wordpress.com]

### Exact signature
```c
DWORD __stdcall RtlComputeCrc32(DWORD dwInitial, const void *pData, INT iLen);
// dwInitial = 0 for a fresh CRC
```
[VERIFIED: WineHQ RtlComputeCrc32 + ntdllblog]

### AHK usage (add to `compression.ahk`)
```ahk
; Compute CRC32 of a UTF-8 string, matching Python zlib.crc32.
; Returns an unsigned 32-bit integer.
Crc32Str(str) {
    utf8Size := StrPut(str, "UTF-8") - 1   ; exclude null terminator
    if (utf8Size <= 0) {
        return 0
    }
    buf := Buffer(utf8Size, 0)
    StrPut(str, buf, "UTF-8")
    ; RtlComputeCrc32(DWORD initial, PVOID data, INT length) -> DWORD
    crc := DllCall("ntdll\RtlComputeCrc32", "UInt", 0, "Ptr", buf.Ptr, "Int", utf8Size, "UInt")
    return crc
}
```

### Python usage (add to `compression.py`)
```python
import zlib

def crc32_str(text: str) -> int:
    """CRC32 of a UTF-8 string, matching AHK ntdll!RtlComputeCrc32(0,...)."""
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF
```

### CRITICAL — do not trust, verify with a shared vector
Because this gates a **medico-legal** integrity check, the plan MUST include a verification task that proves byte-identity on a fixed vector on the real ntdll, not just on theory. Suggested canonical vector:
- input string `"123456789"` (UTF-8 bytes `31 32 33 34 35 36 37 38 39`) → **CRC-32 = `0xCBF43926`** (the standard CRC-32 check value). [VERIFIED: CRC-32 reference check value]
- A radiology-representative vector containing UTF-8 multibyte and a newline, e.g. `"Liver: normal.\nCRCé"`, computed once with `zlib.crc32` and asserted to equal the AHK `Crc32Str` output.

Both sides must hash the **same byte sequence**. Decide explicitly: CRC is computed over the **UTF-8 bytes of the `ct` field string** (the JSON value, after Base62/compression assembly, before JSON serialization). The plan must pin "CRC of what exactly" unambiguously — recommend: `crc = crc32(ct_string_utf8)` where `ct` is the exact string placed in the JSON, computed identically on both ends. [VERIFIED design spec line 156: "CRC32 of `ct`"]

---

## Baud / Tone Parameters

minimodem derives mark/space tones and filter bandwidth from baud automatically (minimodem.c lines 900–934). For the default and the wired targets:

| Baud | mark_f | space_f | band_width | Derivation (minimodem.c) | Suited to |
|------|--------|---------|-----------|--------------------------|-----------|
| 300  | 1270   | 1070    | 50        | `>=100` branch: mark=1270, space=mark-200, bw=50 | very noisy / acoustic |
| 1200 | 1200   | 2200    | 200       | `>=400` branch: mark=baud/2+600=1200, space=mark-(-(baud*5/6))=1200+1000=2200, bw=200 | **default; speaker/mic rig** |
| 4800 | 3000   | 7000    | 200       | mark=4800/2+600=3000, shift=-4000, space=7000, bw=200 | wired line-out→line-in |
| 9600 | 5400   | 13400   | 200       | mark=9600/2+600=5400, shift=-8000, space=13400, bw=200 | clean wired cable |

### Landmines
1. **High-baud tones exceed Nyquist or audible/cable range.** At 9600 baud the derived `space_f = 13400 Hz` — fine for 48 kHz sampling (Nyquist 24 kHz) but **above the passband of many cheap USB audio interfaces and most speaker/mic setups**. For 4800–9600 you will likely need to **override mark/space** to keep both tones in a usable band (e.g. force `bfsk_mark_f`/`bfsk_space_f` to a sane pair around 1500/2500 Hz with a wider shift, or expose them). The locked decision says "use minimodem defaults unless tuning demands otherwise" — tuning *will* demand it above ~4800. Flag to the user. [ASSUMED — confirm on the actual interface's frequency response]
2. **`fsk_plan_new` validates `b_mark`/`b_space < nbands`** (fsk.c:58) — if a tone is too high for the band plan it returns NULL. Surface this as an `init` error, don't crash.
3. **`band_width` is clamped to `<= bfsk_data_rate`** (minimodem.c:960) — at 1200 baud bw stays 200; at 300 baud bw drops to ≤300.
4. **Both ends MUST use the same baud AND the same tone derivation.** Since both ends run the *same* wrapper code, identical baud → identical tones automatically. Do not let one side override tones without the other.
5. **8-N-1 framing = 10 bits/byte** (1 start + 8 data + 1 stop). `bytes/sec ≈ baud/10`. Matches the design throughput table.

---

## Architecture Patterns

### System Architecture (data flow, send path)
```
[Radiologist draft] (AHK GUI)
        │
        ▼
  msgid + JSON dict {id, fn, ct, st, ci=0, cc=1}
        │
        ▼
  compression.ahk: LZNT1 compress ct → Base62 encode → set crc = Crc32Str(ct)
        │
        ▼
  chunking.ahk ChunkMessage(): single frame (ci=0, cc=1), Jxon_Dump → JSON string + "\n"
        │
        ▼ DllCall minimodem_simple_send(json, volume)
  minimodem_simple.dll:
     mm_tx_bytes() → leader | per-byte fsk_transmit_frame() | trailer
        │                                 (8-N-1 @ baud, mark/space tones)
        ▼ simpleaudio_write → WinMM waveOut ring
   ════════════ FSK audio over USB cable ════════════
        ▼ WinMM/ALSA waveIn ring → simpleaudio_read
  libminimodem_simple.so (Pi):
     RX thread: mm_rx_step() loop → fsk_find_frame → databits_decode_ascii8 → bytes
        │  accumulate until "\n" → push complete JSON line to queue
        ▼ ctypes minimodem_simple_receive(buf, size)
  chunking.py handle_received_chunk(): cc==1 → single message
        │
        ▼
  compression.py: verify crc32_str(ct) == msg["crc"]  ── mismatch → request full retransmit
        │ (ok)
        ▼ Base62 decode → LZNT1 decompress
  pipeline.py process_input()  (UNCHANGED)
```

### Recommended project structure
```
minimodem-wrapper/
├── CMakeLists.txt              # two targets: DLL (Win) / .so (Linux)
├── build_deps.sh               # MSYS2: install/build static fftw3f
├── build_wrapper.sh            # configure + make
├── collect_dlls.sh             # copy DLL to AHK/, verify zero deps with ntldd
├── minimodem_simple.h          # public API (mirrors ggwave_simple.h)
├── minimodem_simple.c          # API + RX thread + mm_build_config/mm_tx_bytes/mm_rx_step
├── simpleaudio-winmm.c         # NEW WinMM backend
└── (vendored, copied or referenced from ../minimodem/src/)
    fsk.c fsk.h simple-tone-generator.c databits_ascii.c databits.h baudot.h(stub?)
    simpleaudio.c simpleaudio_internal.h simpleaudio.h
    simpleaudio-alsa.c simpleaudio-pulse.c   # Linux only
```

### Pattern: mirror the ggwave_simple API exactly
| ggwave_simple.h | minimodem_simple.h | Change |
|-----------------|--------------------|--------|
| `_init(playback, capture, protocolId)` | `_init(playback, capture, baud)` | param renamed |
| `_get_playback_device_count()` | same | — |
| `_get_capture_device_count()` | same | — |
| `_get_playback_device_name(id)` | same | WinMM `WAVEOUTCAPS.szPname` |
| `_get_capture_device_name(id)` | same | WinMM `WAVEINCAPS.szPname` |
| `_send(message, volume)` | same | volume → tx_amplitude scale |
| `_is_transmitting()` | same | atomic flag |
| `_process()` | same | becomes ~no-op (RX thread pumps) |
| `_receive(buffer, size)` | same | drains newline-framed queue |
| `_set_protocol(id)` | `_set_baud(int)` | rename; rebuilds fsk_plan |
| `_cleanup()` | same | join RX thread, close streams |
| `_get_error()` | same | — |

> Keep the `__declspec(dllexport/dllimport)` macro pattern from `ggwave_simple.h` (lines 10–14) and `extern "C"` if compiled as C++ — but since this is C, just export with `__declspec(dllexport)` under a `MINIMODEM_SIMPLE_BUILD` define. MinGW exports all symbols by default; to get a clean export table either use `__declspec(dllexport)` or a `.def` file.

### Anti-Patterns to Avoid
- **Calling waveOut/waveIn from the callback** — deadlock. Use events.
- **A function-static `carrier_band`** (as minimodem.c:1180 has) in the library — breaks if two instances ever exist and is not thread-clean. Promote to ctx.
- **Re-deriving tones differently per side** — both must run identical derivation.
- **Trusting CRC equivalence without a test vector** — medico-legal; prove it.
- **Spin-polling `WHDR_DONE` with no sleep** — starves the audio thread; use `CALLBACK_EVENT`.
- **Shipping MinGW runtime DLLs** — defeats the "single self-contained binary" goal; static-link them.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FSK demodulation | Custom Goertzel/FFT decoder | Vendored `fsk.c` + `fftw3f` | Confidence scoring, frame tracking, overscan are subtle and battle-tested |
| FSK modulation | Custom tone synthesis | `simple-tone-generator.c` | Handles phase continuity (`sa_tone_cphase`), LUT, S16/float |
| 8-N-1 framing | Hand-rolled bit packing | `databits_ascii.c` + `fsk_transmit_frame` | Start/stop/prev-stop bit handling is in the existing code |
| CRC32 | Custom CRC table | `ntdll!RtlComputeCrc32` (AHK) / `zlib.crc32` (Py) | Both are standard CRC-32; identical and free |
| LZNT1 / Base62 | Anything new | Existing `compression.ahk` / `compression.py` | Already working, byte-compatible across sides |
| Audio device I/O | Custom WASAPI/COM | WinMM (Win) / ALSA-Pulse (Linux, existing) | WinMM is locked, zero-install; Linux backends already exist |
| Thread-safe queue | Lock-free ring | Single mutex + byte buffer | Throughput is bytes/sec; a mutex is plenty |

**Key insight:** The DSP, framing, and compression are *all* already written and proven. The genuinely new code is exactly three things: (1) the WinMM backend, (2) the `main()` → context-struct refactor, (3) the RX thread + queue + newline framing glue. Everything else is wiring and a one-field (`crc`) protocol addition.

---

## Runtime State Inventory

> This is a transport swap with build-artifact and config implications. Categories assessed:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastore keys reference "ggwave" as a value/key. The JSON schema (`id/fn/ct/st/ci/cc`) is transport-agnostic. | None |
| Live service config | None in git. `--protocol`/`-p` on the Pi and protocol id in AHK are config, replaced by `--baud`/`BAUD_RATE`. No external service holds transport config. | Code/CLI change only (covered by plan) |
| OS-registered state | If the Pi runs `backend.py` under systemd/pm2/cron with `-p 1`, that unit's args reference the old `--protocol` flag and will error once it's removed. | **Check for and update any service unit / launch script invoking `backend.py -p N`** — grep the Pi for the invocation. Not in this repo; flag for the user. |
| Secrets/env vars | None — no env vars reference ggwave. | None |
| Build artifacts | `ggwave-wrapper/build/`, `AHK/ggwave_simple.dll` (+ `SDL2.dll`), `quiet-wrapper/build/` and `_deps/`. The old `ggwave_simple.dll` + `SDL2.dll` in `AHK/` become stale once AHK loads `minimodem_simple.dll`. Python `import ggwave` (backend.py:16, chunking.py:9) must be removed. | New `minimodem-wrapper/build/` artifacts; copy `minimodem_simple.dll` to `AHK/`; **remove/retire** `SDL2.dll` and old `ggwave_simple.dll` from `AHK/` after cutover (keep until verified). Remove `import ggwave` + `import pyaudio` (transport path) from Python. |

**Explicitly nothing found:** Stored data, secrets/env. OS-registered state is *outside this repo* (Pi service manager) — flagged, cannot verify from here.

---

## Common Pitfalls

### Pitfall 1: RX loop's loop-carried state lost between thread iterations
**What goes wrong:** Refactoring `mm_rx_step` to return after each pass but forgetting to persist `samplebuf`, `samples_nvalid`, `advance`, `carrier`, `track_amplitude`, `peak_confidence` in the ctx → the demodulator resets every call and never acquires carrier.
**Why:** In the original these are `main()` locals living across `while(1)` iterations.
**How to avoid:** Promote every loop-carried local (enumerated in § Context struct) into the ctx. Initialize once in `mm_build_config`.
**Warning signs:** Loopback test decodes 0 bytes or only sporadic single chars.

### Pitfall 2: WinMM capture buffer starvation → corrupt FSK
**What goes wrong:** Not re-adding `waveIn` buffers fast enough; dropped samples desync the bit clock.
**Why:** `read` copies out but forgets to `waveInAddBuffer` immediately, or N too small.
**How to avoid:** N≥3 (start 4), re-add inside `read` right after copy. Validate at 1200 baud first.
**Warning signs:** `#short+` style underrun symptoms; intermittent decode; degrades as message length grows.

### Pitfall 3: TX bleeds into RX (half-duplex collision)
**What goes wrong:** On a speaker/mic rig, the outgoing carrier is picked up by `waveIn` and the demodulator chokes / queues garbage.
**How to avoid:** `is_transmitting` atomic; RX thread reads-but-discards while transmitting (keeps buffer drained without desync).
**Warning signs:** Garbage frames queued exactly during sends; works wired, fails on speaker/mic.

### Pitfall 4: CRC computed over different byte sequences on the two sides
**What goes wrong:** AHK CRCs the UTF-16 string or the JSON; Python CRCs the raw bytes → mismatch → every message "fails" and retransmits forever.
**How to avoid:** Pin exactly: `crc = CRC32(UTF-8 bytes of the ct string)`. Verify with a shared vector including multibyte UTF-8.
**Warning signs:** 100% CRC-mismatch retransmit loop; works only for pure-ASCII short messages.

### Pitfall 5: DLL ships with hidden MinGW/FFTW deps
**What goes wrong:** `minimodem_simple.dll` needs `libgcc_s_seh-1.dll`/`libwinpthread-1.dll`/`libfftw3f-3.dll` at runtime; AHK fails to load it on a clean machine.
**How to avoid:** `-static -static-libgcc -static-libstdc++` + static `libfftw3f.a`; verify with `ntldd -R` showing only system DLLs.
**Warning signs:** `LoadLibrary` returns 0; works on dev box (has MinGW on PATH), fails elsewhere.

### Pitfall 6: High baud tones outside the device's frequency response
**What goes wrong:** At 9600 baud, space tone ~13.4 kHz is attenuated/cut by the interface → no carrier.
**How to avoid:** Override mark/space to a usable band for high baud; test the interface's response.
**Warning signs:** 1200 works, 4800+ never acquires carrier.

### Pitfall 7: `_process()`/`_receive()` race with the RX thread
**What goes wrong:** AHK drains the queue while the RX thread writes it → corruption/crash.
**How to avoid:** One mutex around all queue access on both producer (RX thread) and consumer (`_receive`).
**Warning signs:** Rare crashes, garbled received lines under load.

---

## Code Examples

### TX byte loop (extracted from fsk_transmit_stdin)
```c
// Source: derived from minimodem/src/minimodem.c lines 207–249, 81–112
int mm_tx_bytes(minimodem_ctx *ctx, const unsigned char *buf, size_t len) {
    simpleaudio_tone_reset();
    // leader (mark)
    for (int j = 0; j < ctx->tx_leader_bits_len; j++)
        simpleaudio_tone(ctx->sa_out, ctx->bfsk_mark_f, ctx->tx_bit_nsamples);
    // data bytes, 8-N-1 via fsk_transmit_frame
    for (size_t i = 0; i < len; i++) {
        unsigned int bits[2];
        unsigned int nwords = databits_encode_ascii8(bits, (char)buf[i]);
        for (unsigned int w = 0; w < nwords; w++)
            mm_fsk_transmit_frame(ctx->sa_out, bits[w], ctx->bfsk_n_data_bits,
                ctx->tx_bit_nsamples, ctx->bfsk_mark_f, ctx->bfsk_space_f,
                ctx->bfsk_nstartbits, ctx->bfsk_nstopbits, /*invert*/0, /*msb*/0);
    }
    // trailer (mark)
    for (int j = 0; j < ctx->tx_trailer_bits_len; j++)
        simpleaudio_tone(ctx->sa_out, ctx->bfsk_mark_f, ctx->tx_bit_nsamples);
    return 0;
}
```

### WinMM blocking read skeleton (one header, conceptual)
```c
// Source: pattern from learn.microsoft.com waveInAddBuffer/CALLBACK_EVENT +
//         minimodem simpleaudio synchronous contract (simpleaudio-alsa.c)
static ssize_t sa_winmm_read(simpleaudio *sa, void *buf, size_t nframes) {
    winmm_state *w = sa->backend_handle;
    size_t got = 0;
    char *out = buf;
    while (got < nframes) {
        WAVEHDR *h = &w->in_hdr[w->in_head];
        while (!(h->dwFlags & WHDR_DONE))
            WaitForSingleObject(w->in_event, INFINITE);
        size_t avail = h->dwBytesRecorded / sa->backend_framesize;
        size_t take = min(avail, nframes - got);
        memcpy(out + got*sa->backend_framesize, h->lpData, take*sa->backend_framesize);
        got += take;
        // recycle this header immediately
        h->dwFlags &= ~WHDR_DONE;
        waveInAddBuffer(w->hwi, h, sizeof(*h));
        w->in_head = (w->in_head + 1) % w->in_n;
    }
    return (ssize_t)got;
}
```
> This skeleton assumes each header is consumed whole; if `take < avail` you must track a partial offset into the header. Simpler: size each capture header to exactly the read granularity (`samplebuf_size/2` frames) so reads consume whole headers. [ASSUMED — confirm during implementation; partial-header handling may be needed if read sizes vary]

### AHK single-frame send with CRC (chunking.ahk adaptation)
```ahk
; v1: always single frame, attach crc
single := Map("id", msgID, "fn", fn, "ct", ct, "st", st, "ci", 0, "cc", 1)
single["crc"] := Crc32Str(ct)
DllCall("minimodem_simple\minimodem_simple_send", "AStr", Jxon_Dump(single) . "`n", "Int", BAUD_VOLUME, "Int")
```

---

## State of the Art

| Old Approach (ggwave) | New Approach (minimodem) | Impact |
|-----------------------|--------------------------|--------|
| ggwave (MIT) + SDL2 audio | minimodem FSK (GPLv3) + WinMM/ALSA | License changes to GPLv3 (internal-use accepted); one fewer redistributable (no SDL2.dll if static) |
| Protocol ID (0–5) | Baud rate (configurable int) | Tunable throughput; both ends must match |
| ~140-byte payload ceiling → mandatory chunking | Single-frame, no size cap (v1) | Lower latency for reports; chunking dormant for v2 |
| SDL queue pumped by `_process()` | Background RX thread + queue | `_process()` becomes near no-op |
| No message-level integrity | CRC32 on `ct` | Detects corruption; full-retransmit on mismatch |
| Python `import ggwave` + PyAudio | ctypes → `libminimodem_simple.so` | Symmetric C wrapper both ends; PyAudio leaves the transport path |

**Deprecated/retired after cutover:**
- `AHK/ggwave_simple.dll`, `AHK/SDL2.dll` — retire once minimodem verified.
- `import ggwave`, `import pyaudio` in the transport path (`backend.py`, `chunking.py`, `audio.py`). Device enumeration moves to the wrapper's device-count/name calls.
- `_set_protocol` / `-p` / `protocolId` — replaced by `_set_baud` / `--baud` / `BAUD_RATE`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `mingw-w64-x86_64-fftw` pacman package ships a static `libfftw3f.a` | FFTW Static Linking | If only `.dll.a` ships, must build fftw3f from source (`--enable-single --enable-static`); adds a build step. Low risk — well-documented fallback. |
| A2 | High baud (4800–9600) needs mark/space override due to device frequency response | Baud/Tone Params | If wrong, default tones work and no override needed (best case). If right and ignored, high baud silently fails. Medium risk — affects v1 "tunable baud" goal. |
| A3 | Half-duplex TX-pause-RX is needed on speaker/mic but maybe not wired | Threading Model | If unneeded, harmless (read-and-discard). If needed and absent, garbage frames during send. Low risk — read-and-discard is safe default. |
| A4 | Target USB audio interface supports 48k mono `WAVE_FORMAT_IEEE_FLOAT` | WinMM Backend | If only stereo/S16 offered, need downmix/convert path → more code + framesize math. Medium risk. |
| A5 | CRC computed over UTF-8 bytes of `ct` is identical AHK↔Python | CRC32 | Theory says yes; MUST verify with shared vector. If wrong (e.g. UTF-16 vs UTF-8), 100% retransmit loop. Mitigated by mandatory test vector. |
| A6 | Capture headers can be sized to read granularity so reads consume whole headers | Code Examples | If read sizes vary, need partial-header offset tracking. Low risk — implementation detail. |
| A7 | Pi service manager (if any) invoking `backend.py -p N` exists outside this repo | Runtime State Inventory | If a systemd/cron unit uses `-p`, it breaks when flag removed. Cannot verify from repo; user must check the Pi. |

**Nothing in this table is a locked decision** — these are research-derived assumptions the planner/discuss-phase should confirm (especially A2, A4, A5).

---

## Open Questions

1. **Mono support on the actual USB interface (A4)**
   - Known: minimodem requires mono; `simpleaudio.c` aborts on channel mismatch.
   - Unclear: whether the specific class-compliant USB interface offers 48k mono.
   - Recommendation: probe with `waveInOpen` for mono first; add a stereo+downmix fallback only if `WAVERR_BADFORMAT`.

2. **High-baud tone band (A2)**
   - Known: derived tones at 9600 reach ~13.4 kHz.
   - Unclear: device passband at those frequencies.
   - Recommendation: validate baud sweep on real hardware; if high baud fails, expose mark/space override (small addition; design already allows "optionally exposed later").

3. **Whether `_process()` should do anything**
   - Known: RX thread pumps audio; `_process()` was the SDL pump.
   - Recommendation: keep it as a no-op returning 0 (preserves AHK loop & API), or use it for light housekeeping (timeout sweep). Don't put blocking work in it.

4. **TX volume → amplitude mapping**
   - Known: ggwave `volume` was 1–100; minimodem `tx_amplitude` is a float (1.0 default), set via `simpleaudio_tone_init(len, amplitude)`.
   - Recommendation: map `volume/100.0` → `tx_amplitude`, call `simpleaudio_tone_init(4096, amplitude)` at send time (or on volume change). Matches existing AHK volume=50 calls.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| MSYS2 + mingw-w64 toolchain | Windows DLL build | ✓ (proven by quiet-wrapper) | current | none — required |
| `fftw3f` static | `fsk.c` FFT (Windows) | likely via pacman | 3.3.x | build from source `--enable-single --enable-static` |
| `libfftw3-dev` | `fsk.c` FFT (Pi) | apt | 3.3.x | build from source |
| `libasound2-dev` (ALSA) | Linux audio backend | apt | — | PulseAudio dev libs |
| CMake ≥3.10 | build | ✓ | — | none |
| `ntldd` / Dependencies.exe | verify zero deps | MSYS2 ships ntldd | — | Dependency Walker |
| Virtual audio cable | DLL loopback test | not confirmed | — | VB-CABLE / real cable loopback |
| Python `ctypes` | Pi binding | ✓ stdlib | 3.9+ | none |

**Missing dependencies with no fallback:** none blocking — toolchain is proven.
**Missing with fallback:** virtual audio cable for loopback (use VB-CABLE or a physical loopback); static fftw3f (build from source if pacman lacks `.a`).

> These probes describe the Windows dev machine and the Pi target. They could not be run live here (this is the research agent on the Windows box without MSYS2 invoked); the planner should add a Wave 0 task to confirm `libfftw3f.a` presence and mono-48k device support before implementation.

---

## Validation Architecture

> `nyquist_validation` config not located in `.planning/config.json` (file absent at research time) — treated as enabled. Project convention is **manual testing** (no automated harness), so validation is layered manual + a small added automated CRC/loopback check where feasible.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None automated for transport (manual per CLAUDE.md). Add a small C loopback test + a Python/AHK CRC vector assertion. |
| Config file | none |
| Quick run command | C loopback: run a `loopback_test` exe that TX→RX in-process over a virtual cable, assert byte-exact |
| Full suite command | Cross-machine AHK↔Pi round trip over the USB audio cable |

### Phase Requirements → Test Map
| Req | Behavior | Test Type | Command / Method | Exists? |
|-----|----------|-----------|------------------|---------|
| CRC-01 | AHK CRC32 == Python CRC32 on shared vectors | unit | Compute `Crc32Str("123456789")` in AHK == `0xCBF43926`; assert `zlib.crc32(b"123456789")==0xCBF43926`; plus a UTF-8 multibyte vector | ❌ Wave 0 |
| TX-01/RX-01 | byte-exact round trip through DLL | integration (loopback) | `loopback_test`: feed N random byte buffers TX→virtual cable→RX, assert output==input across baud {1200,4800,9600} | ❌ Wave 0 |
| WINMM-01 | WinMM read/write block correctly, no underrun | integration | sustained loopback of a ~500-byte report at 1200 baud; assert no dropped frames / no decode gaps | ❌ Wave 0 |
| FFTW-01 | DLL has zero non-system deps | smoke | `ntldd -R minimodem_simple.dll` → only Windows system DLLs | ❌ Wave 0 |
| API-01 | DLL loads in AHK and all 12 exports resolve | smoke | AHK `LoadLibrary` + a `DllCall` per export | ❌ Wave 0 |
| CFG-01 | baud change applies without recompile, both ends matched | integration | baud sweep test; confirm mismatch → no decode | manual |
| Integrity | corrupted message → CRC mismatch → full retransmit, never surfaces partial | integration | induce bit corruption; assert receiver discards + requests retransmit | manual |

### Sampling rate
- **Per task commit:** CRC vector unit test (instant) + DLL `ntldd` dep check after any build change.
- **Per wave merge:** in-process / virtual-cable loopback byte-exact test at 1200 baud.
- **Phase gate:** cross-machine AHK↔Pi round trip of a full ~500-byte report green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `minimodem-wrapper/test/crc_vector_test` — proves CRC32 byte-identity (AHK + Python both assert against `0xCBF43926` and a UTF-8 vector). **This must pass before any CRC integration.**
- [ ] `minimodem-wrapper/test/loopback_test.c` — byte-exact TX→RX over a virtual audio cable across baud rates. **This is the gate before touching AHK/Python** (per design Risks).
- [ ] `ntldd`/Dependencies.exe dependency check script (extend `collect_dlls.sh` to fail if non-system deps remain).
- [ ] Confirm `libfftw3f.a` static lib present (or document source-build step).
- [ ] Confirm target USB interface supports 48k mono.

---

## Security Domain

> `security_enforcement` not located in config (absent → treated enabled). This is a local IPC transport with no network/auth surface; most ASVS categories N/A. Relevant concerns are input-validation (untrusted decoded bytes) and integrity.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth; physically wired/acoustic local link |
| V3 Session Management | no | Stateless message exchange |
| V4 Access Control | no | Single-user local tool |
| V5 Input Validation | **yes** | Decoded FSK bytes are untrusted: bound-check `_receive` buffer (`bufferSize`), guard `databits_decode` output into a fixed `dataoutbuf[4096]` (minimodem.c:1432 — keep the bound), validate JSON via `Jxon_Load`/`json.loads` in `try/catch` (already done), enforce a max message length before reassembly |
| V6 Cryptography | partial | CRC32 is integrity (not security) — it detects accidental corruption, NOT tampering. Do not present it as authentication. Adequate for this threat model (no adversary on a private cable). |

### Known threat patterns for this stack (C audio wrapper + FFI)
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Buffer overflow on decoded RX bytes / `_receive` copy | Tampering/DoS | Bounds-check every copy; the wrapper must never write past `bufferSize`; cap accumulated line length before `\n` |
| Unbounded queue growth (RX faster than drain, or carrier noise) | DoS | Cap the decoded-byte queue size; drop oldest / reset on overflow |
| Malformed JSON from noise decoded as bytes | Tampering | Already guarded by `try/catch as e` (AHK) and `except` (Python) around JSON parse; CRC mismatch → discard |
| ctypes signature mismatch (wrong argtypes) → memory corruption | Tampering | Set `restype`/`argtypes` explicitly on every ctypes function in `lib/minimodem.py`; pass a sized `create_string_buffer` to `_receive` |
| Integer overflow in framesize/nframes math | DoS | Use `size_t`; validate `nframes`/`bufferSize > 0` (minimodem already asserts) |

---

## Sources

### Primary (HIGH confidence)
- In-repo source (read directly this session): `minimodem/src/minimodem.c`, `fsk.c/.h`, `simple-tone-generator.c`, `databits_ascii.c/databits.h`, `simpleaudio.c/.h/_internal.h`, `simpleaudio-pulse.c`, `simpleaudio-alsa.c`; `ggwave-wrapper/ggwave_simple.{h,cpp,}`, `CMakeLists.txt`, `build.bat`; `quiet-wrapper/{CMakeLists.txt,build_deps.sh,build_wrapper.sh,collect_dlls.sh}`; AHK `chunking.ahk`/`compression.ahk`/`config.ahk`/`dll_manager.ahk`; Python `chunking.py`/`compression.py`/`audio.py`/`backend.py`; design spec + CONTEXT.md.
- ReactOS `rtl/crc32.c` — confirms `RtlComputeCrc32` polynomial `0xEDB88320` (https://doxygen.reactos.org/d5/dbf/rtl_2crc32_8c_source.html)
- ntdll blog disassembly — `RtlComputeCrc32` signature + `~init`/`~result` convention (https://ntdllblog.wordpress.com/2016/10/14/rtlcomputecrc32/)
- WineHQ `RtlComputeCrc32` API (https://source.winehq.org/WineAPI/RtlComputeCrc32.html)
- FFTW official MinGW64 build script `--enable-single` (https://github.com/FFTW/fftw3/blob/master/support/BUILD-MINGW64.sh); Windows install notes (http://www.fftw.org/install/windows.html); MSVC compat PR #161 (https://github.com/FFTW/fftw3/pull/161)
- Microsoft `waveOutWrite` / WAVEHDR docs (https://learn.microsoft.com/en-us/previous-versions/ms713764(v=vs.85))

### Secondary (MEDIUM confidence)
- WinMM callback deadlock guidance — dedicated thread, not callback, for waveOutWrite/waveInAddBuffer (experts-exchange WaveInProc/WaveOutProc thread)
- techmind.org wave I/O tutorial (http://www.techmind.org/wave/) — WAVEHDR recycling patterns
- nodejs commit referencing zlib CRC32 polynomial `0xEDB88320` (https://github.com/nodejs/node/commit/6b4dac3eb5)

### Tertiary (LOW confidence — flagged for validation)
- pacman `mingw-w64-x86_64-fftw` static `.a` presence (A1) — verify on disk.
- USB interface 48k mono float support (A4) — verify on hardware.

---

## Metadata

**Confidence breakdown:**
- minimodem.c decomposition: HIGH — read the full source; extraction map is line-referenced.
- WinMM backend: MEDIUM — pattern is well-documented; exact ring sizing must be tuned empirically (locked as Claude's discretion).
- FFTW static linking: HIGH — toolchain proven by quiet-wrapper; FFTW docs confirm `--enable-single`/static.
- Threading model: HIGH — direct analog of ggwave wrapper's pump, validated against AHK's existing poll.
- CRC32: HIGH on theory (polynomial + convention verified across 3 sources); the byte-identity is gated behind a mandatory test vector, not assumed.
- Baud/tone params: HIGH derivation (read from minimodem.c); MEDIUM on real-hardware high-baud viability (A2).

**Research date:** 2026-06-17
**Valid until:** 2026-07-17 (stable domain — C source pinned in-repo; FFTW/WinMM are decades-stable). Re-verify pacman package contents (A1) at build time.

## RESEARCH COMPLETE
