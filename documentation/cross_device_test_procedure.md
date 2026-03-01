# Cross-Device Integration Test Procedure

End-to-end verification of the minimodem FSK audio pipe between the Windows PC
(AHK frontend) and the Raspberry Pi (Python backend).

---

## 1. Prerequisites

### Hardware

| Item | Notes |
|------|-------|
| Windows PC | Running AutoHotkey v2.0 |
| Raspberry Pi (or Linux SBC) | Debian-based OS recommended |
| USB audio interface **or** USB speaker + USB microphone | Class-compliant, no drivers needed on Linux |
| Two audio cables (TRS or 3.5 mm) | One for each direction (PC->Pi, Pi->PC) |

If using a single USB speaker/mic for testing, only one direction can be tested
at a time unless the device supports full-duplex (simultaneous playback and capture).

### Software — PC side

- AutoHotkey v2.0 installed.
- `minimodem_simple.dll` and its runtime dependencies built and collected into `AHK/`:
  - `minimodem_simple.dll`
  - `libfftw3f-3.dll`
  - `libportaudio-2.dll`
  - `libgcc_s_seh-1.dll` (if dynamically linked)
  - `libwinpthread-1.dll` (if dynamically linked)
- Build with MSYS2 MINGW64 if not already done:
  ```bash
  # In MSYS2 MINGW64 shell
  cd minimodem-wrapper
  bash build.sh
  bash collect_dlls.sh
  ```

### Software — Pi side

- `minimodem` installed:
  ```bash
  sudo apt update && sudo apt install -y minimodem
  ```
- Python 3.8+ with the backend dependencies:
  ```bash
  cd python-backend
  pip install -r requirements.txt   # if requirements.txt exists
  ```
- Verify minimodem is reachable:
  ```bash
  which minimodem
  minimodem --version
  ```

---

## 2. Hardware Setup Checklist

### Audio connections

For full-duplex (simultaneous send/receive), two cables are needed:

```
PC line-out  ------>  Pi line-in    (PC transmits to Pi)
Pi line-out  ------>  PC line-in    (Pi transmits to PC)
```

If using USB audio interfaces on both sides, connect:
- PC USB audio interface output -> Pi USB audio interface input
- Pi USB audio interface output -> PC USB audio interface input

### Volume calibration

Volume levels that are too low cause decoding failures; too high causes clipping
and distortion. Calibrate each direction independently.

**PC side (Windows):**
1. Open Sound Settings > Output device — select the USB audio interface.
2. Set output volume to ~50-70%.
3. Open Sound Settings > Input device — select the USB audio interface.
4. Set input level to ~70-80%.

**Pi side (Linux):**
1. List mixer controls:
   ```bash
   amixer -c 1 scontrols
   ```
2. Set playback volume:
   ```bash
   amixer -c 1 set 'Speaker' 70%
   # or whichever control name appears for your device
   ```
3. Set capture volume:
   ```bash
   amixer -c 1 set 'Mic' 80%
   ```

### Verify the audio path exists

**Pi -> PC direction (Pi transmits, PC listens):**

On the Pi, generate a test tone:
```bash
speaker-test -D hw:1 -t sine -f 1200 -l 1
```
On the PC, open any audio recording app (e.g., Audacity) and verify you see
a sine wave on the input from the USB interface.

**PC -> Pi direction (PC transmits, Pi listens):**

On the PC, play a tone through the USB output (e.g., an online tone generator
at 1200 Hz). On the Pi, record briefly and verify:
```bash
arecord -D hw:1 -f S16_LE -r 48000 -c 1 -d 3 /tmp/test_capture.wav
aplay /tmp/test_capture.wav
```
You should hear the tone played back.

---

## 3. Pi-Side Setup

### Find ALSA devices

```bash
# List capture (input) devices
arecord -l

# List playback (output) devices
aplay -l
```

Note the card and device numbers. For example, if your USB interface is card 1,
device 0, the ALSA device name is `hw:1` or `hw:1,0`.

You can also use the backend's built-in device listing:
```bash
cd python-backend
python3 backend.py --list
```

### Start the backend

```bash
cd python-backend
python3 backend.py --baud-rate 1200 --alsa-dev hw:1
```

Replace `hw:1` with your actual ALSA device. Omit `--alsa-dev` to use the
system default.

The backend will print log output to the console and to `python-backend/backend_log.txt`.
It uses `TestPipeline` by default, which echoes back the received message content.

Leave this terminal running.

---

## 4. PC-Side Setup

### Verify DLLs are in place

Check that the following files exist in the `AHK/` directory:
- `minimodem_simple.dll`
- `libfftw3f-3.dll`
- `libportaudio-2.dll`

### Launch the frontend

Run `AHK/main_dll.ahk` with AutoHotkey v2.0.

1. The device selection dialog will appear. Select:
   - **Speaker (output):** the USB audio interface connected to the Pi.
   - **Microphone (input):** the USB audio interface receiving from the Pi.
   - **Baud rate:** 1200 (must match the Pi backend).
2. Click OK to initialise.

The main GUI window will appear with an input text box and a send button.

---

## 5. Single-Device Loopback Pre-Tests

**Run these before attempting cross-device tests.** They verify that the
transport layer works on each machine independently. You need an audio loopback
(cable from line-out back to line-in on the same device, or a virtual audio cable).

### PC loopback

1. Connect the PC's USB audio output back to its own input.
2. Run the loopback test script:
   ```
   AHK\test_minimodem.ahk
   ```
3. The script runs three tests:
   - Test 1: Short JSON round-trip
   - Test 2: Empty poll (receive returns 0 when idle)
   - Test 3: Longer payload (~500 chars) round-trip
4. All three tests should pass. If Test 1 and Test 3 fail but Test 2 passes,
   the audio loopback is not working.

### Pi loopback

1. Connect the Pi's USB audio output back to its own input.
2. Run the loopback test script:
   ```bash
   cd python-backend
   python3 test_transport.py --baud-rate 1200 --alsa-dev hw:1
   ```
3. The script runs four tests:
   - Test 1: Subprocess health (RX and TX processes alive)
   - Test 2: Send without crash
   - Test 3: Loopback receive (round-trip of short JSON)
   - Test 4: Multiple messages in order
4. Tests 1-2 should always pass. Tests 3-4 require a functioning loopback cable.

**Do not proceed to cross-device tests until both loopback tests pass.**

---

## 6. Test Sequence

### Test A: PC -> Pi (one-way send)

**Goal:** Verify the AHK frontend can transmit a message that the Pi backend
receives and decodes.

1. On the PC, type a short test message in the AHK GUI input box:
   ```
   Test message from PC to Pi
   ```
2. Click Send.
3. On the Pi, watch the backend console output. You should see a `[RECV_RAW]`
   log line containing the message.
4. Also check `python-backend/backend_log.txt`:
   ```bash
   tail -20 python-backend/backend_log.txt
   ```
5. **Pass criteria:** The `[RECV_RAW]` log entry contains the sent message content
   (wrapped in the JSON chunk envelope).

**If this fails:** See the Debugging Guide (Section 7). The PC -> Pi audio path
is broken.

### Test B: Pi -> PC (backend response)

**Goal:** Verify the backend can transmit a response that the AHK frontend
receives and displays.

This test follows naturally from Test A, because the `TestPipeline` automatically
echoes back a response.

1. After sending the message in Test A, watch the AHK GUI for a response to
   appear in the output/response area.
2. On the PC, check the AHK log file `AHK/ggwave_log.txt` for received data:
   ```
   (Open ggwave_log.txt in a text editor and look for [RECV] entries)
   ```
   Note: The AHK log file is currently named `ggwave_log.txt` (legacy naming
   from before the minimodem migration).

3. **Pass criteria:** The AHK frontend displays a response containing the
   echoed content from the backend.

**If this fails but Test A passed:** The Pi -> PC audio path is broken. The
backend is processing messages but the response is not reaching the PC.

### Test C: Full pipeline round-trip (short message)

**Goal:** Verify a short radiology draft completes the full encode -> transmit ->
process -> respond -> decode cycle.

1. In the AHK GUI, enter a short radiology draft:
   ```
   CT abdomen pelvis with contrast. 5mm gallstone. No biliary dilatation. Liver normal. No free fluid.
   ```
2. Click Send.
3. Wait for the response (the `TestPipeline` echoes the content back; with a
   real `LLMPipeline` this would be a formatted report).
4. **Pass criteria:**
   - The Pi backend logs show the full message received without corruption.
   - The AHK frontend displays the response without corruption.
   - Round-trip completes within a reasonable time (under 60 seconds at 1200 baud
     for a short message).

### Test D: Chunked message round-trip (long message)

**Goal:** Verify that messages exceeding `CHUNK_DATA_SIZE` (1500 chars) are
correctly chunked, transmitted, and reassembled on both sides.

1. Prepare a long test message (>1500 characters). Example — paste this into
   the AHK GUI input:
   ```
   CT chest abdomen pelvis with IV contrast. Clinical history: 65 year old male
   with weight loss and abdominal pain. Comparison: CT from 12 months ago.
   Chest: No pulmonary embolism. Scattered ground glass opacities in both lower
   lobes, likely atelectasis vs early infection. No pleural effusion. Heart size
   normal. No pericardial effusion. Mediastinal lymphadenopathy with the largest
   node measuring 2.1cm in the subcarinal station. Abdomen: Liver contains
   multiple hypodense lesions, the largest in segment 6 measuring 3.2 x 2.8cm,
   suspicious for metastases. No biliary dilatation. Gallbladder is
   unremarkable. Spleen is normal in size. Pancreas demonstrates a 1.5cm
   hypodense lesion in the pancreatic head, concerning for primary malignancy.
   No pancreatic duct dilatation. Both kidneys are normal. No hydronephrosis.
   Adrenal glands are normal. Aorta is normal in calibre. No significant
   atherosclerotic disease. Pelvis: Bladder is normal. No pelvic
   lymphadenopathy. No free fluid. Bones: Sclerotic lesion in L3 vertebral
   body measuring 1.2cm, suspicious for metastasis. No acute fracture.
   Degenerative changes in the lumbar spine. Soft tissues are unremarkable.
   Impression: 1. Pancreatic head mass with multiple liver lesions and L3 bone
   lesion, concerning for pancreatic malignancy with hepatic and osseous
   metastases. 2. Mediastinal lymphadenopathy, may represent nodal metastases.
   3. Bilateral lower lobe ground glass opacities.
   ```
2. Click Send.
3. On the Pi, observe the backend logs. You should see multiple `[RECV_RAW]`
   entries (one per chunk), followed by a reassembly message when all chunks
   arrive.
4. Wait for the response to appear in the AHK frontend.
5. **Pass criteria:**
   - All chunks are received on the Pi (check log for chunk count `cc` and
     chunk indices `ci`).
   - The reassembled message matches what was sent (no truncation, no corruption).
   - The response is chunked back to the PC and reassembled correctly.
   - No retransmission requests were needed (check logs for `[RETX]` entries).

**Expected timing at 1200 baud:** A 1500-character payload takes roughly
12-15 seconds to transmit. A 1500+ character message that requires 2 chunks
will take approximately 25-35 seconds for the full round-trip (send + process +
respond).

---

## 7. Debugging Guide

### Test each direction independently with minimodem CLI

If the full system is not working, isolate the problem by testing raw minimodem
communication outside of the application.

**PC -> Pi (manual test):**

On the Pi, start minimodem in receive mode:
```bash
minimodem --rx 1200 -A --alsa-dev hw:1
```

On the PC, you cannot easily run minimodem CLI (it is Linux-only), but you can
use the AHK test script or the DLL directly. Alternatively, generate a WAV file
with minimodem on another Linux machine and play it from the PC.

**Pi -> PC (manual test):**

On the Pi, send a test string:
```bash
echo "Hello from Pi" | minimodem --tx 1200 -A --alsa-dev hw:1
```

On the PC, check if the AHK loopback test or main GUI receives data.

### Capture raw audio for analysis

**On the Pi:**
```bash
# Record 10 seconds of raw audio from the USB interface
arecord -D hw:1 -f S16_LE -r 48000 -c 1 -d 10 /tmp/capture.wav

# Play it back to verify content
aplay /tmp/capture.wav

# Try decoding the captured audio with minimodem
minimodem --rx 1200 -f /tmp/capture.wav
```

**On the PC:**
Use Audacity or any recording tool to capture audio from the USB input device.
Look for the FSK tones visually in the spectrogram view — 1200 baud Bell 202
uses 1200 Hz (mark) and 2200 Hz (space).

### Common failure modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| No audio reaching Pi | Wrong output device on PC, cable disconnected, volume at zero | Check Windows sound settings, verify cable with tone test |
| No audio reaching PC | Wrong ALSA device, cable disconnected, Pi volume at zero | Check `aplay -l`, verify cable with `speaker-test` |
| Audio reaches Pi but minimodem decodes nothing | Volume too low or too high (clipping), baud rate mismatch | Adjust volume, ensure both sides use `--baud-rate 1200` |
| Partial data / garbled output | Clipping, electrical noise, sample rate mismatch | Lower volume, use shorter cables, verify 48000 Hz sample rate |
| Chunks arrive but reassembly fails | Baud rate mismatch between sides, dropped chunks | Check both configs use same baud rate, check for `[RETX]` in logs |
| DLL fails to load on PC | Missing runtime DLLs | Re-run `collect_dlls.sh`, verify all DLLs are in `AHK/` |
| `minimodem` not found on Pi | Not installed | `sudo apt install minimodem` |
| Backend starts but RX process dies immediately | Wrong ALSA device name | Run `arecord -l` and use correct `hw:X` identifier |
| Everything works in loopback but not cross-device | Cable wired to wrong jacks (output->output) | Verify output->input on each cable |

### Log file locations

| Machine | Log file | Contents |
|---------|----------|----------|
| PC (Windows) | `AHK/ggwave_log.txt` | AHK frontend send/receive events, chunk assembly, errors |
| Pi (Linux) | `python-backend/backend_log.txt` | Backend receive, pipeline processing, chunk send, errors |

Note: The AHK log file is named `ggwave_log.txt` for legacy reasons (defined in
`AHK/include/config.ahk` as `LOG_FILE`). It logs minimodem operations despite the
filename.

### Useful diagnostic commands (Pi)

```bash
# Check if minimodem RX/TX subprocesses are running
ps aux | grep minimodem

# Monitor backend log in real-time
tail -f python-backend/backend_log.txt

# Check ALSA device details
cat /proc/asound/cards
arecord -D hw:1 --dump-hw-params /dev/null 2>&1

# Test that minimodem can receive anything at all
minimodem --rx 1200 -A --alsa-dev hw:1
# (send audio from PC, you should see decoded text appear)
```

---

## 8. Success Criteria

The cross-device integration test passes when **all four tests** (A through D)
complete successfully:

- [  ] **Test A:** PC sends a message, Pi backend logs it correctly.
- [  ] **Test B:** Pi backend responds, AHK frontend displays the response.
- [  ] **Test C:** Short radiology draft completes a full round-trip without corruption.
- [  ] **Test D:** Long message (>1500 chars) is chunked, transmitted, reassembled, and
  responded to correctly on both sides.

If all four pass, the minimodem migration is functionally complete for cross-device
communication.
