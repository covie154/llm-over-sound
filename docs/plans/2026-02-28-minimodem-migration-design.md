# Design: Migrate Audio Transport from ggwave to minimodem

**Date:** 2026-02-28
**Status:** Approved

## Motivation

ggwave is too slow for practical use (~140 bytes per transmission). minimodem is a
proven, well-maintained FSK modem tool that offers configurable baud rates and higher
throughput over wired audio connections. libquiet was considered but rejected due to
stale dependencies and difficult builds.

## Architecture Overview

Extract minimodem's core FSK engine into a native Windows DLL (`minimodem_simple.dll`)
paired with PortAudio for audio I/O. On the Raspberry Pi, use the minimodem CLI via
subprocess (apt-installable). The existing chunking, compression, and message framing
layers are transport-agnostic and remain unchanged.

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transport library | minimodem FSK core | Simpler and more proven than libquiet; faster than ggwave |
| Fallback | Approach 3 (subprocess wrapper DLL) | If FSK extraction proves too difficult |
| Windows integration | Native DLL (PortAudio + FFTW3f) | Portable, no installation needed on work machine |
| Pi integration | Subprocess wrapping minimodem CLI | Native Linux tool, apt-installable, simplest path |
| Starting baud rate | 1200 (Bell 202) | Conservative start, tune up once stable |
| ggwave disposition | Archived to `archive/` | Keep as reference, not deleted |
| Chunk size | Configurable, default ~1500-2000 chars | No per-frame limit in minimodem; radiologist reports are a few hundred words |
| Message delimiter | Newline (`\n`) after each JSON chunk | Simple, natural for text streams, easy to debug |
| Build toolchain | MSYS2/MinGW-w64 + CMake | FFTW3f and PortAudio available via pacman; produces native Windows binaries |

## DLL API (`minimodem_simple.h`)

```c
// Init/cleanup
int  minimodem_simple_init(int playbackId, int captureId, int baud_rate);
void minimodem_simple_cleanup(void);

// Transmit
int  minimodem_simple_send(const uint8_t *data, int len);
int  minimodem_simple_is_transmitting(void);

// Receive
int  minimodem_simple_receive(uint8_t *buffer, int bufferSize);

// Configuration
int  minimodem_simple_set_baud_rate(int baud_rate);
int  minimodem_simple_get_frame_len(void);

// Device enumeration
int         minimodem_simple_get_playback_device_count(void);
int         minimodem_simple_get_capture_device_count(void);
const char* minimodem_simple_get_playback_device_name(int id);
const char* minimodem_simple_get_capture_device_name(int id);

// Error reporting
const char* minimodem_simple_get_error(void);
```

Key differences from ggwave_simple:
- `send()` takes binary data (`uint8_t*` + length) instead of null-terminated string
- `baud_rate` replaces `protocolId`
- No `process()` function — PortAudio runs in background threads
- `get_frame_len()` returns max payload size for dynamic chunk sizing

## DLL Internals

### Files Extracted from minimodem

Copied into `minimodem-wrapper/`, not modified in the minimodem submodule:

- `fsk.c` / `fsk.h` — FFT-based FSK bit detection. Only dependency: FFTW3f. Operates
  on float32 sample buffers. Core function `fsk_find_frame()` returns decoded bits +
  confidence score.
- `databits_ascii.c` / `databits.h` — byte-to-bits passthrough (8-bit ASCII, LSB-first).
- `tone_generator.c` — adapted from `simple-tone-generator.c`. Modified to write to
  float buffers instead of simpleaudio handles. Maintains phase continuity across calls.

### FSK Parameters (1200 baud, Bell 202)

| Parameter | Value |
|-----------|-------|
| Sample rate | 48000 Hz |
| Mark frequency | 1200 Hz |
| Space frequency | 2200 Hz |
| Samples per bit | 40 |
| Frame format | 1 start + 8 data (LSB-first) + 1 stop |
| Confidence threshold | 1.5 |
| Carrier loss | 20 consecutive low-confidence bits |

### Transmit Path

1. `send(data, len)` called by AHK
2. Pre-generate entire waveform into float buffer:
   - Leader: 2 bits of mark tone
   - For each byte: start bit (space) + 8 data bits LSB-first (mark/space) + stop bit (mark)
   - Trailer: 2 bits of mark tone
3. Queue waveform to PortAudio TX ring buffer
4. `is_transmitting()` returns 1 until PortAudio drains the buffer

### Receive Path (Background Decoder Thread)

```
State: WAITING_FOR_CARRIER
  - PortAudio RX callback pushes float samples into ring buffer
  - Decoder thread pulls samples, runs fsk_find_frame()
  - If confidence >= 1.5 -> RECEIVING

State: RECEIVING
  - Decode frames continuously (start + 8 data + stop bits)
  - Strip framing, extract byte, append to message buffer
  - Track amplitude (running average)
  - If 20+ consecutive low-confidence bits OR amplitude < 25% of track
    -> CARRIER_LOST

State: CARRIER_LOST
  - Finalize message buffer
  - Push completed message to decoded message queue
  - Reset state -> WAITING_FOR_CARRIER
```

`receive()` pops from the decoded message queue. Returns 0 if empty.

### Threading Model

- PortAudio RX callback -> lock-free ring buffer -> decoder thread -> message queue
- TX: `send()` pre-generates waveform -> PortAudio TX ring buffer -> callback drains
- Mutex on message queue; lock-free ring buffers for audio samples

## Directory Structure

```
minimodem-wrapper/
  CMakeLists.txt
  build.sh                # MSYS2 build script
  collect_dlls.sh         # Copy runtime DLLs to AHK/
  minimodem_simple.h      # Public API
  minimodem_simple.c      # PortAudio I/O, state machine, ring buffers
  fsk.c / fsk.h           # Copied from minimodem/src/
  databits_ascii.c        # Copied from minimodem/src/
  databits.h              # Copied from minimodem/src/
  tone_generator.c        # Adapted from minimodem/src/simple-tone-generator.c
```

### Runtime DLLs (shipped with AHK, no install)

- `minimodem_simple.dll` (ours)
- `libfftw3f-3.dll`
- `libportaudio-2.dll`
- Static-link MinGW runtime if possible, otherwise also ship `libgcc_s_seh-1.dll`
  and `libwinpthread-1.dll`

### Build Dependencies (MSYS2 pacman)

```
mingw-w64-x86_64-fftw
mingw-w64-x86_64-portaudio
mingw-w64-x86_64-cmake
```

## AHK Frontend Changes

### Modified files

- **`config.ahk`**: `DLL_NAME` -> minimodem_simple.dll, remove `PROTOCOL_ID`, add
  `BAUD_RATE := 1200`, make `CHUNK_DATA_SIZE` configurable (default ~1500-2000 chars)
- **`dll_manager.ahk`**: `LoadMinimodemDll()` replacing `LoadGGWaveDll()`, updated init
  call signature (baud_rate instead of protocolId), send takes data+length
- **`gui.ahk`**: Protocol dropdown -> baud rate selector (1200, 2400, 4800)
- **`main_dll.ahk`**: Remove `SetTimer(ProcessAudio, 10)` polling, update init/send calls

### Unchanged files

- `chunking.ahk` — transport-agnostic
- `compression.ahk` — transport-agnostic
- `msgid.ahk` — transport-agnostic

### Chunking implications

With no per-frame payload limit, minimodem sends the entire message as one continuous
FSK stream. Chunking is retained for message IDs, sequencing, retransmission, and
reliability. `CHUNK_DATA_SIZE` increases from 70 to ~1500-2000 characters, reducing
chunk count for typical reports to 1-2 chunks.

Each JSON chunk is terminated with `\n` as the message delimiter.

## Python Backend Changes

### Subprocess transport on Raspberry Pi

Replace ggwave Python bindings with a `MinimodemTransport` class that manages two
persistent subprocesses:

- `minimodem --rx 1200 --quiet` — listens on audio input, decoded text to stdout
- `minimodem --tx 1200` — text from stdin, FSK audio to output

RX: background thread reads stdout, splits on `\n`, pushes JSON chunks to receive queue.
TX: write chunk JSON + `\n` to stdin pipe, flush.

### Modified files

- **`backend.py`**: Replace ggwave init/encode/decode with MinimodemTransport class
- **`lib/config.py`**: Replace `GGWAVE_PAYLOAD_LIMIT` with `CHUNK_DATA_SIZE = 1500`,
  add `BAUD_RATE = 1200`, remove `PROTOCOL_ID`

### Unchanged files

- `lib/chunking.py` — transport-agnostic (update CHUNK_DATA_SIZE reference)
- `lib/compression.py` — unchanged
- `lib/pipeline.py` — unchanged

## Archiving ggwave

- Move `ggwave-wrapper/` -> `archive/ggwave-wrapper/`
- Copy current `AHK/include/dll_manager.ahk` -> `archive/ggwave_dll_manager.ahk`
- Keep `ggwave/` submodule as-is (upstream code)
- Add `archive/README.md` noting these are reference implementations

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| FSK extraction harder than expected | Fall back to Approach 3 (subprocess DLL wrapper) |
| FFTW3f build issues on MSYS2 | Available as prebuilt package via pacman |
| Carrier detect unreliable at high baud | Start at 1200, tune confidence thresholds |
| Latency too high at 1200 baud | ~1.3 seconds for 1500-char chunk; acceptable for report formatting |
| Thread safety bugs in DLL | Follow quiet-wrapper pattern (proven pthread mutex approach) |
