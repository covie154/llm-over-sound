/*
 * minimodem_simple.c
 *
 * Public API + background RX thread + thread-safe newline-framed byte queue
 * for the minimodem_simple wrapper. Mirrors ggwave_simple.cpp's
 * init/send/is_transmitting/process/receive/set_baud/cleanup/get_error contract
 * EXACTLY so the AHK DllCall model and the Python ctypes binding stay symmetric;
 * the only API change vs. ggwave is protocolId -> baud (set_protocol -> set_baud).
 *
 * Design (07-RESEARCH.md § Threading Model):
 *   - One module-level minimodem_ctx (mm_core.c TX/RX engine).
 *   - A background RX thread loops mm_rx_step() (which BLOCKS on simpleaudio_read)
 *     and pushes decoded bytes into a mutex-guarded ring buffer, splitting on '\n'
 *     into complete lines that _receive() drains. This bridges minimodem's blocking
 *     read to AHK's non-blocking 10 ms process()/receive() poll.
 *   - _process() is a near no-op (the RX thread does the pumping; ggwave's _process
 *     pumped SDL). Kept so AHK's loop + the API signature are unchanged.
 *   - Half-duplex (Pitfall 3): while is_transmitting is set the RX thread still calls
 *     mm_rx_step to keep the device buffer drained but DISCARDS the bytes.
 *   - Security V5: accumulated line length and queued-line count are capped; overflow
 *     resets the line / drops oldest rather than growing unbounded. _receive copies
 *     bounds-checked.
 *   - One mutex guards ALL queue access on both producer and consumer (Pitfall 7).
 *
 * GPLv3 -- part of the minimodem_simple wrapper (links mm_core.c / vendored DSP).
 */

#ifndef MINIMODEM_SIMPLE_BUILD
#define MINIMODEM_SIMPLE_BUILD
#endif

#include "minimodem_simple.h"
#include "minimodem_internal.h"   /* minimodem_ctx + mm_* engine */
#include "simpleaudio.h"

#include <pthread.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* ===== Tunables (Security V5 caps) ===== */
#define MM_QUEUE_MAX_LINES    64       /* max complete newline-framed lines buffered */
#define MM_LINE_MAX_LEN       8192     /* max accumulated bytes before a '\n' (drop on overflow) */
#define MM_RX_STEP_BYTES      256      /* bytes pulled per mm_rx_step pass */

/* ===== A complete received line (newline-stripped). ===== */
typedef struct mm_line {
    char  *data;
    int    len;
} mm_line;

/* ===== Module-level state ===== */
static struct {
    int             initialized;
    int             baud;

    minimodem_ctx   ctx;

    pthread_t       rx_thread;
    pthread_mutex_t mutex;
    volatile int    rx_run;            /* RX thread keeps looping while non-zero */
    volatile int    is_transmitting;   /* atomic-ish flag (guarded reads acceptable) */

    /* line accumulator (bytes since the last '\n', not yet a complete line) */
    char            accum[MM_LINE_MAX_LEN];
    int             accum_len;

    /* ring of complete lines ready for _receive */
    mm_line         lines[MM_QUEUE_MAX_LINES];
    int             line_head;         /* index of oldest queued line */
    int             line_count;        /* number of queued lines */

    char            error[256];
} g = {0};

static void set_error(const char *msg)
{
    snprintf(g.error, sizeof(g.error), "%s", msg ? msg : "");
}

/* ---------------------------------------------------------------- */
/* Queue helpers (caller MUST hold g.mutex).                         */
/* ---------------------------------------------------------------- */

/* Push one complete line (a copy of accum[0..accum_len)). Drops oldest on overflow. */
static void queue_push_line_locked(const char *data, int len)
{
    char *copy = malloc((size_t)len + 1);
    if ( !copy )
        return;                        /* OOM: silently drop, do not crash */
    memcpy(copy, data, (size_t)len);
    copy[len] = '\0';

    if ( g.line_count == MM_QUEUE_MAX_LINES ) {
        /* drop the oldest line to make room (DoS guard, Security V5) */
        free(g.lines[g.line_head].data);
        g.lines[g.line_head].data = NULL;
        g.line_head = (g.line_head + 1) % MM_QUEUE_MAX_LINES;
        g.line_count--;
    }

    int tail = (g.line_head + g.line_count) % MM_QUEUE_MAX_LINES;
    g.lines[tail].data = copy;
    g.lines[tail].len  = len;
    g.line_count++;
}

/* Feed a freshly decoded byte buffer into the accumulator, splitting on '\n'. */
static void feed_decoded_bytes_locked(const char *buf, int n)
{
    for ( int i = 0; i < n; i++ ) {
        char c = buf[i];
        if ( c == '\n' ) {
            /* complete line (newline stripped) */
            queue_push_line_locked(g.accum, g.accum_len);
            g.accum_len = 0;
        } else {
            if ( g.accum_len < MM_LINE_MAX_LEN ) {
                g.accum[g.accum_len++] = c;
            } else {
                /* line too long without a '\n' -> reset (Security V5) */
                g.accum_len = 0;
            }
        }
    }
}

/* ---------------------------------------------------------------- */
/* Background RX thread.                                             */
/* ---------------------------------------------------------------- */
static void *rx_thread_main(void *arg)
{
    (void)arg;
    char tmp[MM_RX_STEP_BYTES];

    while ( g.rx_run ) {
        /* mm_rx_step BLOCKS inside simpleaudio_read until samples arrive. */
        int n = mm_rx_step(&g.ctx, tmp, sizeof(tmp));
        if ( n < 0 ) {
            /* read error: brief settle, keep looping (device may recover). */
            continue;
        }
        if ( n == 0 )
            continue;

        pthread_mutex_lock(&g.mutex);
        /* Half-duplex (Pitfall 3): keep the buffer drained during TX but discard. */
        if ( !g.is_transmitting )
            feed_decoded_bytes_locked(tmp, n);
        pthread_mutex_unlock(&g.mutex);
    }
    return NULL;
}

/* ---------------------------------------------------------------- */
/* Stream open helper.                                              */
/* ---------------------------------------------------------------- */
/*
 * Open one simpleaudio stream via the platform default backend
 * (SA_BACKEND_SYSDEFAULT -> WinMM on Windows, ALSA/Pulse on Linux). The device
 * id is passed through as the backend's integer index ("-1" -> default/mapper).
 * RX is opened FLOAT (the FFT needs float); TX FLOAT too (S16 also works, but a
 * single format keeps the tone generator simple).
 */
static simpleaudio *open_stream(int deviceId, sa_direction_t dir)
{
    char devbuf[16];
    snprintf(devbuf, sizeof(devbuf), "%d", deviceId);

    return simpleaudio_open_stream(
            SA_BACKEND_SYSDEFAULT,
            devbuf,
            dir,
            SA_SAMPLE_FORMAT_FLOAT,
            g.ctx.sample_rate ? g.ctx.sample_rate : 48000,
            1,                       /* mono (minimodem requires it) */
            "minimodem_simple",
            dir == SA_STREAM_RECORD ? "rx" : "tx");
}

/* ================================================================ */
/* Device enumeration                                               */
/* ================================================================ */
#ifdef _WIN32
extern int         mm_playback_device_count(void);
extern int         mm_capture_device_count(void);
extern const char *mm_playback_device_name(int deviceId);
extern const char *mm_capture_device_name(int deviceId);
extern int         mm_winmm_drain(simpleaudio *sa);   /* flush + wait for TX playout */
#endif

MINIMODEM_SIMPLE_API int minimodem_simple_get_playback_device_count(void)
{
#ifdef _WIN32
    return mm_playback_device_count();
#else
    /* ALSA/Pulse enumeration is not index-addressable the same way; the Pi
     * selects by default device. Report 0 so callers fall back to default. */
    return 0;
#endif
}

MINIMODEM_SIMPLE_API int minimodem_simple_get_capture_device_count(void)
{
#ifdef _WIN32
    return mm_capture_device_count();
#else
    return 0;
#endif
}

MINIMODEM_SIMPLE_API const char *minimodem_simple_get_playback_device_name(int deviceId)
{
#ifdef _WIN32
    return mm_playback_device_name(deviceId);
#else
    (void)deviceId;
    return "default";
#endif
}

MINIMODEM_SIMPLE_API const char *minimodem_simple_get_capture_device_name(int deviceId)
{
#ifdef _WIN32
    return mm_capture_device_name(deviceId);
#else
    (void)deviceId;
    return "default";
#endif
}

/* ================================================================ */
/* Initialization                                                   */
/* ================================================================ */
MINIMODEM_SIMPLE_API int minimodem_simple_init(int playbackDeviceId,
                                               int captureDeviceId,
                                               int baud)
{
    if ( g.initialized ) {
        set_error("Already initialized");
        return -1;
    }

    /* Build the FSK config + RX plan from baud (mm_core.c). */
    int rc = mm_build_config(&g.ctx, baud, 48000);
    if ( rc < 0 ) {
        set_error(g.ctx.error);
        return rc;                     /* negative; tone-out-of-band etc. */
    }
    g.baud = baud;

    /* TX amplitude default until _send overrides it from volume. */
    simpleaudio_tone_init(4096, 1.0f);

    /* Open capture (RX) and playback (TX) streams. */
    g.ctx.sa_in = open_stream(captureDeviceId, SA_STREAM_RECORD);
    if ( !g.ctx.sa_in ) {
        set_error("Failed to open capture (waveIn) stream");
        mm_destroy(&g.ctx);
        return -2;
    }
    g.ctx.sa_out = open_stream(playbackDeviceId, SA_STREAM_PLAYBACK);
    if ( !g.ctx.sa_out ) {
        set_error("Failed to open playback (waveOut) stream");
        mm_destroy(&g.ctx);            /* closes sa_in */
        return -3;
    }

    /* queue state */
    g.accum_len  = 0;
    g.line_head  = 0;
    g.line_count = 0;
    g.is_transmitting = 0;

    if ( pthread_mutex_init(&g.mutex, NULL) != 0 ) {
        set_error("Failed to init mutex");
        mm_destroy(&g.ctx);
        return -4;
    }

    /* Spin up the background RX thread. */
    g.rx_run = 1;
    if ( pthread_create(&g.rx_thread, NULL, rx_thread_main, NULL) != 0 ) {
        set_error("Failed to create RX thread");
        g.rx_run = 0;
        pthread_mutex_destroy(&g.mutex);
        mm_destroy(&g.ctx);
        return -5;
    }

    g.initialized = 1;
    return 0;
}

/* ================================================================ */
/* Send / Receive                                                   */
/* ================================================================ */
MINIMODEM_SIMPLE_API int minimodem_simple_send(const char *message, int volume)
{
    if ( !g.initialized ) {
        set_error("Not initialized");
        return -1;
    }
    if ( !message || message[0] == '\0' ) {
        set_error("Empty message");
        return -2;
    }

    /* Map volume (1-100) -> tone amplitude (0..1). Open Question 4. */
    if ( volume < 1 )   volume = 1;
    if ( volume > 100 ) volume = 100;
    simpleaudio_tone_init(4096, (float)volume / 100.0f);

    pthread_mutex_lock(&g.mutex);
    g.is_transmitting = 1;
    pthread_mutex_unlock(&g.mutex);

    /* Modulate the caller's bytes to waveOut. On Windows the WinMM write()
     * coalesces into the ring and returns BEFORE the audio has played out, so
     * we must drain explicitly below. On Linux ALSA/Pulse write() blocks to
     * completion, so no drain is needed. */
    int rc = mm_tx_bytes(&g.ctx, (const unsigned char *)message, strlen(message));

#ifdef _WIN32
    /* Flush the trailing partial buffer and wait for the full FSK signal to
     * finish playing before is_transmitting clears (so the RX thread keeps
     * discarding our own transmission, Pitfall 3). */
    if ( rc >= 0 )
        mm_winmm_drain(g.ctx.sa_out);
#endif

    pthread_mutex_lock(&g.mutex);
    g.is_transmitting = 0;
    pthread_mutex_unlock(&g.mutex);

    if ( rc < 0 ) {
        set_error("mm_tx_bytes failed");
        return -3;
    }
    return 0;
}

MINIMODEM_SIMPLE_API int minimodem_simple_is_transmitting(void)
{
    if ( !g.initialized )
        return 0;
    return g.is_transmitting ? 1 : 0;
}

MINIMODEM_SIMPLE_API int minimodem_simple_process(void)
{
    if ( !g.initialized ) {
        set_error("Not initialized");
        return -1;
    }
    /* Near no-op: the background RX thread does the demod pumping (ggwave's
     * _process pumped SDL). Kept so AHK's 10 ms poll + API signature are
     * unchanged. No blocking work here (Open Question 3). */
    return 0;
}

MINIMODEM_SIMPLE_API int minimodem_simple_receive(char *buffer, int bufferSize)
{
    if ( !g.initialized ) {
        set_error("Not initialized");
        return -1;
    }
    if ( !buffer || bufferSize <= 0 ) {
        set_error("Invalid receive buffer");
        return -1;
    }

    int len = 0;
    pthread_mutex_lock(&g.mutex);
    if ( g.line_count > 0 ) {
        mm_line *ln = &g.lines[g.line_head];
        len = ln->len;
        /* bounds-checked copy: never overrun buffer (Security V5) */
        if ( len > bufferSize - 1 )
            len = bufferSize - 1;
        memcpy(buffer, ln->data, (size_t)len);
        buffer[len] = '\0';

        /* dequeue */
        free(ln->data);
        ln->data = NULL;
        g.line_head = (g.line_head + 1) % MM_QUEUE_MAX_LINES;
        g.line_count--;
    }
    pthread_mutex_unlock(&g.mutex);

    return len;   /* 0 if no complete line is queued */
}

/* ================================================================ */
/* Baud configuration                                               */
/* ================================================================ */
MINIMODEM_SIMPLE_API int minimodem_simple_set_baud(int baud)
{
    if ( !g.initialized ) {
        set_error("Not initialized");
        return -1;
    }
    if ( baud <= 0 ) {
        set_error("Invalid baud");
        return -1;
    }
    if ( baud == g.baud )
        return 0;

    /*
     * Rebuild the fsk plan / config for the new baud. Both ends MUST match;
     * this changes only this end (CONTEXT: baud is a link parameter). We must
     * pause the RX thread while rebuilding because mm_build_config memsets the
     * ctx and frees/reallocates fskp + samplebuf that the RX thread reads.
     */
    g.rx_run = 0;
    pthread_join(g.rx_thread, NULL);

    /* Detach the open streams from the ctx so mm_build_config's memset does not
     * lose them; mm_build_config zeroes the whole ctx. */
    simpleaudio *sa_in  = g.ctx.sa_in;
    simpleaudio *sa_out = g.ctx.sa_out;

    /* free the old RX plan + buffer without touching the streams */
    if ( g.ctx.samplebuf ) { free(g.ctx.samplebuf); g.ctx.samplebuf = NULL; }
    if ( g.ctx.fskp )      { fsk_plan_destroy(g.ctx.fskp); g.ctx.fskp = NULL; }

    int rc = mm_build_config(&g.ctx, baud, 48000);
    if ( rc < 0 ) {
        set_error(g.ctx.error);
        /* config is now invalid; close the streams we stashed and bail. */
        if ( sa_in )  simpleaudio_close(sa_in);
        if ( sa_out ) simpleaudio_close(sa_out);
        g.ctx.sa_in = g.ctx.sa_out = NULL;
        g.initialized = 0;
        return rc;
    }

    /* reattach streams + clear any partial line */
    g.ctx.sa_in  = sa_in;
    g.ctx.sa_out = sa_out;
    g.baud = baud;

    pthread_mutex_lock(&g.mutex);
    g.accum_len = 0;
    pthread_mutex_unlock(&g.mutex);

    /* restart RX thread */
    g.rx_run = 1;
    if ( pthread_create(&g.rx_thread, NULL, rx_thread_main, NULL) != 0 ) {
        set_error("Failed to restart RX thread after set_baud");
        return -2;
    }
    return 0;
}

/* ================================================================ */
/* Cleanup                                                          */
/* ================================================================ */
MINIMODEM_SIMPLE_API void minimodem_simple_cleanup(void)
{
    if ( !g.initialized )
        return;

    /* Stop the RX thread. It may be blocked inside simpleaudio_read; closing
     * the streams (mm_destroy) after the join is the safe ordering because the
     * WinMM/ALSA backends return from a blocking read on close/reset. We set
     * rx_run=0 first; if the thread is parked in read it will exit on the next
     * returned buffer. */
    g.rx_run = 0;
    pthread_join(g.rx_thread, NULL);

    mm_destroy(&g.ctx);                /* free samplebuf, fsk plan, close streams */
    pthread_mutex_destroy(&g.mutex);

    /* drain any queued lines */
    for ( int i = 0; i < g.line_count; i++ ) {
        int idx = (g.line_head + i) % MM_QUEUE_MAX_LINES;
        free(g.lines[idx].data);
        g.lines[idx].data = NULL;
    }
    g.line_head = 0;
    g.line_count = 0;
    g.accum_len = 0;

    g.initialized = 0;
}

MINIMODEM_SIMPLE_API const char *minimodem_simple_get_error(void)
{
    /* Prefer the most recent module error; fall back to the ctx error. */
    if ( g.error[0] != '\0' )
        return g.error;
    return g.ctx.error;
}
