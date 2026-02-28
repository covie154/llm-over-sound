# Minimodem Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace ggwave audio transport with minimodem FSK core extracted into a native Windows DLL, and subprocess on the Pi.

**Architecture:** Extract `fsk.c`, `databits_ascii.c`, and `simple-tone-generator.c` from minimodem source into a new `minimodem-wrapper/` project. Wrap with PortAudio for audio I/O. Expose a C API matching the shape of `ggwave_simple.dll`. On Pi, use minimodem CLI via subprocess.

**Tech Stack:** C99, FFTW3f, PortAudio, pthreads, MSYS2/MinGW-w64, CMake, AutoHotkey v2, Python 3

**Reference implementation:** `quiet-wrapper/quiet_simple.c` (597 lines) — same PortAudio + mutex pattern we follow here.

**Design doc:** `docs/plans/2026-02-28-minimodem-migration-design.md`

---

## Phase 1: Setup & Build System

### Task 1: Create minimodem-wrapper directory and copy FSK core files

**Files:**
- Create: `minimodem-wrapper/fsk.h`
- Create: `minimodem-wrapper/fsk.c`
- Create: `minimodem-wrapper/databits.h`
- Create: `minimodem-wrapper/databits_ascii.c`

**Step 1: Create directory**

```bash
mkdir -p minimodem-wrapper
```

**Step 2: Copy FSK core files from minimodem submodule**

```bash
cp minimodem/src/fsk.h minimodem-wrapper/fsk.h
cp minimodem/src/fsk.c minimodem-wrapper/fsk.c
cp minimodem/src/databits.h minimodem-wrapper/databits.h
cp minimodem/src/databits_ascii.c minimodem-wrapper/databits_ascii.c
```

**Step 3: Patch fsk.h to remove simpleaudio dependency**

The original `fsk.h` may include `simpleaudio.h`. Remove that include if present — the FSK core only needs FFTW3f and standard C headers.

Verify with: `grep -n "simpleaudio" minimodem-wrapper/fsk.h minimodem-wrapper/fsk.c`

If found, remove those includes. The FSK functions operate on `float *samples` buffers, not audio device handles.

**Step 4: Patch databits.h to keep only ASCII8**

The original `databits.h` declares Baudot, CallerID, UIC, binary encoders. We only need ASCII8. Strip the others to avoid needing their `.c` files. Keep:
- `bit_reverse()`
- `bit_window()`
- `databits_encode_ascii8()`
- `databits_decode_ascii8()`

**Step 5: Commit**

```bash
git add minimodem-wrapper/fsk.h minimodem-wrapper/fsk.c minimodem-wrapper/databits.h minimodem-wrapper/databits_ascii.c
git commit -m "feat(minimodem-wrapper): copy FSK core files from minimodem source"
```

---

### Task 2: Write adapted tone generator

**Files:**
- Create: `minimodem-wrapper/tone_generator.h`
- Create: `minimodem-wrapper/tone_generator.c`

The original `simple-tone-generator.c` writes to a `simpleaudio *sa_out` handle. We adapt it to write to a `float *buffer` instead.

**Step 1: Write tone_generator.h**

```c
#ifndef TONE_GENERATOR_H
#define TONE_GENERATOR_H

#include <stddef.h>

/* Initialize sine lookup table. Call once at startup.
 * sin_table_len: LUT size (0 = use sinf() directly, 4096 = typical)
 * mag: amplitude 0.0-1.0 */
void tone_generator_init(unsigned int sin_table_len, float mag);

/* Generate tone samples into a float buffer.
 * buf: output buffer (float32, -1.0 to 1.0)
 * tone_freq: frequency in Hz (0.0 = silence)
 * nsamples: number of samples to generate
 * sample_rate: audio sample rate in Hz
 * Returns: number of samples written (== nsamples) */
size_t tone_generate(float *buf, float tone_freq, size_t nsamples, float sample_rate);

/* Reset phase accumulator (call between independent transmissions) */
void tone_reset_phase(void);

#endif /* TONE_GENERATOR_H */
```

**Step 2: Write tone_generator.c**

Adapted from `minimodem/src/simple-tone-generator.c` (177 lines). Key change: output to `float *buf` instead of `simpleaudio_tone()` writing to an audio stream.

```c
#include "tone_generator.h"
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static float *sin_table_float = NULL;
static unsigned int sin_table_len = 0;
static float tone_mag = 1.0f;
static float sa_tone_cphase = 0.0f;

static float sin_lu_float(float phase_turns) {
    if (!sin_table_float)
        return tone_mag * sinf(2.0f * (float)M_PI * phase_turns);
    unsigned int idx = (unsigned int)(phase_turns * sin_table_len) % sin_table_len;
    return sin_table_float[idx];
}

void tone_generator_init(unsigned int new_sin_table_len, float mag) {
    tone_mag = mag;
    sa_tone_cphase = 0.0f;

    if (sin_table_float) {
        free(sin_table_float);
        sin_table_float = NULL;
    }
    sin_table_len = new_sin_table_len;

    if (sin_table_len > 0) {
        sin_table_float = malloc(sin_table_len * sizeof(float));
        for (unsigned int i = 0; i < sin_table_len; i++) {
            sin_table_float[i] = tone_mag * sinf(2.0f * (float)M_PI * i / sin_table_len);
        }
    }
}

size_t tone_generate(float *buf, float tone_freq, size_t nsamples, float sample_rate) {
    if (tone_freq == 0.0f) {
        memset(buf, 0, nsamples * sizeof(float));
        sa_tone_cphase = 0.0f;
        return nsamples;
    }

    float wave_nsamples = sample_rate / tone_freq;
    for (size_t i = 0; i < nsamples; i++) {
        float phase_turns = (float)i / wave_nsamples + sa_tone_cphase;
        buf[i] = sin_lu_float(phase_turns);
    }
    sa_tone_cphase = fmodf(sa_tone_cphase + (float)nsamples / wave_nsamples, 1.0f);
    return nsamples;
}

void tone_reset_phase(void) {
    sa_tone_cphase = 0.0f;
}
```

**Step 3: Commit**

```bash
git add minimodem-wrapper/tone_generator.h minimodem-wrapper/tone_generator.c
git commit -m "feat(minimodem-wrapper): add adapted tone generator (buffer output)"
```

---

### Task 3: Write DLL public header

**Files:**
- Create: `minimodem-wrapper/minimodem_simple.h`

**Step 1: Write minimodem_simple.h**

```c
#ifndef MINIMODEM_SIMPLE_H
#define MINIMODEM_SIMPLE_H

#include <stdint.h>

#ifdef _WIN32
#  ifdef MINIMODEM_SIMPLE_BUILD
#    define MINIMODEM_API __declspec(dllexport)
#  else
#    define MINIMODEM_API __declspec(dllimport)
#  endif
#else
#  define MINIMODEM_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Initialize the modem. Opens audio devices and starts background threads.
 * playbackDeviceId: PortAudio wrapper device index for output (-1 = default)
 * captureDeviceId:  PortAudio wrapper device index for input (-1 = default)
 * baud_rate:        FSK baud rate (1200, 2400, 4800, etc.)
 * Returns 0 on success, negative on error. */
MINIMODEM_API int minimodem_simple_init(int playbackDeviceId, int captureDeviceId, int baud_rate);

/* Clean up all resources. Stops threads, closes audio streams. */
MINIMODEM_API void minimodem_simple_cleanup(void);

/* Transmit binary data as FSK audio.
 * data: pointer to bytes to send
 * len:  number of bytes
 * Returns 0 on success, negative on error.
 * Non-blocking: queues waveform for background playback. */
MINIMODEM_API int minimodem_simple_send(const uint8_t *data, int len);

/* Check if a transmission is still in progress.
 * Returns 1 if transmitting, 0 if idle. */
MINIMODEM_API int minimodem_simple_is_transmitting(void);

/* Receive decoded data. Non-blocking.
 * buffer:     output buffer for received bytes
 * bufferSize: max bytes to write
 * Returns number of bytes received (0 if nothing available), negative on error. */
MINIMODEM_API int minimodem_simple_receive(uint8_t *buffer, int bufferSize);

/* Change baud rate. Reinitializes FSK parameters.
 * Returns 0 on success, negative on error. */
MINIMODEM_API int minimodem_simple_set_baud_rate(int baud_rate);

/* Get maximum recommended payload size per send() call.
 * With minimodem there is no hard per-frame limit — this returns a
 * practical maximum (e.g. 4096) for callers that need a bound. */
MINIMODEM_API int minimodem_simple_get_frame_len(void);

/* Device enumeration */
MINIMODEM_API int         minimodem_simple_get_playback_device_count(void);
MINIMODEM_API int         minimodem_simple_get_capture_device_count(void);
MINIMODEM_API const char* minimodem_simple_get_playback_device_name(int id);
MINIMODEM_API const char* minimodem_simple_get_capture_device_name(int id);

/* Get last error message (empty string if no error). */
MINIMODEM_API const char* minimodem_simple_get_error(void);

#ifdef __cplusplus
}
#endif

#endif /* MINIMODEM_SIMPLE_H */
```

**Step 2: Commit**

```bash
git add minimodem-wrapper/minimodem_simple.h
git commit -m "feat(minimodem-wrapper): add DLL public API header"
```

---

### Task 4: Write CMakeLists.txt and build scripts

**Files:**
- Create: `minimodem-wrapper/CMakeLists.txt`
- Create: `minimodem-wrapper/build.sh`
- Create: `minimodem-wrapper/collect_dlls.sh`

**Step 1: Write CMakeLists.txt**

Reference: `quiet-wrapper/CMakeLists.txt` (42 lines).

```cmake
cmake_minimum_required(VERSION 3.16)
project(minimodem_simple C)

set(CMAKE_C_STANDARD 99)

add_library(minimodem_simple SHARED
    minimodem_simple.c
    minimodem_simple.h
    fsk.c
    fsk.h
    tone_generator.c
    tone_generator.h
    databits_ascii.c
    databits.h
)

target_compile_definitions(minimodem_simple PRIVATE MINIMODEM_SIMPLE_BUILD)

# FFTW3f (single-precision float FFT)
find_library(FFTW3F_LIB NAMES fftw3f libfftw3f-3)
find_path(FFTW3F_INCLUDE fftw3.h)

# PortAudio
find_library(PORTAUDIO_LIB NAMES portaudio libportaudio-2)
find_path(PORTAUDIO_INCLUDE portaudio.h)

target_include_directories(minimodem_simple PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${FFTW3F_INCLUDE}
    ${PORTAUDIO_INCLUDE}
)

target_link_libraries(minimodem_simple PRIVATE
    ${FFTW3F_LIB}
    ${PORTAUDIO_LIB}
    pthread
    m
)

# Static-link MinGW runtime for portability
if(MINGW)
    target_link_options(minimodem_simple PRIVATE -static-libgcc)
endif()

set_target_properties(minimodem_simple PROPERTIES PREFIX "")
```

**Step 2: Write build.sh**

```bash
#!/bin/bash
# Build minimodem_simple.dll using MSYS2 MinGW-w64
# Run from MSYS2 MINGW64 shell

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"

echo "=== Installing dependencies ==="
pacman -S --needed --noconfirm \
    mingw-w64-x86_64-fftw \
    mingw-w64-x86_64-portaudio \
    mingw-w64-x86_64-cmake \
    mingw-w64-x86_64-gcc

echo "=== Configuring ==="
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
cmake -G "MinGW Makefiles" "$SCRIPT_DIR"

echo "=== Building ==="
mingw32-make -j$(nproc)

echo "=== Done ==="
echo "DLL at: $BUILD_DIR/minimodem_simple.dll"
```

**Step 3: Write collect_dlls.sh**

```bash
#!/bin/bash
# Collect runtime DLLs into AHK/ directory for portable deployment
# Run from MSYS2 MINGW64 shell after build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
AHK_DIR="$SCRIPT_DIR/../AHK"
MINGW_BIN="/mingw64/bin"

echo "=== Collecting DLLs ==="

cp "$BUILD_DIR/minimodem_simple.dll" "$AHK_DIR/"
cp "$MINGW_BIN/libfftw3f-3.dll"     "$AHK_DIR/"
cp "$MINGW_BIN/libportaudio-2.dll"   "$AHK_DIR/"

# MinGW runtime (only if not statically linked)
if ldd "$BUILD_DIR/minimodem_simple.dll" | grep -q "libgcc_s_seh"; then
    cp "$MINGW_BIN/libgcc_s_seh-1.dll"  "$AHK_DIR/"
fi
if ldd "$BUILD_DIR/minimodem_simple.dll" | grep -q "libwinpthread"; then
    cp "$MINGW_BIN/libwinpthread-1.dll"  "$AHK_DIR/"
fi

echo "=== DLLs collected in $AHK_DIR ==="
ls -la "$AHK_DIR"/*.dll
```

**Step 4: Commit**

```bash
chmod +x minimodem-wrapper/build.sh minimodem-wrapper/collect_dlls.sh
git add minimodem-wrapper/CMakeLists.txt minimodem-wrapper/build.sh minimodem-wrapper/collect_dlls.sh
git commit -m "feat(minimodem-wrapper): add CMake build system and scripts"
```

---

## Phase 2: DLL Implementation

### Task 5: Write minimodem_simple.c — global state and device enumeration

**Files:**
- Create: `minimodem-wrapper/minimodem_simple.c`

This is the largest file. We build it incrementally. This task covers the global state struct, PortAudio device mapping, and device enumeration API.

**Reference:** `quiet-wrapper/quiet_simple.c` lines 50-84 (state struct), 104-144 (device maps), 371-405 (enumeration API).

**Step 1: Write the global state struct and device mapping**

```c
#include "minimodem_simple.h"
#include "fsk.h"
#include "databits.h"
#include "tone_generator.h"

#include <portaudio.h>
#include <fftw3.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ---------- constants ---------- */
#define SAMPLE_RATE         48000.0f
#define PA_FRAMES_PER_BUF   1024
#define MAX_DEVICES          64
#define MAX_MESSAGE_LEN      8192
#define TX_RING_SIZE        (SAMPLE_RATE * 30) /* 30 sec max TX buffer */
#define RX_RING_SIZE        (SAMPLE_RATE * 2)  /* 2 sec RX ring buffer */
#define CONFIDENCE_THRESHOLD 1.5f
#define MAX_NOCONF_BITS      20
#define LEADER_BITS          2
#define TRAILER_BITS         2
#define TONE_TABLE_LEN       4096
#define TONE_AMPLITUDE       0.5f
#define MAX_ERROR_LEN        256

/* ---------- receive state machine ---------- */
typedef enum {
    RX_WAITING_FOR_CARRIER,
    RX_RECEIVING,
} rx_state_t;

/* ---------- decoded message queue ---------- */
typedef struct msg_node {
    uint8_t *data;
    int len;
    struct msg_node *next;
} msg_node_t;

/* ---------- global state ---------- */
static struct {
    /* audio */
    PaStream       *stream_out;
    PaStream       *stream_in;
    int             pa_initialized;

    /* FSK config */
    int             baud_rate;
    float           mark_freq;
    float           space_freq;
    float           filter_bw;
    unsigned int    bit_nsamples;     /* samples per bit */
    unsigned int    frame_nsamples;   /* samples per frame (start+data+stop) */

    /* FSK decoder */
    fsk_plan       *fskp;
    rx_state_t      rx_state;
    int             noconf_count;
    float           track_amplitude;
    uint8_t         rx_msg_buf[MAX_MESSAGE_LEN];
    int             rx_msg_len;

    /* RX ring buffer (PA callback -> decoder thread) */
    float          *rx_ring;
    volatile int    rx_ring_head;   /* written by PA callback */
    volatile int    rx_ring_tail;   /* read by decoder thread */
    int             rx_ring_size;

    /* TX ring buffer (send() -> PA callback) */
    float          *tx_ring;
    volatile int    tx_ring_head;   /* written by send() */
    volatile int    tx_ring_tail;   /* read by PA callback */
    int             tx_ring_size;

    /* decoder thread */
    pthread_t       decoder_thread;
    volatile int    decoder_running;

    /* decoded message queue */
    msg_node_t     *msg_queue_head;
    msg_node_t     *msg_queue_tail;
    pthread_mutex_t msg_mutex;

    /* device mapping: wrapper index -> PA device index */
    int             playback_map[MAX_DEVICES];
    int             capture_map[MAX_DEVICES];
    char            playback_names[MAX_DEVICES][256];
    char            capture_names[MAX_DEVICES][256];
    int             playback_count;
    int             capture_count;

    /* error */
    char            last_error[MAX_ERROR_LEN];
} g_state;

/* ---------- helpers ---------- */
static void set_error(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(g_state.last_error, MAX_ERROR_LEN, fmt, ap);
    va_end(ap);
}

/* ---------- FSK parameter calculation ---------- */
/* Ported from minimodem/src/minimodem.c lines 900-934 */
static void calc_fsk_params(int baud_rate) {
    g_state.baud_rate = baud_rate;

    if (baud_rate >= 400) {
        /* Bell 202 family */
        float shift = -(float)baud_rate * 5.0f / 6.0f;
        g_state.mark_freq  = (float)baud_rate / 2.0f + 600.0f;
        g_state.space_freq = g_state.mark_freq - shift;
        g_state.filter_bw  = 200.0f;
    } else if (baud_rate >= 100) {
        /* Bell 103 family */
        g_state.mark_freq  = 1270.0f;
        g_state.space_freq = 1070.0f;
        g_state.filter_bw  = 50.0f;
    } else {
        /* RTTY */
        g_state.mark_freq  = 1585.0f;
        g_state.space_freq = 1415.0f;
        g_state.filter_bw  = 10.0f;
    }

    g_state.bit_nsamples = (unsigned int)(SAMPLE_RATE / (float)baud_rate + 0.5f);
    /* frame = 1 start + 8 data + 1 stop = 10 bits */
    g_state.frame_nsamples = g_state.bit_nsamples * 10;
}

/* ---------- PortAudio device enumeration ---------- */
static void build_device_maps(void) {
    g_state.playback_count = 0;
    g_state.capture_count = 0;

    int n = Pa_GetDeviceCount();
    for (int i = 0; i < n && i < MAX_DEVICES; i++) {
        const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
        if (!info) continue;

        if (info->maxOutputChannels > 0 && g_state.playback_count < MAX_DEVICES) {
            int idx = g_state.playback_count;
            g_state.playback_map[idx] = i;
            snprintf(g_state.playback_names[idx], 256, "%s", info->name);
            g_state.playback_count++;
        }
        if (info->maxInputChannels > 0 && g_state.capture_count < MAX_DEVICES) {
            int idx = g_state.capture_count;
            g_state.capture_map[idx] = i;
            snprintf(g_state.capture_names[idx], 256, "%s", info->name);
            g_state.capture_count++;
        }
    }
}

static int ensure_pa(void) {
    if (!g_state.pa_initialized) {
        PaError err = Pa_Initialize();
        if (err != paNoError) {
            set_error("Pa_Initialize failed: %s", Pa_GetErrorText(err));
            return -1;
        }
        g_state.pa_initialized = 1;
        build_device_maps();
    }
    return 0;
}

/* ---------- device enumeration API ---------- */
MINIMODEM_API int minimodem_simple_get_playback_device_count(void) {
    if (ensure_pa() < 0) return 0;
    return g_state.playback_count;
}

MINIMODEM_API int minimodem_simple_get_capture_device_count(void) {
    if (ensure_pa() < 0) return 0;
    return g_state.capture_count;
}

MINIMODEM_API const char* minimodem_simple_get_playback_device_name(int id) {
    if (id < 0 || id >= g_state.playback_count) return "";
    return g_state.playback_names[id];
}

MINIMODEM_API const char* minimodem_simple_get_capture_device_name(int id) {
    if (id < 0 || id >= g_state.capture_count) return "";
    return g_state.capture_names[id];
}

MINIMODEM_API const char* minimodem_simple_get_error(void) {
    return g_state.last_error;
}

MINIMODEM_API int minimodem_simple_get_frame_len(void) {
    return 4096; /* no hard limit; return practical max */
}
```

**Step 2: Verify compilation (headers only, no link)**

```bash
cd minimodem-wrapper/build && cmake .. && mingw32-make 2>&1 | head -30
```

Expected: Linker errors for missing functions (tx/rx callbacks, init, cleanup) but no compile errors.

**Step 3: Commit**

```bash
git add minimodem-wrapper/minimodem_simple.c
git commit -m "feat(minimodem-wrapper): add global state, device enum, FSK param calc"
```

---

### Task 6: Add PortAudio callbacks and ring buffer I/O

**Files:**
- Modify: `minimodem-wrapper/minimodem_simple.c`

Add the PortAudio stream callbacks and ring buffer read/write helpers. These sit between PortAudio's audio thread and our application threads.

**Step 1: Add ring buffer helpers** (insert before device enumeration API)

```c
/* ---------- ring buffer helpers ---------- */
/* Single-producer single-consumer lock-free ring buffer for float samples */

static int ring_available_read(volatile int head, volatile int tail, int size) {
    int avail = head - tail;
    if (avail < 0) avail += size;
    return avail;
}

static int ring_available_write(volatile int head, volatile int tail, int size) {
    return size - 1 - ring_available_read(head, tail, size);
}

static void ring_write(float *ring, volatile int *head, int size,
                       const float *data, int count) {
    int h = *head;
    for (int i = 0; i < count; i++) {
        ring[h] = data[i];
        h = (h + 1) % size;
    }
    *head = h;
}

static void ring_read(float *ring, volatile int *tail, int size,
                      float *data, int count) {
    int t = *tail;
    for (int i = 0; i < count; i++) {
        data[i] = ring[t];
        t = (t + 1) % size;
    }
    *tail = t;
}
```

**Step 2: Add PortAudio callbacks** (insert after ring buffer helpers)

```c
/* ---------- PortAudio callbacks ---------- */

/* RX callback: capture audio -> RX ring buffer */
static int pa_rx_callback(const void *input, void *output,
                          unsigned long frameCount,
                          const PaStreamCallbackTimeInfo *timeInfo,
                          PaStreamCallbackFlags statusFlags,
                          void *userData) {
    (void)output; (void)timeInfo; (void)statusFlags; (void)userData;
    const float *in = (const float *)input;
    if (!in) return paContinue;

    int avail = ring_available_write(g_state.rx_ring_head,
                                     g_state.rx_ring_tail,
                                     g_state.rx_ring_size);
    int to_write = (int)frameCount < avail ? (int)frameCount : avail;
    if (to_write > 0) {
        ring_write(g_state.rx_ring, &g_state.rx_ring_head,
                   g_state.rx_ring_size, in, to_write);
    }
    return paContinue;
}

/* TX callback: TX ring buffer -> playback audio */
static int pa_tx_callback(const void *input, void *output,
                          unsigned long frameCount,
                          const PaStreamCallbackTimeInfo *timeInfo,
                          PaStreamCallbackFlags statusFlags,
                          void *userData) {
    (void)input; (void)timeInfo; (void)statusFlags; (void)userData;
    float *out = (float *)output;

    int avail = ring_available_read(g_state.tx_ring_head,
                                    g_state.tx_ring_tail,
                                    g_state.tx_ring_size);
    int to_read = (int)frameCount < avail ? (int)frameCount : avail;

    if (to_read > 0) {
        ring_read(g_state.tx_ring, &g_state.tx_ring_tail,
                  g_state.tx_ring_size, out, to_read);
    }
    /* silence for remaining frames */
    if (to_read < (int)frameCount) {
        memset(out + to_read, 0, ((int)frameCount - to_read) * sizeof(float));
    }
    return paContinue;
}
```

**Step 3: Commit**

```bash
git add minimodem-wrapper/minimodem_simple.c
git commit -m "feat(minimodem-wrapper): add ring buffers and PortAudio callbacks"
```

---

### Task 7: Add transmit path

**Files:**
- Modify: `minimodem-wrapper/minimodem_simple.c`

Implements `minimodem_simple_send()`. Pre-generates the full FSK waveform (leader + framed bytes + trailer) into a temp buffer, then copies to the TX ring.

**Step 1: Add transmit helper** (insert after PA callbacks)

```c
/* ---------- transmit ---------- */

/* Generate FSK waveform for one byte (1 start + 8 data LSB-first + 1 stop).
 * Returns number of samples written. */
static size_t fsk_encode_byte(float *buf, uint8_t byte) {
    size_t pos = 0;

    /* start bit = space */
    pos += tone_generate(buf + pos, g_state.space_freq,
                         g_state.bit_nsamples, SAMPLE_RATE);

    /* 8 data bits, LSB first */
    for (int i = 0; i < 8; i++) {
        float freq = (byte & (1 << i)) ? g_state.mark_freq : g_state.space_freq;
        pos += tone_generate(buf + pos, freq,
                             g_state.bit_nsamples, SAMPLE_RATE);
    }

    /* stop bit = mark */
    pos += tone_generate(buf + pos, g_state.mark_freq,
                         g_state.bit_nsamples, SAMPLE_RATE);

    return pos;
}

MINIMODEM_API int minimodem_simple_send(const uint8_t *data, int len) {
    if (!g_state.stream_out || len <= 0 || !data) {
        set_error("send: not initialized or invalid args");
        return -1;
    }

    /* calculate total waveform size:
     * leader(2 bits) + len*(10 bits/byte) + trailer(2 bits) */
    size_t total_bits = LEADER_BITS + (size_t)len * 10 + TRAILER_BITS;
    size_t total_samples = total_bits * g_state.bit_nsamples;

    float *waveform = malloc(total_samples * sizeof(float));
    if (!waveform) {
        set_error("send: malloc failed for %zu samples", total_samples);
        return -1;
    }

    size_t pos = 0;

    /* leader: mark tone */
    pos += tone_generate(waveform + pos, g_state.mark_freq,
                         g_state.bit_nsamples * LEADER_BITS, SAMPLE_RATE);

    /* data bytes */
    for (int i = 0; i < len; i++) {
        pos += fsk_encode_byte(waveform + pos, data[i]);
    }

    /* trailer: mark tone */
    pos += tone_generate(waveform + pos, g_state.mark_freq,
                         g_state.bit_nsamples * TRAILER_BITS, SAMPLE_RATE);

    /* queue to TX ring */
    int avail = ring_available_write(g_state.tx_ring_head,
                                     g_state.tx_ring_tail,
                                     g_state.tx_ring_size);
    if ((int)pos > avail) {
        free(waveform);
        set_error("send: TX ring full (%d avail, %zu needed)", avail, pos);
        return -1;
    }

    ring_write(g_state.tx_ring, &g_state.tx_ring_head,
               g_state.tx_ring_size, waveform, (int)pos);

    free(waveform);
    return 0;
}

MINIMODEM_API int minimodem_simple_is_transmitting(void) {
    return ring_available_read(g_state.tx_ring_head,
                               g_state.tx_ring_tail,
                               g_state.tx_ring_size) > 0 ? 1 : 0;
}
```

**Step 2: Commit**

```bash
git add minimodem-wrapper/minimodem_simple.c
git commit -m "feat(minimodem-wrapper): add FSK transmit path"
```

---

### Task 8: Add receive path (decoder thread with state machine)

**Files:**
- Modify: `minimodem-wrapper/minimodem_simple.c`

The decoder thread continuously pulls samples from the RX ring buffer, runs `fsk_find_frame()`, and accumulates decoded bytes. Carrier loss triggers message finalization.

**Step 1: Add decoder thread and message queue helpers**

```c
/* ---------- message queue helpers ---------- */

static void msg_queue_push(const uint8_t *data, int len) {
    msg_node_t *node = malloc(sizeof(msg_node_t));
    if (!node) return;
    node->data = malloc(len);
    if (!node->data) { free(node); return; }
    memcpy(node->data, data, len);
    node->len = len;
    node->next = NULL;

    pthread_mutex_lock(&g_state.msg_mutex);
    if (g_state.msg_queue_tail) {
        g_state.msg_queue_tail->next = node;
    } else {
        g_state.msg_queue_head = node;
    }
    g_state.msg_queue_tail = node;
    pthread_mutex_unlock(&g_state.msg_mutex);
}

static msg_node_t *msg_queue_pop(void) {
    pthread_mutex_lock(&g_state.msg_mutex);
    msg_node_t *node = g_state.msg_queue_head;
    if (node) {
        g_state.msg_queue_head = node->next;
        if (!g_state.msg_queue_head) g_state.msg_queue_tail = NULL;
    }
    pthread_mutex_unlock(&g_state.msg_mutex);
    return node;
}

/* ---------- decoder thread ---------- */

/* Build expect_bits_string for 8N1 framing: "0dddddddd1"
 * 0 = start (space), d = data (don't care), 1 = stop (mark) */
static const char *EXPECT_BITS_8N1 = "0dddddddd1";

static void *decoder_thread_func(void *arg) {
    (void)arg;

    /* working buffer: need at least 2x frame_nsamples for sliding window */
    unsigned int buf_size = g_state.frame_nsamples * 4;
    float *samplebuf = calloc(buf_size, sizeof(float));
    if (!samplebuf) return NULL;

    unsigned int nsamples = 0; /* valid samples in buffer */
    unsigned int overscan = g_state.bit_nsamples / 2;

    while (g_state.decoder_running) {
        /* pull available samples from RX ring */
        int avail = ring_available_read(g_state.rx_ring_head,
                                        g_state.rx_ring_tail,
                                        g_state.rx_ring_size);
        if (avail == 0) {
            Pa_Sleep(1); /* 1ms sleep to avoid busy-wait */
            continue;
        }

        /* how much room in our working buffer? */
        int room = (int)buf_size - (int)nsamples;
        int to_read = avail < room ? avail : room;
        if (to_read <= 0) {
            /* buffer full, shouldn't happen — shift and retry */
            unsigned int shift = buf_size / 2;
            memmove(samplebuf, samplebuf + shift, (nsamples - shift) * sizeof(float));
            nsamples -= shift;
            continue;
        }

        ring_read(g_state.rx_ring, &g_state.rx_ring_tail,
                  g_state.rx_ring_size, samplebuf + nsamples, to_read);
        nsamples += to_read;

        /* need at least one full frame + overscan */
        if (nsamples < g_state.frame_nsamples + overscan)
            continue;

        /* try to decode a frame */
        unsigned long long bits = 0;
        float ampl = 0.0f;
        unsigned int frame_start = 0;

        unsigned int try_max = g_state.bit_nsamples;
        unsigned int try_step = g_state.bit_nsamples / 4;
        if (try_step < 1) try_step = 1;

        float confidence = fsk_find_frame(
            g_state.fskp,
            samplebuf,
            g_state.frame_nsamples,
            0,              /* try_first_sample */
            try_max,        /* try_max_nsamples */
            try_step,       /* try_step_nsamples */
            0.0f,           /* try_confidence_search_limit (0=exhaustive) */
            EXPECT_BITS_8N1,
            &bits, &ampl, &frame_start
        );

        if (confidence >= CONFIDENCE_THRESHOLD) {
            /* good frame */
            g_state.noconf_count = 0;

            if (g_state.rx_state == RX_WAITING_FOR_CARRIER) {
                g_state.rx_state = RX_RECEIVING;
                g_state.track_amplitude = ampl;
                g_state.rx_msg_len = 0;
            }

            if (g_state.rx_state == RX_RECEIVING) {
                /* update amplitude tracking */
                g_state.track_amplitude = (g_state.track_amplitude + ampl) / 2.0f;

                /* extract data byte: strip start bit, take 8 data bits */
                uint8_t byte = (uint8_t)((bits >> 1) & 0xFF);

                if (g_state.rx_msg_len < MAX_MESSAGE_LEN) {
                    g_state.rx_msg_buf[g_state.rx_msg_len++] = byte;
                }
            }

            /* advance past this frame */
            unsigned int advance = frame_start + g_state.frame_nsamples - overscan;
            if (advance > 0 && advance < nsamples) {
                memmove(samplebuf, samplebuf + advance,
                        (nsamples - advance) * sizeof(float));
                nsamples -= advance;
            } else {
                nsamples = 0;
            }
        } else {
            /* low confidence */
            g_state.noconf_count++;

            if (g_state.rx_state == RX_RECEIVING &&
                (g_state.noconf_count >= MAX_NOCONF_BITS ||
                 (ampl > 0 && ampl < g_state.track_amplitude * 0.25f))) {
                /* carrier lost — finalize message */
                if (g_state.rx_msg_len > 0) {
                    msg_queue_push(g_state.rx_msg_buf, g_state.rx_msg_len);
                }
                g_state.rx_state = RX_WAITING_FOR_CARRIER;
                g_state.rx_msg_len = 0;
                g_state.noconf_count = 0;
                g_state.track_amplitude = 0.0f;
            }

            /* advance by try_max to scan ahead */
            unsigned int advance = try_max < nsamples ? try_max : nsamples;
            if (advance > 0) {
                memmove(samplebuf, samplebuf + advance,
                        (nsamples - advance) * sizeof(float));
                nsamples -= advance;
            }
        }
    }

    free(samplebuf);
    return NULL;
}
```

**Step 2: Add receive API function**

```c
MINIMODEM_API int minimodem_simple_receive(uint8_t *buffer, int bufferSize) {
    if (!buffer || bufferSize <= 0) return 0;

    msg_node_t *node = msg_queue_pop();
    if (!node) return 0;

    int copy_len = node->len < bufferSize ? node->len : bufferSize;
    memcpy(buffer, node->data, copy_len);

    free(node->data);
    free(node);
    return copy_len;
}
```

**Step 3: Commit**

```bash
git add minimodem-wrapper/minimodem_simple.c
git commit -m "feat(minimodem-wrapper): add decoder thread and receive state machine"
```

---

### Task 9: Add init, cleanup, and set_baud_rate

**Files:**
- Modify: `minimodem-wrapper/minimodem_simple.c`

Wire everything together: open PA streams, start decoder thread, handle cleanup.

**Step 1: Add audio stream creation**

```c
/* ---------- audio stream management ---------- */

static int create_audio(int playbackId, int captureId) {
    PaError err;

    /* resolve device indices */
    int pa_out = (playbackId >= 0 && playbackId < g_state.playback_count)
                 ? g_state.playback_map[playbackId]
                 : Pa_GetDefaultOutputDevice();
    int pa_in  = (captureId >= 0 && captureId < g_state.capture_count)
                 ? g_state.capture_map[captureId]
                 : Pa_GetDefaultInputDevice();

    if (pa_out == paNoDevice || pa_in == paNoDevice) {
        set_error("init: no audio device available");
        return -1;
    }

    /* output stream */
    PaStreamParameters outParams = {0};
    outParams.device = pa_out;
    outParams.channelCount = 1;
    outParams.sampleFormat = paFloat32;
    outParams.suggestedLatency = Pa_GetDeviceInfo(pa_out)->defaultLowOutputLatency;

    err = Pa_OpenStream(&g_state.stream_out, NULL, &outParams,
                        SAMPLE_RATE, PA_FRAMES_PER_BUF, paClipOff,
                        pa_tx_callback, NULL);
    if (err != paNoError) {
        set_error("init: Pa_OpenStream(out) failed: %s", Pa_GetErrorText(err));
        return -1;
    }

    /* input stream */
    PaStreamParameters inParams = {0};
    inParams.device = pa_in;
    inParams.channelCount = 1;
    inParams.sampleFormat = paFloat32;
    inParams.suggestedLatency = Pa_GetDeviceInfo(pa_in)->defaultLowInputLatency;

    err = Pa_OpenStream(&g_state.stream_in, &inParams, NULL,
                        SAMPLE_RATE, PA_FRAMES_PER_BUF, paClipOff,
                        pa_rx_callback, NULL);
    if (err != paNoError) {
        set_error("init: Pa_OpenStream(in) failed: %s", Pa_GetErrorText(err));
        Pa_CloseStream(g_state.stream_out);
        g_state.stream_out = NULL;
        return -1;
    }

    /* start streams */
    Pa_StartStream(g_state.stream_out);
    Pa_StartStream(g_state.stream_in);

    return 0;
}

static void destroy_audio(void) {
    if (g_state.stream_out) {
        Pa_StopStream(g_state.stream_out);
        Pa_CloseStream(g_state.stream_out);
        g_state.stream_out = NULL;
    }
    if (g_state.stream_in) {
        Pa_StopStream(g_state.stream_in);
        Pa_CloseStream(g_state.stream_in);
        g_state.stream_in = NULL;
    }
}
```

**Step 2: Add init and cleanup**

```c
MINIMODEM_API int minimodem_simple_init(int playbackDeviceId, int captureDeviceId, int baud_rate) {
    memset(&g_state, 0, sizeof(g_state));

    if (ensure_pa() < 0) return -1;

    /* FSK parameters */
    calc_fsk_params(baud_rate);

    /* FSK decoder plan */
    g_state.fskp = fsk_plan_new(SAMPLE_RATE, g_state.mark_freq,
                                 g_state.space_freq, g_state.filter_bw);
    if (!g_state.fskp) {
        set_error("init: fsk_plan_new failed");
        return -1;
    }

    /* tone generator */
    tone_generator_init(TONE_TABLE_LEN, TONE_AMPLITUDE);

    /* allocate ring buffers */
    g_state.tx_ring_size = (int)TX_RING_SIZE;
    g_state.tx_ring = calloc(g_state.tx_ring_size, sizeof(float));
    g_state.rx_ring_size = (int)RX_RING_SIZE;
    g_state.rx_ring = calloc(g_state.rx_ring_size, sizeof(float));

    if (!g_state.tx_ring || !g_state.rx_ring) {
        set_error("init: ring buffer allocation failed");
        return -1;
    }

    /* message queue mutex */
    pthread_mutex_init(&g_state.msg_mutex, NULL);

    /* open audio streams */
    if (create_audio(playbackDeviceId, captureDeviceId) < 0)
        return -1;

    /* start decoder thread */
    g_state.decoder_running = 1;
    g_state.rx_state = RX_WAITING_FOR_CARRIER;
    if (pthread_create(&g_state.decoder_thread, NULL, decoder_thread_func, NULL) != 0) {
        set_error("init: failed to create decoder thread");
        destroy_audio();
        return -1;
    }

    return 0;
}

MINIMODEM_API void minimodem_simple_cleanup(void) {
    /* stop decoder thread */
    g_state.decoder_running = 0;
    pthread_join(g_state.decoder_thread, NULL);

    /* stop audio */
    destroy_audio();

    /* free FSK plan */
    if (g_state.fskp) {
        fsk_plan_destroy(g_state.fskp);
        g_state.fskp = NULL;
    }

    /* free ring buffers */
    free(g_state.tx_ring);  g_state.tx_ring = NULL;
    free(g_state.rx_ring);  g_state.rx_ring = NULL;

    /* drain message queue */
    msg_node_t *node;
    while ((node = msg_queue_pop()) != NULL) {
        free(node->data);
        free(node);
    }

    pthread_mutex_destroy(&g_state.msg_mutex);

    Pa_Terminate();
    g_state.pa_initialized = 0;
}

MINIMODEM_API int minimodem_simple_set_baud_rate(int baud_rate) {
    if (!g_state.fskp) {
        set_error("set_baud_rate: not initialized");
        return -1;
    }

    /* recalculate FSK parameters */
    calc_fsk_params(baud_rate);

    /* recreate FSK plan with new frequencies */
    fsk_plan_destroy(g_state.fskp);
    g_state.fskp = fsk_plan_new(SAMPLE_RATE, g_state.mark_freq,
                                 g_state.space_freq, g_state.filter_bw);
    if (!g_state.fskp) {
        set_error("set_baud_rate: fsk_plan_new failed");
        return -1;
    }

    tone_reset_phase();
    return 0;
}
```

**Step 3: Verify full compilation**

```bash
cd minimodem-wrapper/build && cmake .. && mingw32-make 2>&1
```

Expected: Clean compile and link. `minimodem_simple.dll` produced in `build/`.

**Step 4: Commit**

```bash
git add minimodem-wrapper/minimodem_simple.c
git commit -m "feat(minimodem-wrapper): add init, cleanup, and set_baud_rate"
```

---

### Task 10: Build DLL and collect runtime DLLs

**Step 1: Install MSYS2 dependencies**

```bash
pacman -S --needed --noconfirm \
    mingw-w64-x86_64-fftw \
    mingw-w64-x86_64-portaudio \
    mingw-w64-x86_64-cmake \
    mingw-w64-x86_64-gcc
```

**Step 2: Build**

```bash
cd minimodem-wrapper && bash build.sh
```

Expected: `minimodem-wrapper/build/minimodem_simple.dll` exists.

**Step 3: Collect DLLs**

```bash
bash minimodem-wrapper/collect_dlls.sh
```

Expected: `AHK/minimodem_simple.dll`, `AHK/libfftw3f-3.dll`, `AHK/libportaudio-2.dll` exist.

**Step 4: Verify DLL exports**

```bash
objdump -p minimodem-wrapper/build/minimodem_simple.dll | grep "DLL Name\|minimodem_simple"
```

Expected: All 13 exported functions listed.

**Step 5: Commit build artifacts to .gitignore**

Add to root `.gitignore`:
```
minimodem-wrapper/build/
AHK/*.dll
```

```bash
git add .gitignore
git commit -m "chore: add build artifacts to .gitignore"
```

---

## Phase 3: AHK Frontend Updates

### Task 11: Update AHK config

**Files:**
- Modify: `AHK/include/config.ahk`

**Step 1: Replace ggwave constants with minimodem constants**

Current `config.ahk` (line 17-20):
```ahk
GGWAVE_PAYLOAD_LIMIT := 140
CHUNK_DATA_SIZE := 70
INTER_CHUNK_DELAY := 200
CHUNK_REASSEMBLY_TIMEOUT := 30000
```

Replace with:
```ahk
; minimodem has no per-frame limit; this is max bytes per send()
MAX_PAYLOAD_SIZE := 4096
; Configurable: chunk data size in characters (~few hundred words)
CHUNK_DATA_SIZE := 1500
INTER_CHUNK_DELAY := 200
CHUNK_REASSEMBLY_TIMEOUT := 30000
; FSK baud rate (1200=Bell 202, 2400, 4800)
BAUD_RATE := 1200
```

**Step 2: Commit**

```bash
git add AHK/include/config.ahk
git commit -m "feat(ahk): update config for minimodem transport"
```

---

### Task 12: Update AHK dll_manager

**Files:**
- Modify: `AHK/include/dll_manager.ahk`

**Step 1: Replace ggwave DLL loading with minimodem**

Rewrite the file. Current structure (37 lines) loads `ggwave_simple.dll`. Replace with `minimodem_simple.dll`:

```ahk
#Requires AutoHotkey v2.0

global minimodemDll := 0

LoadMinimodemDll() {
    global minimodemDll
    dllPath := A_ScriptDir "\minimodem_simple.dll"

    if !FileExist(dllPath) {
        MsgBox("DLL not found: " dllPath)
        ExitApp
    }

    minimodemDll := DllCall("LoadLibrary", "Str", dllPath, "Ptr")
    if !minimodemDll {
        MsgBox("Failed to load DLL: " dllPath)
        ExitApp
    }
}

UnloadMinimodemDll() {
    global minimodemDll
    if minimodemDll {
        DllCall("FreeLibrary", "Ptr", minimodemDll)
        minimodemDll := 0
    }
}

GetMinimodemError() {
    return StrGet(DllCall("minimodem_simple\minimodem_simple_get_error", "Ptr"), "UTF-8")
}
```

**Step 2: Commit**

```bash
git add AHK/include/dll_manager.ahk
git commit -m "feat(ahk): update dll_manager for minimodem DLL"
```

---

### Task 13: Update AHK GUI

**Files:**
- Modify: `AHK/include/gui.ahk`

**Step 1: Replace protocol dropdown with baud rate selector and update device enumeration DllCalls**

Replace all `ggwave_simple\ggwave_simple_*` function names with `minimodem_simple\minimodem_simple_*` in device enumeration.

Replace the protocol dropdown (line 59-61) with baud rate options:

```ahk
; Baud rate selector (replaces protocol dropdown)
deviceGui.AddText("xm y+15", "Baud Rate:")
baudRateList := deviceGui.AddDropDownList("xm y+5 w380 vBaudRate Choose1",
    ["1200 (Bell 202 - Conservative)",
     "2400 (Balanced)",
     "4800 (Fast)"])
```

Update the return value to extract baud rate instead of protocol:

```ahk
; Extract baud rate from selection
baudStr := baudRateList.Text
if InStr(baudStr, "1200")
    selectedBaudRate := 1200
else if InStr(baudStr, "2400")
    selectedBaudRate := 2400
else if InStr(baudStr, "4800")
    selectedBaudRate := 4800
else
    selectedBaudRate := BAUD_RATE  ; from config.ahk
```

**Step 2: Commit**

```bash
git add AHK/include/gui.ahk
git commit -m "feat(ahk): update GUI for minimodem (baud rate selector, device enum)"
```

---

### Task 14: Update AHK main_dll.ahk

**Files:**
- Modify: `AHK/main_dll.ahk`

**Step 1: Update init call** (current line 35-39)

Replace:
```ahk
initResult := DllCall("ggwave_simple\ggwave_simple_init",
    "Int", selectedSpeakerIndex,
    "Int", selectedMicrophoneIndex,
    "Int", 1,
    "Int")
```

With:
```ahk
initResult := DllCall("minimodem_simple\minimodem_simple_init",
    "Int", selectedSpeakerIndex,
    "Int", selectedMicrophoneIndex,
    "Int", selectedBaudRate,
    "Int")
```

**Step 2: Update send calls**

The send API changes from null-terminated string to binary data + length. Where the current code calls `ggwave_simple_send(jsonString, volume)`, replace with:

```ahk
; Convert string to UTF-8 buffer for binary send
SendData(data) {
    buf := Buffer(StrPut(data, "UTF-8") - 1)  ; exclude null terminator
    StrPut(data, buf, "UTF-8")
    result := DllCall("minimodem_simple\minimodem_simple_send",
        "Ptr", buf,
        "Int", buf.Size,
        "Int")
    return result
}
```

**Step 3: Update receive calls**

Replace `ggwave_simple_receive` with `minimodem_simple_receive`:

```ahk
; In the polling timer or receive loop
recvBuf := Buffer(8192)
bytesReceived := DllCall("minimodem_simple\minimodem_simple_receive",
    "Ptr", recvBuf,
    "Int", recvBuf.Size,
    "Int")
if bytesReceived > 0 {
    receivedStr := StrGet(recvBuf, bytesReceived, "UTF-8")
    ; process receivedStr (split on newlines, parse JSON chunks)
}
```

**Step 4: Update is_transmitting check**

Replace `ggwave_simple_is_transmitting` with `minimodem_simple_is_transmitting`:

```ahk
isTransmitting := DllCall("minimodem_simple\minimodem_simple_is_transmitting", "Int")
```

**Step 5: Remove ProcessAudio timer**

Remove `SetTimer(ProcessAudio, 10)` — no `process()` call needed. The receive polling timer can remain but calls `minimodem_simple_receive` instead of `ggwave_simple_process` + `ggwave_simple_receive`.

**Step 6: Update cleanup call**

Replace `ggwave_simple_cleanup` with `minimodem_simple_cleanup`:

```ahk
DllCall("minimodem_simple\minimodem_simple_cleanup")
UnloadMinimodemDll()
```

**Step 7: Commit**

```bash
git add AHK/main_dll.ahk
git commit -m "feat(ahk): update main_dll for minimodem transport"
```

---

### Task 15: Update AHK chunking for newline delimiter

**Files:**
- Modify: `AHK/include/chunking.ahk`

**Step 1: Append newline to each chunk before sending**

In `SendChunkedMessage()`, after building each chunk JSON string and before calling the send function, append `\n`:

```ahk
; After building chunkJson:
chunkJson := chunkJson "`n"  ; newline delimiter for minimodem
SendData(chunkJson)
```

**Step 2: Update receive processing to split on newlines**

In the receive handler, split received data on `\n` to extract individual JSON chunks:

```ahk
; receivedStr may contain multiple newline-delimited chunks
chunks := StrSplit(receivedStr, "`n")
for chunk in chunks {
    chunk := Trim(chunk)
    if chunk = ""
        continue
    ; parse JSON chunk and process
    ProcessReceivedChunk(chunk)
}
```

**Step 3: Update CHUNK_DATA_SIZE reference**

If `chunking.ahk` references `GGWAVE_PAYLOAD_LIMIT`, update to use `MAX_PAYLOAD_SIZE` from the new config.

**Step 4: Commit**

```bash
git add AHK/include/chunking.ahk
git commit -m "feat(ahk): add newline delimiter to chunking for minimodem"
```

---

## Phase 4: Python Backend Updates

### Task 16: Update Python config

**Files:**
- Modify: `python-backend/lib/config.py`

**Step 1: Replace ggwave constants**

Current (lines 14-20):
```python
COMPRESSION_THRESHOLD = 100
...
GGWAVE_PAYLOAD_LIMIT = 140
CHUNK_DATA_SIZE = 70
INTER_CHUNK_DELAY = 0.5
CHUNK_REASSEMBLY_TIMEOUT = 30
```

Replace with:
```python
COMPRESSION_THRESHOLD = 100
...
MAX_PAYLOAD_SIZE = 4096      # no hard per-frame limit with minimodem
CHUNK_DATA_SIZE = 1500       # configurable, ~few hundred words
INTER_CHUNK_DELAY = 0.2      # 200ms between chunks (match AHK)
CHUNK_REASSEMBLY_TIMEOUT = 30
BAUD_RATE = 1200             # default FSK baud rate
```

**Step 2: Commit**

```bash
git add python-backend/lib/config.py
git commit -m "feat(python): update config for minimodem transport"
```

---

### Task 17: Create MinimodemTransport class

**Files:**
- Create: `python-backend/lib/transport.py`

**Step 1: Write the subprocess-based transport**

```python
"""Minimodem subprocess transport for Raspberry Pi."""

import subprocess
import threading
import queue
import logging
import shutil
from .config import BAUD_RATE

logger = logging.getLogger(__name__)


class MinimodemTransport:
    """Manages minimodem TX/RX subprocesses for audio data transport."""

    def __init__(self, baud_rate=BAUD_RATE, alsa_dev=None):
        self.baud_rate = baud_rate
        self.alsa_dev = alsa_dev
        self.rx_process = None
        self.tx_process = None
        self.rx_thread = None
        self.rx_queue = queue.Queue()
        self._running = False
        self._line_buffer = ""

        if not shutil.which("minimodem"):
            raise RuntimeError("minimodem not found. Install with: apt install minimodem")

    def start(self):
        """Start RX and TX subprocesses."""
        self._running = True

        # RX subprocess: minimodem --rx <baud> --quiet
        rx_cmd = ["minimodem", "--rx", str(self.baud_rate), "--quiet"]
        if self.alsa_dev:
            rx_cmd.extend(["--alsa-dev", self.alsa_dev])
        self.rx_process = subprocess.Popen(
            rx_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        # TX subprocess: minimodem --tx <baud>
        tx_cmd = ["minimodem", "--tx", str(self.baud_rate)]
        if self.alsa_dev:
            tx_cmd.extend(["--alsa-dev", self.alsa_dev])
        self.tx_process = subprocess.Popen(
            tx_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        # background thread to read RX output
        self.rx_thread = threading.Thread(target=self._rx_reader, daemon=True)
        self.rx_thread.start()

        logger.info("MinimodemTransport started (baud=%d)", self.baud_rate)

    def stop(self):
        """Stop subprocesses and reader thread."""
        self._running = False

        if self.tx_process:
            self.tx_process.stdin.close()
            self.tx_process.wait(timeout=5)
            self.tx_process = None

        if self.rx_process:
            self.rx_process.terminate()
            self.rx_process.wait(timeout=5)
            self.rx_process = None

        logger.info("MinimodemTransport stopped")

    def send(self, data: str):
        """Send a string (typically a JSON chunk) over minimodem TX.
        Appends newline delimiter automatically."""
        if not self.tx_process or self.tx_process.poll() is not None:
            raise RuntimeError("TX subprocess not running")
        payload = (data + "\n").encode("utf-8")
        self.tx_process.stdin.write(payload)
        self.tx_process.stdin.flush()

    def receive(self, timeout=0.1):
        """Receive a decoded message (newline-delimited string).
        Returns None if nothing available within timeout."""
        try:
            return self.rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _rx_reader(self):
        """Background thread: read minimodem RX stdout, split on newlines."""
        while self._running and self.rx_process:
            try:
                chunk = self.rx_process.stdout.read(1)
                if not chunk:
                    break
                char = chunk.decode("utf-8", errors="replace")
                if char == "\n":
                    line = self._line_buffer.strip()
                    if line:
                        self.rx_queue.put(line)
                    self._line_buffer = ""
                else:
                    self._line_buffer += char
            except Exception as e:
                logger.error("RX reader error: %s", e)
                break
```

**Step 2: Commit**

```bash
git add python-backend/lib/transport.py
git commit -m "feat(python): add MinimodemTransport subprocess wrapper"
```

---

### Task 18: Update Python backend.py

**Files:**
- Modify: `python-backend/backend.py`

**Step 1: Replace ggwave imports and init**

Remove (lines 15-16):
```python
import ggwave
import pyaudio
```

Replace with:
```python
from lib.transport import MinimodemTransport
```

**Step 2: Replace audio stream setup**

Remove PyAudio stream creation (lines 101-116). Replace with:

```python
transport = MinimodemTransport(baud_rate=args.baud_rate, alsa_dev=args.alsa_dev)
transport.start()
```

**Step 3: Replace main receive loop**

Remove `ggwave.decode()` calls (line 135). Replace with:

```python
while True:
    received = transport.receive(timeout=0.1)
    if received is None:
        check_chunk_timeouts_and_send(transport)
        continue

    # received is a newline-delimited JSON string
    try:
        chunk_dict = json.loads(received)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON received: %s", received[:100])
        continue

    # handle chunk (existing logic)
    result = handle_received_chunk(chunk_dict)
    if result:
        process_complete_message(result, transport)
```

**Step 4: Replace send calls**

Remove `ggwave.encode()` + stream write (lines 181-182, 235). Replace with:

```python
def send_chunk(chunk_json: str, transport: MinimodemTransport):
    transport.send(chunk_json)
```

**Step 5: Update argparse**

Replace `--protocol` with `--baud-rate`:

```python
parser.add_argument("-b", "--baud-rate", type=int, default=1200,
                    help="FSK baud rate (default: 1200)")
parser.add_argument("--alsa-dev", type=str, default=None,
                    help="ALSA device name for minimodem")
```

Remove `-i`/`-o` device index args (minimodem uses ALSA device names, not indices). Remove `-p`/`--protocol`. Keep `-v`/`--volume` for future use. Keep `-l`/`--list`.

**Step 6: Update cleanup**

Replace PyAudio cleanup with:
```python
transport.stop()
```

**Step 7: Commit**

```bash
git add python-backend/backend.py
git commit -m "feat(python): replace ggwave with MinimodemTransport in backend"
```

---

## Phase 5: Archive & Cleanup

### Task 19: Archive ggwave wrapper code

**Files:**
- Move: `ggwave-wrapper/` -> `archive/ggwave-wrapper/`
- Copy: `AHK/include/dll_manager.ahk` -> already modified, but the git history preserves the old version
- Create: `archive/README.md`

**Step 1: Create archive and move ggwave-wrapper**

```bash
mkdir -p archive
git mv ggwave-wrapper archive/ggwave-wrapper
```

**Step 2: Write archive README**

```markdown
# Archive

Reference implementations kept for future use.

## ggwave-wrapper/

Original ggwave DLL wrapper (SDL2-based). Replaced by minimodem-wrapper
in Feb 2026 due to ggwave's 140-byte payload limit. See
`docs/plans/2026-02-28-minimodem-migration-design.md` for rationale.
```

**Step 3: Commit**

```bash
git add archive/
git commit -m "chore: archive ggwave-wrapper as reference implementation"
```

---

### Task 20: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update Architecture section**

Replace ggwave references with minimodem. Update:
- AHK Frontend description: `minimodem_simple.dll` instead of `ggwave_simple DLL`
- Python Backend description: `minimodem CLI subprocess` instead of `ggwave`
- Add `minimodem-wrapper/` to the component list
- Move ggwave-wrapper to archived status

**Step 2: Update Audio Channel Constraints section**

Replace ggwave-specific constraints (140-byte limit, protocol IDs) with minimodem:
- No per-frame payload limit (continuous FSK stream)
- CHUNK_DATA_SIZE configurable (~1500 chars default)
- Newline delimiter between JSON chunks
- Baud rate configurable (starting at 1200)

**Step 3: Update Key Constraints section**

Replace ggwave encoding/compression references with minimodem equivalents.

**Step 4: Update Build section**

Replace ggwave-wrapper build instructions with minimodem-wrapper.

**Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for minimodem migration"
```

---

## Phase 6: Integration Testing

### Task 21: Loopback test (Windows DLL)

**Step 1: Write a minimal AHK loopback test script**

Create `AHK/test_minimodem.ahk`:

```ahk
#Requires AutoHotkey v2.0
#Include include/config.ahk
#Include include/dll_manager.ahk

LoadMinimodemDll()

; Init with default devices
result := DllCall("minimodem_simple\minimodem_simple_init",
    "Int", -1, "Int", -1, "Int", 1200, "Int")
MsgBox("Init result: " result)

; Send test message
testMsg := '{"id":"TEST","fn":"ping","ct":"hello world"}'
buf := Buffer(StrPut(testMsg, "UTF-8") - 1)
StrPut(testMsg, buf, "UTF-8")
result := DllCall("minimodem_simple\minimodem_simple_send",
    "Ptr", buf, "Int", buf.Size, "Int")
MsgBox("Send result: " result)

; Wait for transmission to complete
while DllCall("minimodem_simple\minimodem_simple_is_transmitting", "Int") {
    Sleep(100)
}
MsgBox("Transmission complete")

; Poll for receive (requires audio loopback cable or virtual cable)
recvBuf := Buffer(8192)
attempts := 0
while attempts < 100 {
    bytesReceived := DllCall("minimodem_simple\minimodem_simple_receive",
        "Ptr", recvBuf, "Int", recvBuf.Size, "Int")
    if bytesReceived > 0 {
        received := StrGet(recvBuf, bytesReceived, "UTF-8")
        MsgBox("Received: " received)
        break
    }
    Sleep(100)
    attempts++
}
if attempts >= 100
    MsgBox("No data received (need audio loopback)")

DllCall("minimodem_simple\minimodem_simple_cleanup")
UnloadMinimodemDll()
MsgBox("Test complete")
```

**Step 2: Run the test**

Run `AHK/test_minimodem.ahk` with AutoHotkey v2. If using a USB audio loopback cable (output -> input on same device), the sent message should be received back.

Without loopback: verify init succeeds, send succeeds, is_transmitting transitions to 0 after send.

**Step 3: Commit test script**

```bash
git add AHK/test_minimodem.ahk
git commit -m "test: add minimodem DLL loopback test script"
```

---

### Task 22: Loopback test (Python subprocess)

**Step 1: Write a minimal Python loopback test**

Create `python-backend/test_transport.py`:

```python
"""Quick loopback test for MinimodemTransport."""
import time
from lib.transport import MinimodemTransport

transport = MinimodemTransport(baud_rate=1200)
transport.start()
print("Transport started")

# Send test message
test_msg = '{"id":"TEST","fn":"ping","ct":"hello world"}'
transport.send(test_msg)
print(f"Sent: {test_msg}")

# Wait for receive (requires audio loopback)
print("Waiting for receive...")
for i in range(100):
    received = transport.receive(timeout=0.1)
    if received:
        print(f"Received: {received}")
        break
else:
    print("No data received (need audio loopback)")

transport.stop()
print("Test complete")
```

**Step 2: Run on Raspberry Pi**

```bash
sudo apt install minimodem
cd python-backend
python3 test_transport.py
```

**Step 3: Commit**

```bash
git add python-backend/test_transport.py
git commit -m "test: add minimodem transport loopback test"
```

---

### Task 23: Cross-device integration test

**Step 1:** Connect PC to Pi via USB audio cable (PC line-out -> Pi line-in, Pi line-out -> PC line-in).

**Step 2:** On Pi, start the backend:
```bash
cd python-backend
python3 backend.py --baud-rate 1200
```

**Step 3:** On PC, run the AHK frontend and send a test message through the GUI.

**Step 4:** Verify:
- Message reaches Pi backend (check `backend_log.txt`)
- Pipeline processes it (or returns echo for test pipeline)
- Response transmitted back over audio
- AHK receives and displays the response

**Step 5:** If it works, this task is done. If not, debug with:
- `arecord -f FLOAT_LE -r 48000 -c 1 test.wav` on Pi to verify audio input
- Check `ggwave_log.txt` on Windows for DLL errors
- Check `backend_log.txt` on Pi for transport errors
