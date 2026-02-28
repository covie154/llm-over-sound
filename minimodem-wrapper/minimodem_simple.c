/*
 * minimodem_simple.c
 *
 * A simplified DLL wrapper around minimodem FSK modem functionality,
 * providing a PortAudio-based send/receive interface.
 *
 * This file contains:
 *   - Global state struct
 *   - FSK parameter calculation (ported from minimodem.c)
 *   - PortAudio device enumeration
 *   - Device enumeration API functions
 *
 * Transmit, receive, init, and cleanup are added in subsequent files/tasks.
 */

/* --- Includes --- */

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
#include <stdarg.h>

/* --- Constants --- */

#define SAMPLE_RATE         48000.0f
#define PA_FRAMES_PER_BUF   1024
#define MAX_DEVICES          64
#define MAX_MESSAGE_LEN      8192
#define TX_RING_SIZE        ((int)(SAMPLE_RATE * 30))   /* 30 sec max TX buffer */
#define RX_RING_SIZE        ((int)(SAMPLE_RATE * 2))    /* 2 sec RX ring buffer */
#define CONFIDENCE_THRESHOLD 1.5f
#define MAX_NOCONF_BITS      20
#define LEADER_BITS          2
#define TRAILER_BITS         2
#define TONE_TABLE_LEN       4096
#define TONE_AMPLITUDE       0.5f
#define MAX_ERROR_LEN        256

/* --- Receive state enum --- */

typedef enum {
    RX_WAITING_FOR_CARRIER,
    RX_RECEIVING
} rx_state_t;

/* --- Message queue node --- */

typedef struct msg_node {
    uint8_t         *data;
    int              len;
    struct msg_node *next;
} msg_node_t;

/* --- Global state --- */

static struct {
    /* --- Audio streams --- */
    PaStream       *stream_out;
    PaStream       *stream_in;
    int             pa_initialized;

    /* --- FSK configuration --- */
    int             baud_rate;
    float           mark_freq;
    float           space_freq;
    float           filter_bw;
    unsigned int    bit_nsamples;
    unsigned int    frame_nsamples;

    /* --- FSK decoder --- */
    fsk_plan       *fskp;
    rx_state_t      rx_state;
    int             noconf_count;
    float           track_amplitude;
    uint8_t         rx_msg_buf[MAX_MESSAGE_LEN];
    int             rx_msg_len;

    /* --- RX ring buffer --- */
    float          *rx_ring;
    volatile int    rx_ring_head;
    volatile int    rx_ring_tail;
    int             rx_ring_size;

    /* --- TX ring buffer --- */
    float          *tx_ring;
    volatile int    tx_ring_head;
    volatile int    tx_ring_tail;
    int             tx_ring_size;

    /* --- Decoder thread --- */
    pthread_t       decoder_thread;
    volatile int    decoder_running;

    /* --- Message queue (decoded messages awaiting receive()) --- */
    msg_node_t     *msg_queue_head;
    msg_node_t     *msg_queue_tail;
    pthread_mutex_t msg_mutex;

    /* --- Device mapping (wrapper index -> PortAudio index) --- */
    int             playback_map[MAX_DEVICES];
    int             capture_map[MAX_DEVICES];
    char            playback_names[MAX_DEVICES][256];
    char            capture_names[MAX_DEVICES][256];
    int             playback_count;
    int             capture_count;

    /* --- Error --- */
    char            last_error[MAX_ERROR_LEN];
} g_state = {
    .msg_mutex = PTHREAD_MUTEX_INITIALIZER
};

/* ================================================================
 * Internal helpers
 * ================================================================ */

/* --- set_error: format and store an error message --- */

static void set_error(const char *fmt, ...) {
    if (!fmt) {
        g_state.last_error[0] = '\0';
        return;
    }
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(g_state.last_error, MAX_ERROR_LEN, fmt, ap);
    va_end(ap);
}

/* ================================================================
 * FSK parameter calculation
 * Ported from minimodem.c lines 900-934.
 * ================================================================ */

/* --- calc_fsk_params: derive mark/space/bw from baud rate --- */

static void calc_fsk_params(int baud_rate) {
    g_state.baud_rate = baud_rate;

    if (baud_rate >= 400) {
        /*
         * Bell 202:  baud=1200  mark=1200  space=2200
         * General:   mark = baud/2 + 600
         *            space = mark + baud*5/6
         */
        g_state.mark_freq  = (float)(baud_rate / 2 + 600);
        g_state.space_freq = g_state.mark_freq + (float)(baud_rate * 5 / 6);
        g_state.filter_bw  = 200.0f;
    } else if (baud_rate >= 100) {
        /*
         * Bell 103:  baud=300  mark=1270  space=1070
         */
        g_state.mark_freq  = 1270.0f;
        g_state.space_freq = 1070.0f;
        g_state.filter_bw  = 50.0f;
    } else {
        /*
         * RTTY:  baud=45.45  mark=1585  space=1415  shift=170
         */
        g_state.mark_freq  = 1585.0f;
        g_state.space_freq = 1415.0f;
        g_state.filter_bw  = 10.0f;
    }

    /* Samples per bit (rounded) */
    g_state.bit_nsamples = (unsigned int)(SAMPLE_RATE / baud_rate + 0.5f);

    /* Samples per frame: 1 start + 8 data + 1 stop = 10 bits */
    g_state.frame_nsamples = g_state.bit_nsamples * 10;
}

/* ================================================================
 * PortAudio initialisation and device enumeration
 * ================================================================ */

/* --- build_device_maps: scan PortAudio devices, populate maps --- */

static void build_device_maps(void) {
    int n = Pa_GetDeviceCount();
    if (n <= 0) {
        g_state.playback_count = 0;
        g_state.capture_count  = 0;
        return;
    }

    int pb = 0, cap = 0;
    for (int i = 0; i < n && pb < MAX_DEVICES && cap < MAX_DEVICES; i++) {
        const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
        if (!info) continue;

        if (info->maxOutputChannels > 0 && pb < MAX_DEVICES) {
            g_state.playback_map[pb] = i;
            snprintf(g_state.playback_names[pb], 256, "%s", info->name);
            pb++;
        }
        if (info->maxInputChannels > 0 && cap < MAX_DEVICES) {
            g_state.capture_map[cap] = i;
            snprintf(g_state.capture_names[cap], 256, "%s", info->name);
            cap++;
        }
    }

    g_state.playback_count = pb;
    g_state.capture_count  = cap;
}

/* --- ensure_pa: initialize PortAudio once, then enumerate devices --- */

static int ensure_pa(void) {
    if (g_state.pa_initialized) return 0;

    PaError err = Pa_Initialize();
    if (err != paNoError) {
        set_error("Pa_Initialize: %s", Pa_GetErrorText(err));
        return -1;
    }
    g_state.pa_initialized = 1;
    build_device_maps();
    return 0;
}

/* ================================================================
 * Ring buffer helpers (single-producer single-consumer lock-free)
 * ================================================================ */

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

/* ================================================================
 * PortAudio stream callbacks
 * ================================================================ */

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

/* ================================================================
 * Public API — Device enumeration
 * ================================================================ */

MINIMODEM_API int minimodem_simple_get_playback_device_count(void) {
    pthread_mutex_lock(&g_state.msg_mutex);
    if (ensure_pa() != 0) {
        pthread_mutex_unlock(&g_state.msg_mutex);
        return -1;
    }
    int count = g_state.playback_count;
    pthread_mutex_unlock(&g_state.msg_mutex);
    return count;
}

MINIMODEM_API int minimodem_simple_get_capture_device_count(void) {
    pthread_mutex_lock(&g_state.msg_mutex);
    if (ensure_pa() != 0) {
        pthread_mutex_unlock(&g_state.msg_mutex);
        return -1;
    }
    int count = g_state.capture_count;
    pthread_mutex_unlock(&g_state.msg_mutex);
    return count;
}

MINIMODEM_API const char *minimodem_simple_get_playback_device_name(int id) {
    pthread_mutex_lock(&g_state.msg_mutex);
    if (ensure_pa() != 0) {
        pthread_mutex_unlock(&g_state.msg_mutex);
        return NULL;
    }
    if (id < 0 || id >= g_state.playback_count) {
        pthread_mutex_unlock(&g_state.msg_mutex);
        return NULL;
    }
    const char *name = g_state.playback_names[id];
    pthread_mutex_unlock(&g_state.msg_mutex);
    return name;
}

MINIMODEM_API const char *minimodem_simple_get_capture_device_name(int id) {
    pthread_mutex_lock(&g_state.msg_mutex);
    if (ensure_pa() != 0) {
        pthread_mutex_unlock(&g_state.msg_mutex);
        return NULL;
    }
    if (id < 0 || id >= g_state.capture_count) {
        pthread_mutex_unlock(&g_state.msg_mutex);
        return NULL;
    }
    const char *name = g_state.capture_names[id];
    pthread_mutex_unlock(&g_state.msg_mutex);
    return name;
}

/* --- get_error: return last error string --- */

MINIMODEM_API const char *minimodem_simple_get_error(void) {
    return g_state.last_error;
}

/* --- get_frame_len: return practical max payload size --- */

MINIMODEM_API int minimodem_simple_get_frame_len(void) {
    return 4096;
}
