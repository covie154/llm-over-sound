# Technology Stack

**Analysis Date:** 2026-03-28

## Languages

**Primary:**
- **Python 3** - Backend server on Raspberry Pi/Linux SBC (`python-backend/backend.py`)
- **AutoHotkey v2.0** - Windows GUI frontend (`AHK/main_dll.ahk`, strict v2 syntax required)
- **C++17** - ggwave wrapper DLL for audio I/O (`ggwave-wrapper/ggwave_simple.cpp`)

**Supporting:**
- **C** - ggwave core library (upstream dependency, `ggwave/src/ggwave.cpp`)

## Runtime

**Environment:**
- **Python 3.x** - Runs on Raspberry Pi or equivalent SBC (Linux)
- **AutoHotkey v2.0** - Runs on Windows (tested on Windows 11 Pro)
- **Windows NTDLL APIs** - Required on frontend for compression (RtlCompressBuffer, RtlDecompressBuffer)

**Package Manager:**
- **pip** - Python package management
- **CMake 3.10+** - C++ build system for wrapper and ggwave

## Frameworks

**Core:**
- **ggwave** - Data-over-sound library for audio-based IPC. Uses protocol ID 1 (Audible Fast, ~140 bytes/transmission limit)
- **PyAudio** - Python bindings for audio device I/O and stream management (both input and output at 48kHz mono)
- **SDL2** - Audio backend for ggwave (vendor copy at `ggwave/SDL2/`)

**Testing:**
- Manual testing (no automated harness) - Integration tests via round-trip message integrity with USB audio cable between Windows PC and Pi

**Build/Dev:**
- **CMake** - Cross-platform build for C++ wrapper
- **C++17 Standard** - Compilation target for wrapper DLL

## Key Dependencies

**Critical:**
- **ggwave** (`ggwave/`) - Upstream library providing data-over-sound encoding/decoding. Protocol ID 1 is default (Audible Fast).
  - Why it matters: Core IPC mechanism; audio pipe is sole communication channel between frontend and backend
- **PyAudio** - Python bindings for cross-platform audio I/O
  - Why it matters: Receives ggwave signals from mic, sends to speaker; device enumeration for USB audio interface selection
- **SDL2** - Underlying audio implementation for ggwave
  - Why it matters: Provides hardware abstraction for audio capture/playback on Windows and Linux

**Infrastructure:**
- **ntdll.dll** (Windows system) - LZNT1 compression/decompression via RtlCompressBuffer/RtlDecompressBuffer
  - Compression engine constant: COMPRESSION_FORMAT_LZNT1=2 (default in frontend)
- **Crypt32.dll** (Windows system) - Base64 encoding via CryptBinaryToStringW (used for payload encoding in frontend)

## Configuration

**Environment:**
- No environment file (`.env`) currently required
- LLM integration TBD - pipeline stages 1, 3, 4, 5 have stub implementations (NotImplementedError)
- Configuration is hardcoded in:
  - `AHK/include/config.ahk` - Frontend settings (COMPRESSION_THRESHOLD=100, GGWAVE_PAYLOAD_LIMIT=140, etc.)
  - `python-backend/lib/config.py` - Backend settings (same constants)

**Build:**
- **CMakeLists.txt** in `ggwave-wrapper/` - Configures C++ compilation, finds SDL2, links against ggwave source
- SDL2_DIR configured to `ggwave/SDL2/cmake` for CMake discovery
- Output directory: `build/` (created by CMake)

## Platform Requirements

**Development:**
- **Windows 11 Pro** (tested; Windows 10+ expected to work)
  - AutoHotkey v2.0 installed
  - CMake 3.10+ for building wrapper DLL
  - USB audio interface or built-in line-out (for ggwave output to Pi)
- **Linux (Raspberry Pi or SBC)**
  - Python 3.x installed
  - PyAudio library installed
  - Audio input/output: USB audio interface (recommended over onboard 3.5mm jack)

**Production:**
- **Deployment target:** Raspberry Pi 4B or equivalent SBC running Linux (full duplex USB audio interface)
- **Windows PC:** Audio interface with line-out to Pi line-in; USB audio input for receiving from Pi
- **Audio specs:**
  - Sample rate: 48 kHz (mono)
  - Protocol: ggwave Audible Fast (ID 1)
  - Bandwidth: ~140 bytes per transmission (requires chunking for full reports)

## Audio Channel Specifications

**Transmission Protocol:**
- ggwave Audible Fast (protocol ID 1)
- Payload ceiling: ~140 bytes per transmission
- Compression threshold: Messages >100 characters are compressed using LZNT1
- Chunking: Messages exceeding per-transmission limit are split with sequencing headers (message ID, chunk index "ci", chunk count "cc")
- Chunk reassembly timeout: 30 seconds before requesting retransmission

**Audio Interface:**
- Target: Class-compliant USB audio interface on both sides
- Current testing: USB speaker/microphone
- Future: Dedicated USB audio interface with separate line-out to Pi line-in and line-in from Pi line-out (full duplex)
- Volume calibration: Configurable via `--volume` flag on backend (default 50, range 1-100) and Windows audio settings

---

*Stack analysis: 2026-03-28*
