# Design: Replace ggwave with minimodem (both sides)

**Date:** 2026-06-17
**Status:** Approved (brainstorming) — pending GSD plan-phase
**Author:** covie154 + Claude

## Goal

Replace the data-over-sound transport from **ggwave** to **minimodem FSK** on
**both** the Windows AHK frontend and the Raspberry Pi Python backend, while
preserving every layer above transport (GUI, message protocol, compression,
chunking). The two ends must continue to interoperate over the same audio link.

## Motivation

Evaluation of modem alternatives to ggwave (see also the prototype
`quiet-wrapper/`). minimodem is a simple, well-understood FSK modem. This design
makes it a drop-in transport by wrapping it behind the *same* simple API the
existing `ggwave_simple` DLL already exposes, so the substantial application code
above transport is reused almost verbatim.

## Key decisions (settled during brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Both sides → minimodem | minimodem and ggwave are incompatible protocols; swapping one side alone breaks the link. |
| Windows audio API | **WinMM** (`waveOut*`/`waveIn*`) | Ships with every Windows, statically linkable → single self-contained, copy-pasteable binary, no install. Throughput is set by baud, not the audio API. |
| Packaging | **`minimodem_simple.dll`** mirroring `ggwave_simple.dll` API | AHK keeps its `DllCall` model; `chunking.ahk`, `compression.ahk`, `gui.ahk`, `msgid.ahk` reused nearly unchanged. |
| Pi side | **Shared wrapper compiled as `.so` + `ctypes`** | One wrapper codebase, symmetric API on both ends; replaces the ggwave Python binding. |
| Integrity | **Single framed message + CRC32 (no chunking, v1)** | Latency-first: one transmission avoids the repeated per-chunk preamble (~0.5–1 s each) + inter-chunk delays. Message-level CRC32 detects corruption; a failed CRC triggers a whole-message resend. Chunking (~200-word chunks) deferred to v2. |
| FFTW | **Static-link `fftw3f` (v1)** | `fsk.c` needs single-precision FFT; static link keeps the DLL self-contained. Goertzel rewrite deferred to v2. |
| License | **GPLv3 accepted** for internal/research use | minimodem is GPLv3 (ggwave was MIT); a DLL built from its source is GPLv3 and loads into the AHK process. Noted before any distribution. |
| Baud rate | **Configurable end-to-end**, default **1200** | 1200 suits the current speaker/mic rig; raise to 4800–9600 on the wired link. User is unsure of the optimum, so it must be tunable without recompiling. |

## Throughput reference (informed the integrity decision)

A ~100-word report ≈ 600 chars raw → after LZNT1 + Base62 ≈ **~500 bytes on the
wire**. minimodem 8-N-1 framing = 10 bits/byte, so bytes/sec ≈ baud ÷ 10, plus a
fixed ~0.5–1 s carrier/preamble per transmission.

| Baud | Bytes/sec | ~500-byte report | Suited to |
|------|-----------|------------------|-----------|
| 300  | 30  | ~17 s | very noisy / acoustic |
| 1200 | 120 | ~4 s  | speaker–mic (current test rig) |
| 4800 | 480 | ~1 s  | wired line-out → line-in |
| 9600 | 960 | ~0.5 s| clean wired cable |

Because transfers are seconds-scale **and latency matters**, v1 sends each report
as a **single framed transmission** (no chunking) with a message-level CRC32; a
failed CRC triggers a full resend. This avoids the per-chunk preamble (~0.5–1 s
each) and inter-chunk delays that multiple chunks would add. Chunking returns in
v2 with large (~200-word ≈ ~1 KB) chunks once payloads grow long enough to
warrant it.

## Architecture

```
AHK frontend (Windows)                       Python backend (Raspberry Pi)
┌───────────────────────────┐                ┌───────────────────────────┐
│ gui.ahk / msgid.ahk        │                │ pipeline.py               │
│ chunking.ahk (+CRC32)      │                │ chunking.py (+CRC32)      │
│ compression.ahk (LZNT1,    │                │ compression.py (LZNT1,    │
│   Base62, CRC32 helper)    │                │   Base62, CRC32)          │
│ dll_manager.ahk ──DllCall─┐│                │ lib/minimodem.py (ctypes) │
└───────────────────────────┘│                └───────────┬───────────────┘
                             ▼│                            ▼
        minimodem_simple.dll  │   ===== FSK audio =====   libminimodem_simple.so
        (WinMM backend)       │       (USB audio link)    (ALSA/Pulse backend)
                              └────────────────────────────┘
```

Identical C wrapper source compiled per-platform; only the `simpleaudio` backend
differs (WinMM on Windows, existing ALSA/Pulse on Linux).

## Components

### 1. `minimodem-wrapper/` (new, CMake — mirrors `ggwave-wrapper/`)

**Reused minimodem core (vendored from `minimodem/src/`):**
- `fsk.c` / `fsk.h` — FSK demodulation (needs `fftw3f`).
- `simple-tone-generator.c` — FSK modulation.
- `databits_ascii.c` — 8-N-1 byte framing.
- `simpleaudio.c` + `simpleaudio_internal.h` — backend dispatch.
- Linux: existing `simpleaudio-alsa.c` / `simpleaudio-pulse.c`.

**New: `simpleaudio-winmm.c`**
- Implements the 4-function `simpleaudio_backend` struct
  (`open_stream`/`read`/`write`/`close`) over `waveOutOpen`/`waveOutWrite` and
  `waveInOpen`/`waveInAddBuffer`, using a small ring of `WAVEHDR` buffers to make
  `read`/`write` block cleanly (matching minimodem's synchronous model).
- Device enumeration: `waveOutGetNumDevs`/`waveOutGetDevCaps` and
  `waveInGetNumDevs`/`waveInGetDevCaps`; `backend_device` selects by integer index.
- Registers `SA_BACKEND_WINAUDIO` in the `sa_backend_t` enum and `simpleaudio.c`
  dispatch (guarded by a `USE_WINAUDIO` define).

**New: `minimodem_simple.c` / `minimodem_simple.h`**
- Refactors minimodem.c's TX and RX loops (currently embedded in `main()`) into
  reusable functions.
- Runs a **background RX thread**: continuous `waveIn` → `fsk_find_frame` →
  decoded bytes pushed to a thread-safe queue. This preserves AHK's existing
  10 ms `process()` poll + `receive()` drain model with no change to AHK timing.
- `send()` modulates the message to `waveOut` (volume-scaled).

**API (mirrors `ggwave_simple.h` exactly so AHK/ctypes change minimally):**
```c
int  minimodem_simple_init(int playbackDeviceId, int captureDeviceId, int baud);
int  minimodem_simple_get_playback_device_count(void);
int  minimodem_simple_get_capture_device_count(void);
const char* minimodem_simple_get_playback_device_name(int deviceId);
const char* minimodem_simple_get_capture_device_name(int deviceId);
int  minimodem_simple_send(const char* message, int volume);
int  minimodem_simple_is_transmitting(void);
int  minimodem_simple_process(void);
int  minimodem_simple_receive(char* buffer, int bufferSize);
int  minimodem_simple_set_baud(int baud);   /* replaces set_protocol */
void minimodem_simple_cleanup(void);
const char* minimodem_simple_get_error(void);
```
Note: the `protocolId` parameter of the old API becomes **`baud`**. Tone
frequencies default to minimodem's defaults; optionally exposed later if tuning
demands it. **Baud is a link parameter — both ends must use the same value.**

**Build:** CMake targeting `minimodem_simple.dll` (Windows, WinMM + static
`fftw3f`) and `libminimodem_simple.so` (Linux, ALSA/Pulse + `fftw3f`). Build
scripts mirror `ggwave-wrapper/` (`build_wrapper.sh`, `collect_dlls.sh`). The
Windows DLL links `winmm.lib`; goal is zero redistributable DLLs beyond the one
wrapper file.

### 2. AHK frontend changes
- `dll_manager.ahk` — load `minimodem_simple.dll`; rename load/unload/error
  helpers (or keep names, repoint path).
- `main_dll.ahk` — `init` call passes `BAUD_RATE` instead of protocol id.
- `config.ahk` — add `BAUD_RATE` global (default 1200), kept alongside existing
  ALL_CAPS config; this is the single tuning knob.
- `chunking.ahk` — v1: send each message as a **single frame** (`ci=0`, `cc=1`),
  no splitting; add a message-level `crc` field; on receive, validate CRC and
  route a mismatch through the existing retransmit path (full-message resend).
  The split/reassemble code paths are retained but dormant, ready for v2 chunking.
- `compression.ahk` — add CRC32 helper via `ntdll!RtlComputeCrc32`.
- `gui.ahk`, `msgid.ahk` — unchanged.

### 3. Python backend changes
- New `lib/minimodem.py` — `ctypes` binding to `libminimodem_simple.so`, same API
  surface as the wrapper; replaces the ggwave binding in the transport path.
- `lib/audio.py` — device enumeration via the wrapper's device-count/name calls
  (PyAudio no longer required for the transport path).
- `lib/chunking.py` — v1: single-frame send (`ci=0`, `cc=1`); add `crc` (CRC32 via
  `zlib.crc32`); validate on receive; honor full-message retransmit requests.
  Split/reassemble retained but dormant for v2.
- `backend.py` — transport init swaps ggwave → minimodem; `--baud` CLI argument
  (default 1200) plus existing `--volume`. `process_input()` pipeline untouched.

### 4. Message protocol (additive)
- Keep LZNT1 compression, Base62 encoding (keeps payload newline-safe), and the
  `id`/`fn`/`ct`/`st`/`ci`/`cc` JSON schema (`ci=0`, `cc=1` in v1).
- New field **`crc`** (CRC32 of `ct`) on every message.
- Framing: newline-delimited JSON messages over the FSK byte stream.
- v1 sends the whole compressed report in a single frame — no size cap (ggwave's
  ~140-byte ceiling is gone). v2 reintroduces chunking with large (~200-word ≈
  ~1 KB) chunks for very long payloads.

## Data flow (send path, unchanged above transport)
1. User draft → `msgid` + JSON dict.
2. LZNT1 compress whole payload → Base62 → wrap as a single frame
   (`ci=0`, `cc=1`) + **`crc`** (CRC32 of `ct`).
3. Frame JSON → `minimodem_simple_send` → FSK audio.
4. Receiver RX thread decodes bytes → newline-framed JSON → `receive()` drains →
   CRC check → Base62 decode → LZNT1 decompress → deliver. CRC mismatch or
   timeout → full-message retransmit request (existing path).

## Error handling
- **CRC mismatch:** discard the frame, request a full retransmit by `id` (existing
  mechanism); timeout → re-request; never surface a partial/corrupt report.
- **Audio device open failure:** wrapper returns negative + `get_error()` string;
  AHK shows `MsgBox`, Python logs and exits per existing patterns.
- **Carrier loss / decode noise:** `fsk_find_frame` confidence already filters
  low-confidence frames; undecodable bytes simply don't complete a chunk →
  retransmit.

## Testing (manual, per project convention)
1. **DLL loopback** — wrapper TX → wrapper RX on one machine via a virtual audio
   cable; verify byte-exact round trip across baud rates.
2. **Cross-machine round trip** — AHK ↔ Pi over the USB audio cable; calibrate
   volume per direction first.
3. **Report-length payloads** — full reports in a single frame; induce corruption
   to confirm message-level CRC detection + full retransmit.
4. **Baud sweep** — confirm `BAUD_RATE`/`--baud` changes apply without recompile
   and both ends must match.

## Out of scope / v2
- **Chunking for long payloads** — reintroduce `id/ci/cc` splitting with large
  (~200-word ≈ ~1 KB) chunks once reports exceed a comfortable single-frame size;
  lets the receiver re-request only the corrupted chunk instead of the whole
  message. Split/reassemble code stays in place (dormant) from v1 to ease this.
- **Reed-Solomon-per-chunk FEC** (e.g. RS(255,223)) — corrects burst errors
  without a round-trip; add when measured chunk-loss on the acoustic rig makes
  retransmit round-trips dominate latency. RS code can be lifted from ggwave or
  quiet.
- **Fountain codes (LT/Raptor)** across chunks — eliminates the retransmit
  handshake; more complex.
- **Goertzel 2-tone detection** to drop the FFTW dependency entirely.
- Auto baud negotiation between ends.

## Risks
- Refactoring minimodem.c's `main()` TX/RX loops into a library is the bulk of
  the work and the main correctness risk; mitigated by the loopback test first.
- WinMM blocking semantics via `WAVEHDR` rings need care to avoid underruns/
  glitches that corrupt FSK; validate at low baud first.
- Static-linking `fftw3f` on the Windows toolchain (MSVC/MinGW) must produce a
  dependency-free DLL — verify with a dependency walker.
