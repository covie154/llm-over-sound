# Reflections — Phase 7: minimodem cutover & audio bring-up (2026-06-25)

Session arc: took Phase 7 (replace ggwave with minimodem FSK on both ends) from design
through a 4-wave build to a **functionally validated bidirectional round trip** over a
wired Behringer UCA202 link. The build went roughly to plan; the long tail — and most of
the learning — was in hardware/integration bring-up.

Companion reference (the how-to + gotcha catalogue): [`testing-audio.md`](testing-audio.md).

---

## The shape of the work (and the surprise)

The "planned" work — wrapping minimodem behind the `ggwave_simple` API, a WinMM backend, a
ctypes binding, single-frame+CRC framing — was the *easy* 20%. The unplanned 80% was
everything that only shows up when real audio hardware is in the loop. Nearly every bug
this session lived at an **integration seam that no test exercised**:

- The Wave-0 loopback gate passed byte-exact — but it used an **in-memory** simpleaudio
  backend, so it never touched the **WinMM TX path** or the **ALSA RX path**. Both had real
  defects (the per-bit-write throughput collapse; the `-1`→`plughw:-1,0` device bug) that a
  green loopback hid.
- `gui.ahk` still called the `ggwave_simple` DLL namespace for device enumeration — a file
  the plan declared "unchanged."
- A **mono** modem over a **stereo** interface — the OS bridges it, but only if you wire
  both channels.
- A request/response protocol that didn't **enforce** its own request-vs-response
  distinction, so self-echo became an infinite feedback loop.
- FSK carrier-acquisition garbage wrapping every frame, breaking a naive `json.loads`.

**Lesson:** a passing loopback that bypasses the real device path gives false confidence.
"Tested" must mean the actual seam that ships, not a convenient stand-in. Budget explicitly
for a first-on-hardware debugging pass — it is not a rounding error.

---

## What actually broke, and the pattern

| Symptom | Real cause | Class |
|---|---|---|
| ~36 s to send 476 B; 1200==9600 baud | WinMM wrote one tiny buffer per *bit*; ring saturated → every bit blocked on a timer-granularity event | systems / audio API |
| Empty device pickers, `Choose(1)` crash | `gui.ahk` enumerated via the old `ggwave_simple` namespace | integration seam |
| `undefined symbol: pa_simple_free` | Linux build compiled the Pulse backend but didn't link it; Pulse also wrong default on a bare-ALSA Pi | build config |
| `audio open error: No such file` | ALSA `default` = onboard HDMI (no capture), not the USB card | OS audio routing |
| `json.loads` fails at col 0 | FSK acquisition garbage prepended to the frame | data-over-sound reality |
| Runaway "Processed function … Processed function …" | backend reprocessed its OWN echoed responses | protocol design |
| Flat / garbage capture | mono-over-stereo: only one RCA channel wired; OS averages L+R | electrical / channel |

The pattern: **most failures were not in the algorithm; they were at boundaries** — DLL↔AHK,
mono↔stereo, request↔response, modem↔channel, app↔OS-audio. The DSP core (proved by
loopback) was correct the whole time.

---

## Debugging discipline that worked

- **Reference implementation as oracle.** Decoding recordings with the stock `minimodem`
  CLI instantly separated "our code" from "the signal." When it showed `CARRIER … rate
  perfect` but `ampl≈0` + garbage, we knew the modem/baud were right and the channel was bad
  — no point touching code.
- **Spectral analysis to settle arguments.** A 40-line Goertzel script over `cap300.wav`
  proved the transmission was continuous (not gappy), correctly-toned, good level — but
  smeared across the band. That killed the "is it a TX bug?" hypothesis with data.
- **Logs as ground truth, not ad-hoc recordings.** The backend `[RECV_RAW]` and frontend
  logs unambiguously showed *which direction* worked. The audio recorder actively misled us
  (an idle return line is *supposed* to be flat; a "valid recording" was just self-echo).
- **One variable at a time.** The worst stretch was when hardware was being swapped between
  observations — the rig became a moving target. Locking the wiring and changing one thing
  at a time is what finally converged it.

---

## Design decisions that paid off

- **CRC as the single integrity gate.** Because every frame is CRC-checked, we could be
  *aggressive* about frame recovery — scan every `{`, slice past garbage, ignore trailing
  junk — with zero risk of accepting a corrupt frame. A mis-extraction simply fails CRC and
  is dropped. Cheap heuristics are safe when a strong gate backs them.
- **Latency-first v1 (single frame, no chunking).** Kept the protocol tiny and made the
  WinMM throughput bug obvious (a single transmission, easy to time) instead of hiding it in
  chunk churn.
- **Mirroring the `ggwave_simple` API exactly.** The AHK `DllCall` model and most of
  chunking/compression survived untouched; the swap stayed surgical.

## Decisions to revisit
- The mono-over-stereo bridging "just works" via the OS but is fragile (needs both channels
  wired). A stereo-aware wrapper using one explicit channel would make single-cable runs
  possible and remove a footgun.
- `-1` ("system default") device id is silently broken on Linux (becomes `plughw:-1,0`).
  Either map `<0` → `NULL`/`"default"`, or require explicit indices.

---

## Learning points (reusable)

**Data-over-sound**
- Expect demod garbage around frames (carrier ramp-up, spurious locks); make app-layer
  framing self-synchronising and back it with a CRC.
- Tag request vs response and refuse to act on your own echo — cross-talk/self-loop is the
  default, not the exception.
- Acoustic links smear closely-spaced FSK tones (reverb/HΩ response); a wired line-level
  path is night-and-day. Tone *separation* matters more than raw level.

**Audio I/O**
- Never emit audio one symbol per device write — coalesce into large buffers, or per-write
  OS/timer latency dominates and throughput collapses (baud becomes irrelevant).
- Mind mono vs stereo and how the OS up/down-mixes; wire all channels the device exposes.
- Know your OS audio routing: ALSA `default` ≠ your USB card; USB card indices drift;
  Windows "Listen to this device" silently creates loopbacks.

**Process**
- Validate the *real* path, not a stand-in loopback.
- Keep a reference decoder and a spectral tool in the kit; they convert opinions into facts.
- Maintain a living testing/gotcha doc during bring-up — it paid for itself this session.

---

## Status & what's next

**Done:** minimodem cutover functionally validated end-to-end over wired UCA202s — `test`
round-trips, echo reply returns intact, `RECV_OK` both ends, 1200 baud.

**Outstanding (follow-ups, not blockers):**
1. CRC + induced-corruption retransmit test; baud sweep (1200/4800/9600 — likely much higher
   works on the wire now).
2. Retire `AHK/ggwave_simple.dll` + `AHK/SDL2.dll` now that the cutover is proven.
3. Re-enable compression (LZNT1 + Base62), gated behind an AHK↔Python cross-impl check.
4. Fix the `-1`→`"default"` Linux device bug.
5. Delete legacy `pyaudio`/`ggwave` scripts (`testing-audio.py`, `test-output-audio.py`).
6. v2: tone-override (acoustic robustness), audio source auto-recognition + level
   calibration, chunking for long payloads, optional FEC.
