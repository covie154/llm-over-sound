/*
 * loopback_test.c - byte-exact in-process TX->RX self-test (minimodem_loopback).
 *
 * Wave 0 gate (07-VALIDATION.md): proves the decomposed FSK engine
 * (mm_build_config / mm_tx_bytes / mm_rx_step) round-trips byte-for-byte BEFORE
 * any AHK/Python integration. This exercises the exact engine the wrapper +
 * WinMM/ALSA backend drive, but over a self-contained IN-MEMORY simpleaudio
 * backend so the test needs no audio hardware or virtual cable (harness backend
 * is Claude's discretion per CONTEXT.md).
 *
 * In-memory backend:
 *   - PLAYBACK write()  : appends float frames to a global sample FIFO.
 *   - RECORD   read()   : pops float frames from that FIFO; when drained it
 *                         returns silence (zeros) so mm_rx_step's blocking
 *                         contract is honored without ever blocking forever.
 * TX and RX share the SAME FIFO -> a perfect noiseless loopback. This isolates
 * the FSK refactor (Pitfall 1: loop-carried RX state must persist in ctx).
 *
 * The exe sweeps baud {1200, 4800, 9600}. It exits 0 ONLY when 1200-baud
 * loopback is byte-exact (the default/contract). 4800/9600 are reported but, if
 * the band plan rejects the tones or carrier never acquires (ASSUMPTION A2 /
 * Pitfall 6), they are recorded as "tone/carrier issue" and DO NOT fail the gate.
 *
 * GPLv3 -- part of the minimodem_simple wrapper test harness.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "minimodem_internal.h"     /* minimodem_ctx + mm_* engine */
#include "simpleaudio.h"
#include "simpleaudio_internal.h"

/* ============================================================= */
/* In-memory loopback simpleaudio backend.                       */
/* TX write appends; RX read pops; both share one float FIFO.    */
/* ============================================================= */

static float  *g_fifo   = NULL;
static size_t  g_cap    = 0;     /* allocated capacity (frames) */
static size_t  g_widx   = 0;     /* write index (frames) */
static size_t  g_ridx   = 0;     /* read index (frames) */
static size_t  g_silence_reads = 0;  /* count of all-silence reads (drain detector) */

static void fifo_reset(void)
{
    g_widx = 0;
    g_ridx = 0;
    g_silence_reads = 0;
}

static void fifo_ensure(size_t extra_frames)
{
    if ( g_widx + extra_frames <= g_cap )
        return;
    size_t newcap = g_cap ? g_cap * 2 : (1u << 20);
    while ( newcap < g_widx + extra_frames )
        newcap *= 2;
    float *p = realloc(g_fifo, newcap * sizeof(float));
    if ( !p ) { fprintf(stderr, "loopback fifo OOM\n"); exit(2); }
    g_fifo = p;
    g_cap = newcap;
}

static int lb_open(simpleaudio *sa, const char *dev, sa_direction_t dir,
                   sa_format_t fmt, unsigned int rate, unsigned int channels,
                   char *app, char *stream)
{
    (void)dev; (void)dir; (void)app; (void)stream;
    /* float, mono, matching the wrapper's stream config */
    if ( fmt != SA_SAMPLE_FORMAT_FLOAT || channels != 1 ) {
        fprintf(stderr, "loopback backend: expected float mono\n");
        return 0;
    }
    sa->backend_framesize = sizeof(float) * channels;
    sa->channels = channels;
    sa->rate = rate;
    sa->backend_handle = (void *)1;   /* non-NULL marker */
    return 1;
}

static ssize_t lb_write(simpleaudio *sa, void *buf, size_t nframes)
{
    (void)sa;
    fifo_ensure(nframes);
    memcpy(g_fifo + g_widx, buf, nframes * sizeof(float));
    g_widx += nframes;
    return (ssize_t)nframes;
}

static ssize_t lb_read(simpleaudio *sa, void *buf, size_t nframes)
{
    (void)sa;
    float *out = (float *)buf;
    size_t avail = (g_widx > g_ridx) ? (g_widx - g_ridx) : 0;
    size_t take = avail < nframes ? avail : nframes;
    if ( take ) {
        memcpy(out, g_fifo + g_ridx, take * sizeof(float));
        g_ridx += take;
    }
    /* pad the remainder with silence so the blocking contract returns nframes */
    if ( take < nframes ) {
        memset(out + take, 0, (nframes - take) * sizeof(float));
        if ( take == 0 )
            g_silence_reads++;
        else
            g_silence_reads = 0;
    } else {
        g_silence_reads = 0;
    }
    return (ssize_t)nframes;
}

static void lb_close(simpleaudio *sa) { sa->backend_handle = NULL; }

static const struct simpleaudio_backend lb_backend = {
    lb_open, lb_read, lb_write, lb_close,
};

/* Open a loopback stream directly (bypasses simpleaudio_open_stream's switch). */
static simpleaudio *lb_open_stream(sa_direction_t dir, unsigned int rate)
{
    simpleaudio *sa = calloc(1, sizeof(simpleaudio));
    if ( !sa ) return NULL;
    sa->backend = &lb_backend;
    sa->format = SA_SAMPLE_FORMAT_FLOAT;
    sa->samplesize = sizeof(float);
    if ( !lb_backend.simpleaudio_open_stream(sa, "0", dir,
            SA_SAMPLE_FORMAT_FLOAT, rate, 1, "lb", "lb") ) {
        free(sa);
        return NULL;
    }
    return sa;
}

/* ============================================================= */
/* One byte-exact round trip at a given baud.                    */
/* Returns 0 byte-exact, 1 decode mismatch, -1 setup failure.    */
/* ============================================================= */
static int run_one(int baud, const unsigned char *payload, size_t payload_len,
                   const char **why)
{
    *why = "";
    minimodem_ctx ctx;
    int rc = mm_build_config(&ctx, baud, 48000);
    if ( rc < 0 ) {
        *why = ctx.error;
        return -1;                     /* e.g. tone out of band at high baud */
    }

    fifo_reset();
    ctx.sa_out = lb_open_stream(SA_STREAM_PLAYBACK, ctx.sample_rate);
    ctx.sa_in  = lb_open_stream(SA_STREAM_RECORD,   ctx.sample_rate);
    if ( !ctx.sa_out || !ctx.sa_in ) {
        *why = "stream open failed";
        if ( ctx.sa_out ) simpleaudio_close(ctx.sa_out);
        if ( ctx.sa_in )  simpleaudio_close(ctx.sa_in);
        ctx.sa_out = ctx.sa_in = NULL;
        mm_destroy(&ctx);
        return -1;
    }

    simpleaudio_tone_init(4096, 1.0f);

    /* TX: append the whole modulated waveform to the shared FIFO. */
    if ( mm_tx_bytes(&ctx, payload, payload_len) < 0 ) {
        *why = "mm_tx_bytes failed";
        mm_destroy(&ctx);
        return -1;
    }

    /* RX: pump mm_rx_step until we've decoded payload_len bytes or the FIFO is
     * drained (several consecutive all-silence reads => no more frames). */
    unsigned char *got = malloc(payload_len + 64);
    if ( !got ) { mm_destroy(&ctx); *why = "OOM"; return -1; }
    size_t got_n = 0;
    char tmp[256];
    int guard = 0;
    const int max_guard = 1000000;     /* hard safety bound */

    while ( got_n < payload_len && guard++ < max_guard ) {
        int n = mm_rx_step(&ctx, tmp, sizeof(tmp));
        if ( n < 0 ) { *why = "mm_rx_step read error"; break; }
        for ( int i = 0; i < n && got_n < payload_len + 32; i++ )
            got[got_n++] = (unsigned char)tmp[i];
        /* FIFO drained and demod produced nothing more -> stop. */
        if ( g_silence_reads > 8 )
            break;
    }

    int result;
    if ( got_n == payload_len && memcmp(got, payload, payload_len) == 0 ) {
        result = 0;                    /* byte-exact */
    } else {
        result = 1;                    /* mismatch / short */
        if ( !**why ) {
            static char buf[128];
            snprintf(buf, sizeof(buf),
                     "decoded %zu of %zu bytes (carrier/decode issue)",
                     got_n, payload_len);
            *why = buf;
        }
    }

    free(got);
    mm_destroy(&ctx);
    return result;
}

/* ============================================================= */
int main(void)
{
    /* Build a representative payload: a fixed ASCII string + ~500 random bytes
     * (printable range to stay 8-N-1 safe) per WINMM-01 report-length case. */
    const char *prefix = "{\"id\":\"abc1234\",\"fn\":\"test\",\"ct\":\"Liver: normal.\",\"ci\":0,\"cc\":1}";
    size_t plen = strlen(prefix);

    size_t rand_len = 500;
    size_t total = plen + rand_len;
    unsigned char *payload = malloc(total);
    if ( !payload ) { fprintf(stderr, "OOM\n"); return 2; }
    memcpy(payload, prefix, plen);
    srand(12345);                      /* deterministic */
    for ( size_t i = 0; i < rand_len; i++ )
        payload[plen + i] = (unsigned char)(0x20 + (rand() % 0x5F));  /* printable ASCII */

    const int bauds[] = { 1200, 4800, 9600 };
    int gate_ok = 0;

    printf("=== minimodem_loopback: in-process byte-exact TX->RX ===\n");
    printf("payload: %zu bytes (%zu fixed + %zu random printable)\n\n",
           total, plen, rand_len);

    for ( size_t b = 0; b < sizeof(bauds)/sizeof(bauds[0]); b++ ) {
        const char *why = "";
        int r = run_one(bauds[b], payload, total, &why);
        if ( r == 0 ) {
            printf("[ OK   ] baud %5d : byte-exact (%zu bytes)\n", bauds[b], total);
            if ( bauds[b] == 1200 )
                gate_ok = 1;
        } else if ( bauds[b] == 1200 ) {
            printf("[ FAIL ] baud %5d : %s  <-- GATE\n", bauds[b], why);
        } else {
            printf("[ NOTE ] baud %5d : %s (tone override may be needed; not a gate failure)\n",
                   bauds[b], why);
        }
    }

    free(payload);

    printf("\n");
    if ( gate_ok ) {
        printf("GATE PASS: 1200-baud loopback is byte-exact.\n");
        return 0;
    }
    printf("GATE FAIL: 1200-baud loopback did NOT round-trip byte-exact.\n");
    return 1;
}
