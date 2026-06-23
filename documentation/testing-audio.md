# Testing the minimodem Audio Link (Phase 7)

**Last updated:** 2026-06-21
**Scope:** Bring-up and testing of the minimodem FSK transport that replaced ggwave
(Phase 7). Covers the C wrapper, the Windows (AHK) and Pi (Python) integration, and the
hardware audio link.

Related docs:
- Design contract: [`docs/superpowers/specs/2026-06-17-minimodem-transport-design.md`](../docs/superpowers/specs/2026-06-17-minimodem-transport-design.md)
- Phase plans/summaries: `.planning/phases/07-replace-ggwave-with-minimodem-both-sides/`

---

## Where we are

The minimodem cutover is **functionally proven end-to-end except the live acoustic
round trip**, which is bottlenecked by the audio channel (not the code).

| Layer | Status | Evidence |
|-------|--------|----------|
| C engine (modulate/demod/DSP, `mm_core.c`) | ✅ working | `minimodem_loopback` byte-exact on Windows **and** Pi |
| Wave-0 CRC32 agreement | ✅ working | `crc32("123456789") == 0xCBF43926` on Python; AHK uses same `ntdll!RtlComputeCrc32` |
| `minimodem_simple.dll` (Windows, WinMM) | ✅ built, dependency-free | `objdump`/`ntldd`: only KERNEL32/WINMM/msvcrt |
| `minimodem_simple.so` (Pi, ALSA) | ✅ built, loads | `nm -D` shows API; ctypes `load()` OK |
| Windows TX audio | ✅ correct | waveform: continuous, correct 1200/300-baud tones, good level |
| Pi ALSA capture path | ✅ receives signal | `arecord` VU meter moves; capture recorded |
| **Acoustic round-trip decode** | ❌ marginal | tones smeared by speaker→air→mic; CRC fails |
| **Wired (UCA202 ×2) decode** | ✅ frames intact | JSON frame arrives complete over line-out→line-in; framing now tolerant of FSK acquisition garbage |

**Bottom line:** modem, framing, CRC, levels, and frequencies are all correct. The
acoustic channel smears two closely-spaced FSK tones; the **wired Behringer UCA202
line-level path decodes cleanly** (the intended target hardware). Two UCA202s (Pi card 0,
PC side) gave intact frames on the first wired attempt.

---

## Progress so far (what was built/fixed)

Phase 7 shipped in four waves (see phase SUMMARYs), then a series of hardware bring-up fixes:

**Waves**
1. `minimodem-wrapper/` foundation: `minimodem.c` `main()` TX/RX loops decomposed into a
   context-struct library (`mm_core.c`); new `simpleaudio-winmm.c` WinMM backend;
   dependency-free DLL.
2. Public `minimodem_simple_*` API + background RX thread + newline-framed queue;
   Wave-0 gate (byte-exact loopback + CRC32 vector).
3. AHK frontend + Python backend swapped to minimodem: single-frame message + CRC32,
   configurable `--baud` / `BAUD_RATE`, `ggwave`/`pyaudio` removed from the transport path.
4. Hardware validation plan (round trip / corruption / baud sweep / retire ggwave) — **in progress**.

**Bring-up fixes (commit refs)**
- `c9040c1` — **WinMM TX coalescing**: ~9× transmit slowdown fixed; baud now actually affects speed.
- `ba16c6d` — `gui.ahk` device enumeration still called the `ggwave_simple` namespace → repointed to `minimodem_simple` + empty-list guard (was crashing `speakerList.Choose(1)`).
- `e2f2a85` — replaced the dead "protocol" dropdown with an editable **baud** field.
- `a7f4c05` — Linux build is **ALSA-only by default** (fixes `undefined symbol: pa_simple_free`); PulseAudio is opt-in (`-DMM_ENABLE_PULSE=ON`).
- `requirements.txt` added (`pydantic`, `python-frontmatter`; no pyaudio/ggwave).

---

## Gotchas (hard-won)

### Build / toolchain
- **NDEBUG strips TX audio.** The vendored `simple-tone-generator.c` emits the audio
  `simpleaudio_write` *inside an `assert()`*. A Release build (`-DNDEBUG`) removes the
  assert **and its side-effecting write** → silent TX. The CMake forces `-UNDEBUG`.
- **Windows build = MSYS2 MinGW64** (`/c/msys64/mingw64`), static `fftw3f` + `-static
  -static-libgcc` → a single copy-pasteable `.dll` with only system DLL deps. Verify with
  `objdump -p` / `ntldd -R`.
- **Linux build is ALSA-only by default.** Building the Pulse backend without linking
  `libpulse-simple` left an `undefined pa_simple_free` symbol that broke `dlopen`. Pulse is
  also the `SYSDEFAULT` backend when compiled in, so it would fail at runtime on a bare-ALSA
  Pi anyway. Use plain `cmake .. && cmake --build .` (not the Windows `build_wrapper.sh`).

### ALSA / device selection (the big time-sinks)
- **Capture is silent until you arm it.** `alsamixer -c <card>` → **F4 (Capture)** →
  unmute (`M`), raise gain, and press **Space** so the channel shows a red **`CAPTURE`**
  label. If there's an **Auto Gain Control**, turn it **OFF** (AGC pumps and wrecks FSK).
  Persist with `sudo alsactl store`. Use `arecord -D plughw:<N>,0 -V mono /dev/null` to
  watch the live input meter.
- **`default` ≠ your USB card.** On this Pi, ALSA `default` resolves to card 0 (bcm2835
  **HDMI**, playback-only) → `arecord` gives `audio open error: No such file or directory`
  on capture. The USB interface here is **card 2** (`Device` / "USB PnP Sound Device",
  full duplex: playback dev 0 + capture dev 0).
- **USB card indices can drift** across reboots/replug. Prefer a by-name `~/.asoundrc`
  (`plughw:CARD=Device,DEV=0`) or pass explicit indices to the backend.
- **`backend.py` with no `-i/-o` is currently broken on Linux.** It passes device id `-1`,
  and the wrapper turns that into the ALSA string `plughw:-1,0` (invalid) instead of
  `"default"`. **Workaround: always pass `-i 2 -o 2`** → the wrapper opens `plughw:2,0`
  (the raw device that works). *(Latent bug — see Next steps.)*
- **Single-subdevice USB card = exclusive.** While `backend.py` holds card 2 you can't also
  run `arecord` on it; stop the backend before VU-meter / capture tests.

### Diagnosing the link
- **`minimodem` CLI is the reference decoder.** `sudo apt install minimodem`, then
  `minimodem --rx --file cap.wav <baud>`. Reading a recording with stock minimodem cleanly
  separates "our code" from "the signal". (Our wrapper uses minimodem's own Bell‑202/103
  tone derivation, so stock minimodem decodes our frontend's output.)
- **`CARRIER … rate perfect` + low `ampl`/`confidence` + garbage = signal problem, not
  baud/code.** `confidence ≈ 1.5` is minimodem's floor (it's guessing on noise).
- **Per-byte `CARRIER/NOCARRIER` flicker ≠ audio gaps.** Spectral analysis showed the
  transmission is one continuous burst; the flicker was just low-confidence wobble.
- **FSK carrier-acquisition garbage wraps each frame.** Async FSK demod emits a few
  spurious bytes while the carrier ramps up, and noise between frames can trigger a brief
  spurious carrier lock. These bytes get prepended/appended to the newline-framed line
  (`\x..K*\x..B}{"cc":1,...}`), so a raw `json.loads`/`Jxon_Load` fails at column 0 even
  though the payload is intact. Fix: recover the JSON object by slicing first-`{` to
  last-`}` (`extract_json_frame` in `chunking.py`; brace-slice in `chunking.ahk`) — CRC
  stays the integrity gate, so a mis-sliced frame fails CRC and is rejected. Lines with no
  brace pair are pure noise → skipped quietly. *(This was the last blocker on the wired
  round trip.)*
- **Acoustic smears closely-spaced tones.** At 300 baud Bell‑103 the mark/space are only
  ~200 Hz apart (≈1070/1270 Hz); a consumer speaker→air→mic path spread the energy across
  1050–1270 Hz, blurring the two tones → bit errors → CRC reject. Level was fine (peak
  0.57, no clipping) — separation/SNR was the problem.

### Throughput
- Wire-time ≈ `bytes ÷ (baud / 10)` (8-N-1) + a fixed carrier/preamble. ~500 B ≈ 4 s @1200,
  ~0.5 s @9600. Before the coalescing fix it was ~36 s and baud-independent.

---

## Reflections / lessons

- **In-memory loopback validated the *engine* but not the *device paths*.** The Wave-0
  loopback uses an in-memory `simpleaudio` backend, so neither the WinMM TX path nor the
  ALSA RX path was exercised until hardware bring-up. Both had real issues the gate could
  never have caught (the WinMM per-bit-write slowdown; the `-1` device-string bug). Lesson:
  a loopback that bypasses the real backend is necessary but not sufficient — budget for a
  first-real-hardware debugging pass.
- **Layered isolation paid off.** Raw hardware (`plughw:2,0`) → reference decoder
  (`minimodem --rx`) → spectral analysis (Goertzel windows) each removed a layer of
  ambiguity and pointed at the channel, sparing a wild goose chase through the code.
- **Decode "garbage" is information.** Correct frequency + "rate perfect" told us the modem
  was right long before anything decoded; the missing piece was always amplitude/SNR/tone
  separation.
- **Acoustic data-over-sound with consumer USB audio is genuinely hard** at these tone
  spacings. The project's wired-cable target exists for exactly this reason; acoustic is a
  testing convenience, not the design point.

---

## Next steps

**Immediate — finish the round trip (Wave 4 / Plan 07-05):**
1. ~~Validate over the wired cable.~~ **DONE (2026-06-24)** — two UCA202s over line-out→line-in
   decode intact frames at 1200 baud (after the FSK-garbage framing fix). Next: confirm the
   full **response path** (backend echoes via `TestPipeline` → frontend displays it) and the
   reverse direction.
2. Run the **CRC + full-retransmit** integrity test (induce corruption → confirm no partial
   report ever surfaces) and the **baud sweep** (1200/4800/9600, both ends matched; record
   where the interface passband fails — note high baud may need a tone override).
3. **Retire ggwave artifacts** (`AHK/ggwave_simple.dll`, `AHK/SDL2.dll`) only after the
   round trip is confirmed.

**If acoustic testing must work now:**
4. **Add a tone-override** (custom mark/space) to `minimodem_simple_*` + AHK `config.ahk` +
   Python `--mark/--space`, with a both-ends-match check. A wide shift (e.g. mark 1200 /
   space 2200 at 300 baud) survives acoustic smearing far better than the narrow Bell‑103
   shift. (This is the "tone override" flagged as assumption A2 / spec v2.)

**Cleanups / deferred:**
5. **Fix the `-1` → `"default"` Linux device bug** in `minimodem_simple.c` (`deviceId < 0`
   should pass `NULL` so ALSA opens `"default"`), so a bare `python backend.py` works via the
   `~/.asoundrc` default.
6. **Re-enable compression** (LZNT1 + Base62) once the round trip is validated — agreed to do
   this as the first step *after* validation. Gate it behind a cross-impl round-trip check
   (AHK `ntdll` LZNT1 ↔ Python pure-LZNT1).
7. **(v2)** Audio source auto-recognition + level calibration handshake — auto-detect the USB
   interface and self-tune TX volume / RX gain (already in the spec's "Out of scope / v2").
8. Delete the legacy ggwave-era scripts `python-backend/testing-audio.py` and
   `test-output-audio.py` (still import `pyaudio`/`ggwave`; unused by the runtime).

---

## Quick reference — commands used

```bash
# Pi build (ALSA-only, default)
cd minimodem-wrapper && rm -rf build && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release && cmake --build . -j"$(nproc)"
nm -D minimodem_simple.so | grep minimodem_simple_   # exports present?
./minimodem_loopback                                  # engine self-test (byte-exact)

# Pi device check + capture meter (stop backend first — exclusive device)
cat /proc/asound/cards ; arecord -l ; aplay -l
arecord -D plughw:2,0 -f S16_LE -r 48000 -c 1 -V mono /dev/null   # live input meter

# Run backend (MUST pass -i/-o on Linux for now)
python backend.py --baud 1200 -i 2 -o 2

# Reference-decode a recording (isolate signal vs code)
arecord -D plughw:2,0 -f S16_LE -r 48000 -c 1 -d 4 cap.wav   # send from PC during window
sudo apt-get install -y minimodem
minimodem --rx --file cap.wav 1200      # or 300 for Bell-103
```
