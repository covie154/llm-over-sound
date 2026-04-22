# Session Reflection — 28 Feb 2026: quiet_simple DLL Wrapper

## Objective

Replace ggwave (~140 bytes/frame) with libquiet for the audio data pipe. Build
libquiet and all dependencies on Windows via MSYS2, then create a `quiet_simple.dll`
wrapper with the same API pattern as `ggwave_simple.dll` so the AHK frontend can be
migrated to the higher-throughput library (up to 7500 bytes/frame with cable-64k).

---

## What was done

### 1. quiet_simple wrapper DLL (6 files created)

| File | Purpose |
|------|---------|
| `quiet-wrapper/quiet_simple.h` | DLL header — 12 exported functions with `dllexport`/`dllimport` macros |
| `quiet-wrapper/quiet_simple.c` | C99 implementation (~600 lines) |
| `quiet-wrapper/CMakeLists.txt` | Builds `quiet_simple.dll`, links quiet + portaudio + pthread |
| `quiet-wrapper/build_deps.sh` | MSYS2 script: installs packages, builds libfec, liquid-dsp, libquiet |
| `quiet-wrapper/build_wrapper.sh` | MSYS2 script to cmake + make the wrapper |
| `quiet-wrapper/collect_dlls.sh` | Copies runtime DLLs + `quiet-profiles.json` to `AHK/` |

### 2. Key architecture decisions

- **Encoder:** Uses raw `quiet_encoder` + a custom PortAudio output callback
  (NOT `quiet_portaudio_encoder`). This gives accurate `is_transmitting()` —
  the callback detects when `quiet_encoder_emit()` returns no data, meaning
  the transmit queue has drained. No timestamp estimation needed.
- **Decoder:** Uses `quiet_portaudio_decoder_create()` which manages its own
  background thread and ring buffer. `receive()` polls non-blocking
  `quiet_portaudio_decoder_recv()`.
- **No `process()` function:** Unlike ggwave_simple which requires explicit
  `process()` calls in a polling loop, quiet's PortAudio callbacks handle
  audio I/O automatically. The AHK caller only polls `receive()` and checks
  `is_transmitting()`.
- **`send()` takes `(data, len)` instead of a null-terminated string** — supports
  binary payloads directly.
- **`get_frame_len()`** lets AHK query the max payload dynamically rather than
  hardcoding assumptions about frame size.

### 3. API differences from ggwave_simple

| ggwave_simple | quiet_simple | Reason |
|---------------|--------------|--------|
| `init(playback, capture, protocolId)` | `init(playback, capture, profileName, profilesPath)` | Profiles are named strings, not numeric IDs |
| `send(message, volume)` | `send(data, len)` | Binary payloads; volume handled at OS level |
| `process()` required in loop | No process needed | PortAudio callbacks are automatic |
| `set_protocol(id)` | `set_profile(name)` | Destroys and recreates encoder/decoder |
| N/A | `get_frame_len()` | New — AHK queries max payload dynamically |

### 4. Code review fixes applied

The wrapper was reviewed and the following issues were caught and fixed:

1. **Uninitialized mutex** — Added `PTHREAD_MUTEX_INITIALIZER` to static struct.
2. **Unchecked realloc in device map building** — Replaced with `free` + `malloc`
   with NULL checks, handling the zero-device edge case.
3. **Device enumeration not mutex-protected** — All four enumeration functions
   now acquire the mutex.
4. **`quiet_encoder_send` return 0 (EOF) not handled** — Changed `sent < 0` to
   `sent <= 0` with distinct error messages.
5. **Race between Pa_Terminate and decoder thread** — Added `Pa_Sleep(150)` in
   cleanup to let the background consume thread exit before tearing down PortAudio.
6. **NULL-check encoder in PA callback** — Defensive guard against the brief
   window during destroy/recreate where the encoder pointer could be NULL.
7. **`get_frame_len()` lacked mutex** — Added for consistency with other API
   functions.

---

## MSYS2 build issues encountered

Building libquiet's dependency chain on a fresh MSYS2 install surfaced several
issues. Documenting them here for future reference.

### Issue 1: Stale package database (404 on mirrors)

**Symptom:** `pacman -S` fails with 404 errors fetching `.pkg.tar.zst` files.
**Fix:** `pacman -Syu` to sync the database before installing anything.

### Issue 2: pkgconf vs pkg-config conflict

**Symptom:** Installing `mingw-w64-x86_64-pkg-config` conflicts with the
already-installed `mingw-w64-x86_64-pkgconf`, and removing pkgconf breaks cmake.
**Root cause:** `pkgconf` is the modern replacement for `pkg-config`. MSYS2
ships pkgconf by default; cmake depends on it. The build script was requesting
the older `pkg-config` package unnecessarily.
**Fix:** Changed the script to install `mingw-w64-x86_64-pkgconf` instead.

### Issue 3: No C compiler on fresh MSYS2 install

**Symptom:** CMake reports `No CMAKE_C_COMPILER could be found`.
**Root cause:** Fresh MSYS2 doesn't include the MinGW GCC toolchain by default.
**Fix:** Added `mingw-w64-x86_64-gcc` to the pacman install list.

### Issue 4: libfec cmake_minimum_required too old

**Symptom:** CMake error — `Compatibility with CMake < 3.5 has been removed`.
**Root cause:** The quiet/libfec fork's CMakeLists.txt uses a very old minimum
version that newer CMake rejects.
**Fix:** Added `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` to the cmake invocation.

### Issue 5: libfec uses POSIX `random()` unavailable on Windows

**Symptom:** `sim.c:23: error: implicit declaration of function 'random'`.
**Root cause:** `random()` and `MAX_RANDOM` are POSIX-only; MinGW doesn't
provide them.
**Fix:** Added `-DCMAKE_C_FLAGS="-Drandom=rand -DMAX_RANDOM=RAND_MAX"` to map
them to the C standard equivalents at compile time without modifying upstream
source.

### Issue 6: Stale CMake cache after failed builds

**Symptom:** Re-running cmake after fixing an issue still fails with the old
error because `CMakeCache.txt` cached the failure.
**Fix:** Changed `mkdir -p build` to `rm -rf build && mkdir build` in the
libfec build step so the cache is always fresh.

---

## Status

- **quiet_simple wrapper code:** Complete, reviewed, all fixes applied.
- **build_deps.sh:** Partially tested — packages install, libfec build in
  progress (last fix applied but not yet confirmed).
- **build_wrapper.sh / collect_dlls.sh:** Not yet tested (blocked on deps).
- **AHK integration:** Not started — will need updated DllCall wrappers.
- **Loopback test:** Not yet done.

## Next steps

1. Finish the dependency build (libfec → liquid-dsp → libquiet).
2. Build `quiet_simple.dll` with `build_wrapper.sh`.
3. Run `collect_dlls.sh` to stage DLLs in `AHK/`.
4. Write a minimal AHK test script to load the DLL, enumerate devices, and
   query frame length.
5. Loopback test: connect audio output to input, send a string, verify receipt.
6. Migrate the AHK frontend from ggwave_simple to quiet_simple.
