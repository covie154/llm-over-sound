# Phase 7: Replace ggwave with minimodem (both sides) - Context

**Gathered:** 2026-06-17
**Status:** Ready for planning
**Source:** Design spec (brainstorming) — docs/superpowers/specs/2026-06-17-minimodem-transport-design.md

<domain>
## Phase Boundary

Replace the data-over-sound transport from **ggwave** to **minimodem FSK** on both
the Windows AHK frontend and the Raspberry Pi Python backend, preserving every layer
above transport (GUI, message protocol, compression, Base62, message IDs). The two
ends must continue to interoperate over the same audio link.

**In scope:** new `minimodem-wrapper/` (C, CMake) producing `minimodem_simple.dll`
(Windows) and `libminimodem_simple.so` (Linux) with a WinMM audio backend on Windows;
AHK changes to load the new DLL and pass baud; Python `ctypes` binding replacing the
ggwave binding; single-frame message + CRC32 integrity (no chunking in v1); end-to-end
configurable baud.

**Out of scope (v2):** chunking with large (~200-word) chunks; Reed-Solomon FEC;
fountain codes; Goertzel (to drop FFTW); auto baud negotiation.
</domain>

<decisions>
## Implementation Decisions (locked)

### Scope
- Both sides move to minimodem. ggwave and minimodem are wire-incompatible; one-sided swap is not viable.

### Windows audio
- New `simpleaudio-winmm.c` implementing the `simpleaudio_backend` 4-function struct over `waveOut*`/`waveIn*`.
- WinMM chosen for zero-install portability (`winmm.dll` ships with Windows; statically linkable → single copy-pasteable binary). No Cygwin/PulseAudio/PortAudio.
- Device enumeration via `waveOutGetNumDevs`/`waveOutGetDevCaps` and `waveInGetNumDevs`/`waveInGetDevCaps`; `backend_device` selects by integer index.

### Packaging / API
- `minimodem_simple.dll` mirrors `ggwave_simple.h` API exactly so AHK keeps its `DllCall` model and `chunking.ahk`/`compression.ahk`/`gui.ahk`/`msgid.ahk` are reused nearly unchanged.
- API surface: `minimodem_simple_init(int playbackDeviceId, int captureDeviceId, int baud)`, device count/name getters, `_send(msg, volume)`, `_is_transmitting`, `_process`, `_receive(buf, size)`, `_set_baud(int)` (replaces `set_protocol`), `_cleanup`, `_get_error`.
- The old `protocolId` parameter becomes `baud`.
- A background RX thread runs continuous `waveIn` → `fsk_find_frame` → decoded-byte queue, so AHK's existing 10 ms `process()` poll + `receive()` drain model is preserved unchanged. `send()` modulates to `waveOut`.

### Reused minimodem core (vendored from minimodem/src/)
- `fsk.c`/`fsk.h` (demod), `simple-tone-generator.c` (mod), `databits_ascii.c` (8-N-1), `simpleaudio.c`/`simpleaudio_internal.h` (dispatch). Linux keeps existing `simpleaudio-alsa.c`/`simpleaudio-pulse.c`.
- minimodem.c's TX and RX loops (currently in `main()`) are refactored into reusable library functions — this is the bulk of the work and the main correctness risk.

### Pi side
- Same wrapper compiled as `libminimodem_simple.so` (ALSA/Pulse backend), called from Python via a new `lib/minimodem.py` `ctypes` binding — symmetric API on both ends. Replaces the ggwave Python binding in the transport path.

### Integrity (v1)
- Single framed message + message-level CRC32. No chunking in v1 (latency-first: avoids repeated per-chunk preamble + inter-chunk delays).
- Keep LZNT1 compression, Base62 encoding (newline-safe), and the `id`/`fn`/`ct`/`st`/`ci`/`cc` JSON schema with `ci=0`, `cc=1`.
- New `crc` field (CRC32 of `ct`) on every message: AHK via `ntdll!RtlComputeCrc32`, Python via `zlib.crc32`.
- Framing: newline-delimited JSON over the FSK byte stream.
- On CRC mismatch or timeout: full-message retransmit via the existing retransmit path. Never surface a partial/corrupt report.
- Split/reassemble code paths in `chunking.ahk`/`chunking.py` are retained but dormant, ready for v2 chunking.

### FFTW
- `fsk.c` requires single-precision `fftw3f`; statically link it so the DLL stays self-contained. Goertzel rewrite deferred to v2.

### License
- minimodem is GPLv3 (ggwave was MIT). A DLL built from its source is GPLv3 and loads into the AHK process. Accepted for internal/research use; noted in spec.

### Baud
- Configurable end-to-end, default 1200. AHK: `BAUD_RATE` global in `config.ahk`. Python: `--baud` CLI arg (default 1200). Baud is a link parameter — both ends MUST match. Must be tunable without recompiling.

### Build
- CMake, mirroring `ggwave-wrapper/` (`build_wrapper.sh`, `collect_dlls.sh`). Windows links `winmm.lib`; goal is zero redistributable DLLs beyond the one wrapper file. Verify dependency-free with a dependency walker.

### Claude's Discretion
- Exact WAVEHDR ring-buffer sizing/count for the WinMM backend (tune to avoid underruns at low baud first).
- Internal queue/threading primitives in the wrapper.
- Default FSK tone frequencies (use minimodem defaults unless tuning demands otherwise).
- Test harness specifics for the loopback test (virtual audio cable choice).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design contract
- `docs/superpowers/specs/2026-06-17-minimodem-transport-design.md` — full design: decisions, throughput table, component breakdown, data flow, testing, v2.

### Existing transport to mirror
- `ggwave-wrapper/ggwave_simple.h` — API surface the new DLL must mirror.
- `ggwave-wrapper/CMakeLists.txt`, `ggwave-wrapper/build_wrapper.sh`, `ggwave-wrapper/collect_dlls.sh` — build pattern to mirror.
- `quiet-wrapper/` — prior wrapper prototype (CMake + simple C API + build scripts) as a second reference.

### minimodem source to vendor/refactor
- `minimodem/src/minimodem.c` — TX/RX loops in `main()` to refactor into a library.
- `minimodem/src/fsk.c` / `fsk.h` — demod core (FFTW).
- `minimodem/src/simple-tone-generator.c` — modulation.
- `minimodem/src/databits_ascii.c` — 8-N-1 framing.
- `minimodem/src/simpleaudio.c`, `simpleaudio_internal.h`, `simpleaudio.h` — backend dispatch + struct to implement.
- `minimodem/src/simpleaudio-pulse.c` — closest blocking backend template for the new WinMM backend.

### Frontend layers to adapt
- `AHK/include/dll_manager.ahk` — DLL load/unload/error (repoint to new DLL).
- `AHK/main_dll.ahk` — init call (pass baud).
- `AHK/include/config.ahk` — add `BAUD_RATE`.
- `AHK/include/chunking.ahk` — single-frame + CRC.
- `AHK/include/compression.ahk` — add CRC32 helper.

### Backend layers to adapt
- `python-backend/backend.py` — transport init swap + `--baud`.
- `python-backend/lib/audio.py` — device enumeration via wrapper.
- `python-backend/lib/chunking.py` — single-frame + CRC.
- `python-backend/lib/compression.py` — CRC32.
</canonical_refs>

<specifics>
## Specific Ideas

- Throughput reference: ~500-byte report; bytes/sec ≈ baud÷10 (8-N-1) + ~0.5–1 s preamble. 1200 baud ≈ 4 s (speaker/mic); 4800–9600 baud ≈ 0.5–1 s (wired).
- Testing (manual, per project convention): (1) DLL loopback via virtual cable across baud rates; (2) cross-machine AHK↔Pi over USB audio cable; (3) report-length single-frame payloads with induced corruption to confirm CRC + full retransmit; (4) baud sweep without recompile, both ends matched.
</specifics>

<deferred>
## Deferred Ideas (v2)

- Chunking with large (~200-word ≈ ~1 KB) chunks for long payloads; re-request only the corrupted chunk. Dormant split/reassemble code stays in place to ease this.
- Reed-Solomon-per-chunk FEC (e.g. RS(255,223)); fountain codes (LT/Raptor).
- Goertzel 2-tone detection to drop the FFTW dependency.
- Auto baud negotiation between ends.
</deferred>

---

*Phase: 07-replace-ggwave-with-minimodem-both-sides*
*Context gathered: 2026-06-17 from design spec*
