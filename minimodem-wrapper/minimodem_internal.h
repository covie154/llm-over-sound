/*
 * minimodem_internal.h
 *
 * Internal context struct + core FSK engine declarations for minimodem_simple.
 *
 * This hoists minimodem.c's main() locals — both the config derived from baud
 * and ALL loop-carried RX state — into a single `minimodem_ctx` so the
 * background RX thread (Plan 07-02) can drive one demod pass at a time without
 * any thread-unsafe function-statics. In particular the former function-static
 * `carrier_band` (minimodem.c ~line 1180) becomes a ctx field (Pitfall 1 /
 * Anti-Patterns).
 *
 * GPLv3 — derived from minimodem.c (Copyright (C) 2011-2020 Kamal Mostafa).
 */

#ifndef MINIMODEM_INTERNAL_H
#define MINIMODEM_INTERNAL_H

#include <stddef.h>
#include "simpleaudio.h"
#include "fsk.h"

typedef struct minimodem_ctx {

    /* ---- Config (set once in mm_build_config, derived from baud) ---- */
    float        bfsk_data_rate;            /* = baud */
    float        bfsk_mark_f;               /* derived from baud */
    float        bfsk_space_f;              /* derived from baud */
    float        band_width;                /* derived from baud (clamped <= data_rate) */
    unsigned int bfsk_n_data_bits;          /* = 8 */
    int          bfsk_nstartbits;           /* = 1 */
    float        bfsk_nstopbits;            /* = 1.0 */
    unsigned int sample_rate;               /* = 48000 */
    float        fsk_confidence_threshold;  /* = 1.5  (minimodem.c:519) */
    float        fsk_confidence_search_limit;/* = 2.3 (minimodem.c:528) */
    unsigned int bfsk_frame_n_bits;         /* = n_data + nstart + nstop = 10 */
    char         expect_data_string[64];    /* built by build_expect_bits_string() */
    unsigned int expect_n_bits;
    unsigned int expect_nsamples;
    float        nsamples_per_bit;
    unsigned int nsamples_overscan;
    unsigned int frame_nsamples;

    /* ---- TX state (was file-scope globals at minimodem.c:49-58) ---- */
    simpleaudio *sa_out;
    float        tx_bfsk_mark_f;
    unsigned int tx_bit_nsamples;
    int          tx_leader_bits_len;        /* = 2 */
    int          tx_trailer_bits_len;       /* = 2 */
    float        tx_amplitude;              /* TX tone magnitude (volume/100) */

    /* ---- RX loop-carried state (was main() locals 1056-1133) ---- */
    fsk_plan    *fskp;                       /* fsk_plan_new(), minimodem.c:1045 */
    float       *samplebuf;                  /* malloc'd, minimodem.c:1071 */
    size_t       samplebuf_size;
    size_t       samples_nvalid;
    unsigned int advance;
    int          carrier;
    float        confidence_total;
    float        amplitude_total;
    unsigned int nframes_decoded;
    size_t       carrier_nsamples;
    unsigned int noconfidence;
    float        track_amplitude;
    float        peak_confidence;
    int          carrier_band;               /* PROMOTED from minimodem.c:1180 static */
    simpleaudio *sa_in;

    /* ---- Error reporting (for minimodem_simple_get_error) ---- */
    char         error[256];

} minimodem_ctx;


/*
 * build_expect_bits_string — reused verbatim from minimodem.c:442-487.
 */
int
mm_build_expect_bits_string( char *expect_bits_string,
        int bfsk_nstartbits,
        int bfsk_n_data_bits,
        float bfsk_nstopbits,
        int invert_start_stop,
        int use_expect_bits,
        unsigned long long expect_bits );

/*
 * mm_fsk_transmit_frame — lifted verbatim from minimodem.c:81-112,
 * renamed and made non-static.
 */
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
        int bfsk_msb_first );

/*
 * mm_build_config — derive mark/space/band_width from baud and prepare the RX
 * fsk plan + sample buffer. Initializes every loop-carried RX field to its
 * loop-entry value. Returns 0 on success, negative on error (sets ctx->error).
 */
int
mm_build_config( minimodem_ctx *ctx, int baud, unsigned int sample_rate );

/*
 * mm_tx_bytes — transmit a byte buffer over ctx->sa_out: leader marks, then
 * per-byte 8-N-1 frames, then trailer marks. Returns 0 on success.
 * Requires ctx->sa_out to be an open playback stream.
 */
int
mm_tx_bytes( minimodem_ctx *ctx, const unsigned char *buf, size_t len );

/*
 * mm_rx_step — perform exactly ONE read-and-scan pass over ctx->sa_in and
 * append any decoded bytes to `out` (bounded by out_size). Returns the number
 * of bytes appended (0..N), or negative on a read error. All loop-carried
 * state persists in ctx between calls.
 */
int
mm_rx_step( minimodem_ctx *ctx, char *out, size_t out_size );

/*
 * mm_destroy — free samplebuf, destroy fsk plan, close any open streams.
 */
void
mm_destroy( minimodem_ctx *ctx );

#endif /* MINIMODEM_INTERNAL_H */
