/*
 * mm_core.c
 *
 * minimodem.c's main() TX/RX loops, decomposed into a context-struct library.
 *
 * GPLv3 — derived from minimodem/src/minimodem.c
 *         (Copyright (C) 2011-2020 Kamal Mostafa <kamal@whence.com>).
 *
 * Decomposition map (07-RESEARCH.md § minimodem.c Decomposition):
 *   build_expect_bits_string (minimodem.c:442-487) -> mm_build_expect_bits_string (verbatim)
 *   fsk_transmit_frame       (minimodem.c:81-112)   -> mm_fsk_transmit_frame (verbatim, non-static)
 *   fsk_transmit_stdin body  (minimodem.c:114-250)  -> mm_tx_bytes (stdin/select/itimer/sighandler stripped)
 *   main() baud/tone deriv    (minimodem.c:882-965) -> mm_build_config
 *   main() RX prep            (minimodem.c:1037-1131)-> mm_build_config
 *   main() RX loop body       (minimodem.c:1137-1463)-> mm_rx_step (one pass per call; bytes -> out, not stdout)
 *   main() cleanup            (minimodem.c:1465-1480)-> mm_destroy
 *
 * Stripped: getopt/usage/version, benchmarks, sndfile/--file, signals,
 * stdin read / stdout write, baudot/callerid/uic/RTTY modes, --inverted,
 * --mark/--space overrides, sync bytes, carrier autodetect (-a).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>

#include "minimodem_internal.h"  /* pulls in simpleaudio.h + fsk.h */
#include "databits.h"

/* v1 transport is fixed 8-N-1 ASCII, non-inverted, lsb-first, no sync bytes. */
#define MM_INVERT_START_STOP   0
#define MM_MSB_FIRST           0


/* ===== build_expect_bits_string (verbatim, minimodem.c:442-487) ===== */
int
mm_build_expect_bits_string( char *expect_bits_string,
        int bfsk_nstartbits,
        int bfsk_n_data_bits,
        float bfsk_nstopbits,
        int invert_start_stop,
        int use_expect_bits,
        unsigned long long expect_bits )
{
    char start_bit_value = invert_start_stop ? '1' : '0';
    char stop_bit_value = invert_start_stop ? '0' : '1';
    int j = 0;
    if ( bfsk_nstopbits != 0.0f )
        expect_bits_string[j++] = stop_bit_value;
    int i;
    // Nb. only integer number of start bits works (for rx)
    for ( i=0; i<bfsk_nstartbits; i++ )
        expect_bits_string[j++] = start_bit_value;
    for ( i=0; i<bfsk_n_data_bits; i++,j++ ) {
        if ( use_expect_bits )
            expect_bits_string[j] = ( (expect_bits>>i)&1 ) + '0';
        else
            expect_bits_string[j] = 'd';
    }
    if ( bfsk_nstopbits != 0.0f )
        expect_bits_string[j++] = stop_bit_value;
    expect_bits_string[j] = 0;

    return j;
}


/* ===== fsk_transmit_frame (verbatim, minimodem.c:81-112; non-static) ===== */
void
mm_fsk_transmit_frame(
        simpleaudio *sa_out,
        unsigned int bits,
        unsigned int n_data_bits,
        size_t bit_nsamples,
        float bfsk_mark_f,
        float bfsk_space_f,
        float bfsk_nstartbits,
        float bfsk_nstopbits,
        int invert_start_stop,
        int bfsk_msb_first )
{
    int i;
    if ( bfsk_nstartbits > 0 )
        simpleaudio_tone(sa_out, invert_start_stop ? bfsk_mark_f : bfsk_space_f,
                bit_nsamples * bfsk_nstartbits);        // start
    for ( i=0; i<(int)n_data_bits; i++ ) {              // data
        unsigned int bit;
        if (bfsk_msb_first) {
            bit = ( bits >> (n_data_bits - i - 1) ) & 1;
        } else {
            bit = ( bits >> i ) & 1;
        }

        float tone_freq = bit == 1 ? bfsk_mark_f : bfsk_space_f;
        simpleaudio_tone(sa_out, tone_freq, bit_nsamples);
    }
    if ( bfsk_nstopbits > 0 )
        simpleaudio_tone(sa_out, invert_start_stop ? bfsk_space_f : bfsk_mark_f,
                bit_nsamples * bfsk_nstopbits);         // stop
}


/* ===== mm_build_config (minimodem.c:882-965 + 1037-1131) ===== */
int
mm_build_config( minimodem_ctx *ctx, int baud, unsigned int sample_rate )
{
    memset(ctx, 0, sizeof(*ctx));

    if ( baud <= 0 ) {
        snprintf(ctx->error, sizeof(ctx->error),
                "invalid baud rate %d (must be > 0)", baud);
        return -1;
    }
    if ( sample_rate == 0 )
        sample_rate = 48000;

    ctx->sample_rate = sample_rate;
    ctx->bfsk_data_rate = (float)baud;
    ctx->bfsk_n_data_bits = 8;
    ctx->bfsk_nstartbits = 1;
    ctx->bfsk_nstopbits = 1.0f;
    ctx->fsk_confidence_threshold = 1.5f;        /* minimodem.c:519 */
    ctx->fsk_confidence_search_limit = 2.3f;     /* minimodem.c:528 */
    ctx->tx_leader_bits_len = 2;
    ctx->tx_trailer_bits_len = 2;
    ctx->tx_amplitude = 1.0f;

    /* --- baud -> mark/space/band_width derivation (minimodem.c:900-934) --- */
    float bfsk_mark_f = 0, bfsk_space_f = 0, band_width = 0;
    int autodetect_shift;
    if ( ctx->bfsk_data_rate >= 400 ) {
        /* Bell 202: baud=1200 mark=1200 space=2200 */
        autodetect_shift = - ( ctx->bfsk_data_rate * 5 / 6 );
        bfsk_mark_f  = ctx->bfsk_data_rate / 2 + 600;
        bfsk_space_f = bfsk_mark_f - autodetect_shift;
        band_width = 200;
    } else if ( ctx->bfsk_data_rate >= 100 ) {
        /* Bell 103: baud=300 mark=1270 space=1070 */
        autodetect_shift = 200;
        bfsk_mark_f  = 1270;
        bfsk_space_f = bfsk_mark_f - autodetect_shift;
        band_width = 50;
    } else {
        /* RTTY-ish low baud */
        autodetect_shift = 170;
        bfsk_mark_f  = 1585;
        bfsk_space_f = bfsk_mark_f - autodetect_shift;
        band_width = 10;
    }

    /* restrict band_width to <= data rate (minimodem.c:959-961) */
    if ( band_width > ctx->bfsk_data_rate )
        band_width = ctx->bfsk_data_rate;

    /* sanitize confidence search limit (minimodem.c:963-965) */
    if ( ctx->fsk_confidence_search_limit < ctx->fsk_confidence_threshold )
        ctx->fsk_confidence_search_limit = ctx->fsk_confidence_threshold;

    ctx->bfsk_mark_f = bfsk_mark_f;
    ctx->bfsk_space_f = bfsk_space_f;
    ctx->band_width = band_width;

    /* n databits + start + stop bits (minimodem.c:942-947) */
    ctx->bfsk_frame_n_bits =
        ctx->bfsk_n_data_bits + ctx->bfsk_nstartbits + (unsigned int)ctx->bfsk_nstopbits;
    if ( ctx->bfsk_frame_n_bits > 64 ) {
        snprintf(ctx->error, sizeof(ctx->error),
                "total number of bits per frame must be <= 64");
        return -1;
    }

    /* --- TX derived state (minimodem.c:131-136) --- */
    ctx->tx_bit_nsamples = (unsigned int)(sample_rate / ctx->bfsk_data_rate + 0.5f);
    ctx->tx_bfsk_mark_f = ctx->bfsk_mark_f;

    /* --- RX prep (minimodem.c:1037-1131) --- */
    ctx->nsamples_per_bit = sample_rate / ctx->bfsk_data_rate;

    ctx->fskp = fsk_plan_new(sample_rate, ctx->bfsk_mark_f, ctx->bfsk_space_f,
                             ctx->band_width);
    if ( !ctx->fskp ) {
        /* high baud may push a tone outside the band plan (fsk.c:58) -
         * surface as an error, do not crash (Pitfall 6 / ASSUMPTION A2). */
        snprintf(ctx->error, sizeof(ctx->error),
                "fsk_plan_new() failed for baud=%d (mark=%.0fHz space=%.0fHz bw=%.0f) "
                "- tone likely out of band; lower baud or override tones",
                baud, ctx->bfsk_mark_f, ctx->bfsk_space_f, ctx->band_width);
        return -1;
    }

    /* sample buffer sizing (minimodem.c:1056-1071) */
    unsigned int nbits = 0;
    nbits += 1;                         /* prev stop bit */
    nbits += ctx->bfsk_nstartbits;      /* start bits */
    nbits += ctx->bfsk_n_data_bits;     /* data bits */
    nbits += 1;                         /* stop bit */

    size_t samplebuf_size = (size_t)(ceilf(ctx->nsamples_per_bit) * (nbits+1));
    samplebuf_size *= 2;                /* half-buf filling method */
#define MM_SAMPLE_BUF_DIVISOR 12
    if ( samplebuf_size < sample_rate / MM_SAMPLE_BUF_DIVISOR )
        samplebuf_size = sample_rate / MM_SAMPLE_BUF_DIVISOR;

    ctx->samplebuf_size = samplebuf_size;
    ctx->samplebuf = malloc(samplebuf_size * sizeof(float));
    if ( !ctx->samplebuf ) {
        snprintf(ctx->error, sizeof(ctx->error), "samplebuf malloc failed");
        fsk_plan_destroy(ctx->fskp);
        ctx->fskp = NULL;
        return -1;
    }

    /* overscan (minimodem.c:1090-1108) */
    float fsk_frame_overscan = 0.5f;
    ctx->nsamples_overscan =
        (unsigned int)(ctx->nsamples_per_bit * fsk_frame_overscan + 0.5f);
    if ( fsk_frame_overscan > 0.0f && ctx->nsamples_overscan == 0 )
        ctx->nsamples_overscan = 1;

    /* frame size (minimodem.c:1112-1113) */
    ctx->frame_nsamples =
        (unsigned int)(ctx->nsamples_per_bit * (float)ctx->bfsk_frame_n_bits + 0.5f);

    /* expect bits string (minimodem.c:1115-1131) */
    ctx->expect_n_bits = mm_build_expect_bits_string(
            ctx->expect_data_string,
            ctx->bfsk_nstartbits, ctx->bfsk_n_data_bits, ctx->bfsk_nstopbits,
            MM_INVERT_START_STOP, 0, 0);
    ctx->expect_nsamples =
        (unsigned int)(ctx->nsamples_per_bit * ctx->expect_n_bits);

    /* --- initialize ALL loop-carried RX state to loop-entry values --- */
    ctx->samples_nvalid  = 0;
    ctx->advance         = 0;
    ctx->carrier         = 0;
    ctx->confidence_total= 0;
    ctx->amplitude_total = 0;
    ctx->nframes_decoded = 0;
    ctx->carrier_nsamples= 0;
    ctx->noconfidence    = 0;
    ctx->track_amplitude = 0.0f;
    ctx->peak_confidence = 0.0f;
    ctx->carrier_band    = -1;   /* was function-static at minimodem.c:1180 */

    return 0;
}


/* ===== mm_tx_bytes (minimodem.c:114-250 minus stdin/select/itimer/signals) ===== */
int
mm_tx_bytes( minimodem_ctx *ctx, const unsigned char *buf, size_t len )
{
    if ( !ctx->sa_out )
        return -1;

    simpleaudio_tone_reset();   /* phase continuity */

    /* leader tone (mark) — minimodem.c:210-212 */
    int j;
    for ( j=0; j<ctx->tx_leader_bits_len; j++ )
        simpleaudio_tone(ctx->sa_out, ctx->bfsk_mark_f, ctx->tx_bit_nsamples);

    /* data bytes: 8-N-1 frames via mm_fsk_transmit_frame — minimodem.c:224-228 */
    for ( size_t i=0; i<len; i++ ) {
        unsigned int bits[2];
        unsigned int nwords = databits_encode_ascii8(bits, (char)buf[i]);
        for ( unsigned int w=0; w<nwords; w++ )
            mm_fsk_transmit_frame(ctx->sa_out, bits[w], ctx->bfsk_n_data_bits,
                    ctx->tx_bit_nsamples, ctx->bfsk_mark_f, ctx->bfsk_space_f,
                    ctx->bfsk_nstartbits, ctx->bfsk_nstopbits,
                    MM_INVERT_START_STOP, MM_MSB_FIRST);
    }

    /* trailer tone (mark) — replaces the SIGALRM flush (minimodem.c:64-66) */
    for ( j=0; j<ctx->tx_trailer_bits_len; j++ )
        simpleaudio_tone(ctx->sa_out, ctx->bfsk_mark_f, ctx->tx_bit_nsamples);

    return 0;
}


/* ===== mm_rx_step (minimodem.c:1137-1463 — ONE pass per call) ===== */
/*
 * Performs exactly one read-and-scan pass: shift samplebuf by `advance`,
 * refill via simpleaudio_read if half-empty (the blocking call), run
 * fsk_find_frame + confidence/refine, and on success decode bytes into `out`.
 * Returns number of bytes appended to `out` (0..N), or negative on read error.
 * All persistent state lives in ctx (never in function-statics).
 *
 * The carrier-autodetect block (minimodem.c:1179-1220) is intentionally
 * SKIPPED — tones are fixed and known from baud.
 */
int
mm_rx_step( minimodem_ctx *ctx, char *out, size_t out_size )
{
    if ( !ctx->sa_in || !ctx->fskp || !ctx->samplebuf )
        return -1;

    size_t out_n = 0;

    /* Shift samples by 'advance' (minimodem.c:1144-1156) */
    assert( ctx->advance <= ctx->samplebuf_size );
    if ( ctx->advance == ctx->samplebuf_size ) {
        ctx->samples_nvalid = 0;
        ctx->advance = 0;
    }
    if ( ctx->advance ) {
        if ( ctx->advance > ctx->samples_nvalid ) {
            /* not enough valid samples to advance yet; wait for next refill */
            return 0;
        }
        memmove(ctx->samplebuf, ctx->samplebuf + ctx->advance,
                (ctx->samplebuf_size - ctx->advance) * sizeof(float));
        ctx->samples_nvalid -= ctx->advance;
        ctx->advance = 0;
    }

    /* Refill if half-empty (minimodem.c:1158-1174) — blocking read */
    if ( ctx->samples_nvalid < ctx->samplebuf_size/2 ) {
        float  *samples_readptr = ctx->samplebuf + ctx->samples_nvalid;
        size_t  read_nsamples = ctx->samplebuf_size/2;
        assert( read_nsamples > 0 );
        assert( ctx->samples_nvalid + read_nsamples <= ctx->samplebuf_size );
        ssize_t r = simpleaudio_read(ctx->sa_in, samples_readptr, read_nsamples);
        if ( r < 0 ) {
            snprintf(ctx->error, sizeof(ctx->error), "simpleaudio_read: error");
            return -1;
        }
        ctx->samples_nvalid += r;
    }

    if ( ctx->samples_nvalid == 0 )
        return 0;

    /* (carrier-autodetect block skipped — fixed tones) */

    if ( ctx->samples_nvalid < ctx->expect_nsamples )
        return 0;

    /* try_max_nsamples (minimodem.c:1236-1241) */
    unsigned int try_max_nsamples;
    if ( ctx->carrier )
        try_max_nsamples = (unsigned int)(ctx->nsamples_per_bit * 0.75f + 0.5f);
    else
        try_max_nsamples = (unsigned int)ctx->nsamples_per_bit;
    try_max_nsamples += ctx->nsamples_overscan;

#define MM_FSK_ANALYZE_NSTEPS 3
    unsigned int try_step_nsamples = try_max_nsamples / MM_FSK_ANALYZE_NSTEPS;
    if ( try_step_nsamples == 0 )
        try_step_nsamples = 1;

    float confidence, amplitude;
    unsigned long long bits = 0;
    unsigned int frame_start_sample = 0;
    unsigned int try_first_sample;
    float try_confidence_search_limit;

    try_confidence_search_limit = ctx->fsk_confidence_search_limit;
    try_first_sample = ctx->carrier ? ctx->nsamples_overscan : 0;

    confidence = fsk_find_frame(ctx->fskp, ctx->samplebuf, ctx->expect_nsamples,
            try_first_sample,
            try_max_nsamples,
            try_step_nsamples,
            try_confidence_search_limit,
            ctx->expect_data_string,
            &bits,
            &amplitude,
            &frame_start_sample);

    int do_refine_frame = 0;

    if ( confidence < ctx->peak_confidence * 0.75f ) {
        do_refine_frame = 1;
        ctx->peak_confidence = 0;
    }

    /* no-confidence if amplitude drops below 25% of tracked amplitude */
    if ( amplitude < ctx->track_amplitude * 0.25f ) {
        confidence = 0;
    }

#define MM_FSK_MAX_NOCONFIDENCE_BITS 20

    if ( confidence <= ctx->fsk_confidence_threshold ) {

        if ( ++ctx->noconfidence > MM_FSK_MAX_NOCONFIDENCE_BITS ) {
            ctx->carrier_band = -1;
            if ( ctx->carrier ) {
                ctx->carrier = 0;
                ctx->carrier_nsamples = 0;
                ctx->confidence_total = 0;
                ctx->amplitude_total = 0;
                ctx->nframes_decoded = 0;
                ctx->track_amplitude = 0.0f;
            }
        }

        /* advance forward by try_max_nsamples and try again next call */
        ctx->advance = try_max_nsamples;
        return (int)out_n;
    }

    /* Add a frame's worth of samples (minimodem.c:1324) */
    ctx->carrier_nsamples += ctx->frame_nsamples;

    if ( ctx->carrier ) {
        ctx->carrier_nsamples += frame_start_sample;
        ctx->carrier_nsamples -= ctx->nsamples_overscan;
    } else {
        /* just acquired carrier */
        ctx->carrier = 1;
        databits_decode_ascii8(0, 0, 0, 0);  /* reset frame processor */
        do_refine_frame = 1;
    }

    if ( do_refine_frame ) {
        if ( confidence < INFINITY && try_step_nsamples > 1 ) {
#define MM_FSK_ANALYZE_NSTEPS_FINE 8
            try_step_nsamples = try_max_nsamples / MM_FSK_ANALYZE_NSTEPS_FINE;
            if ( try_step_nsamples == 0 )
                try_step_nsamples = 1;
            try_confidence_search_limit = INFINITY;
            float confidence2, amplitude2;
            unsigned long long bits2;
            unsigned int frame_start_sample2;
            confidence2 = fsk_find_frame(ctx->fskp, ctx->samplebuf, ctx->expect_nsamples,
                    try_first_sample,
                    try_max_nsamples,
                    try_step_nsamples,
                    try_confidence_search_limit,
                    ctx->expect_data_string,
                    &bits2,
                    &amplitude2,
                    &frame_start_sample2);
            if ( confidence2 > confidence ) {
                bits = bits2;
                amplitude = amplitude2;
                frame_start_sample = frame_start_sample2;
            }
        }
    }

    ctx->track_amplitude = ( ctx->track_amplitude + amplitude ) / 2;
    if ( ctx->peak_confidence < confidence )
        ctx->peak_confidence = confidence;

    ctx->confidence_total += confidence;
    ctx->amplitude_total += amplitude;
    ctx->nframes_decoded++;
    ctx->noconfidence = 0;

    /* advance past frame (minimodem.c:1407) */
    ctx->advance = frame_start_sample + ctx->frame_nsamples - ctx->nsamples_overscan;

    /* chop off the prev_stop bit (minimodem.c:1414-1416) */
    if ( ctx->bfsk_nstopbits != 0.0f )
        bits = bits >> 1;

    /* chop off framing bits (minimodem.c:1424-1428) */
    bits = bit_window(bits, ctx->bfsk_nstartbits, ctx->bfsk_n_data_bits);
    if ( MM_MSB_FIRST )
        bits = bit_reverse(bits, ctx->bfsk_n_data_bits);

    /* decode to bytes (minimodem.c:1431-1446) — bounded by out_size (Security V5) */
    char dataoutbuf[4096];
    unsigned int dataout_nbytes =
        databits_decode_ascii8(dataoutbuf, sizeof(dataoutbuf),
                               bits, (int)ctx->bfsk_n_data_bits);

    if ( dataout_nbytes == 0 )
        return (int)out_n;

    /* append to caller's out buffer, bounded */
    for ( unsigned int i=0; i<dataout_nbytes && out_n < out_size; i++ )
        out[out_n++] = dataoutbuf[i];

    return (int)out_n;
}


/* ===== mm_destroy (minimodem.c:1465-1480) ===== */
void
mm_destroy( minimodem_ctx *ctx )
{
    if ( !ctx )
        return;
    if ( ctx->samplebuf ) {
        free(ctx->samplebuf);
        ctx->samplebuf = NULL;
    }
    if ( ctx->fskp ) {
        fsk_plan_destroy(ctx->fskp);
        ctx->fskp = NULL;
    }
    if ( ctx->sa_in ) {
        simpleaudio_close(ctx->sa_in);
        ctx->sa_in = NULL;
    }
    if ( ctx->sa_out ) {
        simpleaudio_close(ctx->sa_out);
        ctx->sa_out = NULL;
    }
}
