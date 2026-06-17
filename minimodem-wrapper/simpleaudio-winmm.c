/*
 * simpleaudio-winmm.c
 *
 * WinMM (waveOut / waveIn) backend for simpleaudio, implementing the
 * 4-function simpleaudio_backend struct. Modeled structurally on
 * simpleaudio-pulse.c / simpleaudio-alsa.c (the simplest blocking backends).
 *
 * Contract (must match ALSA/Pulse): simpleaudio_read / simpleaudio_write are
 * SYNCHRONOUS and BLOCKING -- they do not return until nframes frames have
 * been read / written. mm_rx_step depends on read() blocking; simpleaudio_tone
 * asserts write() > 0.
 *
 * Format: 48000 Hz, mono (1 channel). Requests WAVE_FORMAT_IEEE_FLOAT (RX uses
 * float for the FFT); falls back to WAVE_FORMAT_PCM S16 + manual S16-to-float
 * on WAVERR_BADFORMAT (ASSUMPTION A4).
 *
 * HARD RULES (07-RESEARCH Windows gotchas):
 *   - Never call waveOut / waveIn functions from inside a waveProc callback
 *     (deadlock): we use CALLBACK_EVENT, never CALLBACK_FUNCTION.
 *   - waveIn buffers are recycled (waveInAddBuffer) immediately after copy-out
 *     (Pitfall 2 -- starvation corrupts FSK).
 *   - waveOutReset / waveInReset before close.
 *
 * GPLv3 -- part of the minimodem_simple wrapper.
 */

#ifdef _WIN32

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include <windows.h>
#include <mmsystem.h>
#include <mmreg.h>

#ifndef WAVE_FORMAT_IEEE_FLOAT
#define WAVE_FORMAT_IEEE_FLOAT 0x0003
#endif

#include "simpleaudio.h"
#include "simpleaudio_internal.h"

/* Ring depth for both playback and capture WAVEHDRs (Claude's discretion). */
#define MM_NHDR 4

typedef struct {
    int          is_record;          /* 1 = waveIn (capture), 0 = waveOut */
    int          use_s16;            /* 1 = device gave S16, convert to float */
    unsigned int channels;
    unsigned int rate;

    /* playback */
    HWAVEOUT     hwo;
    HANDLE       out_event;
    WAVEHDR      out_hdr[MM_NHDR];
    char        *out_buf[MM_NHDR];
    size_t       out_buf_cap;        /* bytes capacity of each out_buf */
    unsigned int out_next;           /* next header to (re)use */

    /* capture */
    HWAVEIN      hwi;
    HANDLE       in_event;
    WAVEHDR      in_hdr[MM_NHDR];
    char        *in_buf[MM_NHDR];
    size_t       in_buf_cap;         /* bytes capacity of each in_buf */
    unsigned int in_head;            /* next header to consume */
    size_t       in_partial_frames;  /* frames already consumed from in_hdr[in_head] */
} winmm_state;


/* device index: backend_device parsed as integer; NULL/"-1" -> WAVE_MAPPER */
static UINT
mm_parse_device( const char *backend_device )
{
    if ( !backend_device )
        return WAVE_MAPPER;
    int idx = atoi(backend_device);
    if ( idx < 0 )
        return WAVE_MAPPER;
    return (UINT)idx;
}

static void
mm_make_format( WAVEFORMATEX *wfx, unsigned int rate, unsigned int channels,
                int use_s16 )
{
    memset(wfx, 0, sizeof(*wfx));
    wfx->wFormatTag = use_s16 ? WAVE_FORMAT_PCM : WAVE_FORMAT_IEEE_FLOAT;
    wfx->nChannels = (WORD)channels;
    wfx->nSamplesPerSec = rate;
    wfx->wBitsPerSample = (WORD)(use_s16 ? 16 : 32);
    wfx->nBlockAlign = (WORD)(wfx->nChannels * wfx->wBitsPerSample / 8);
    wfx->nAvgBytesPerSec = wfx->nSamplesPerSec * wfx->nBlockAlign;
    wfx->cbSize = 0;
}


/* ---------------------------------------------------------------- close */
static void
sa_winmm_close( simpleaudio *sa )
{
    winmm_state *w = (winmm_state *)sa->backend_handle;
    if ( !w )
        return;

    if ( w->is_record ) {
        if ( w->hwi ) {
            waveInStop(w->hwi);
            waveInReset(w->hwi);
            for ( int i=0; i<MM_NHDR; i++ ) {
                if ( w->in_hdr[i].dwFlags & WHDR_PREPARED )
                    waveInUnprepareHeader(w->hwi, &w->in_hdr[i], sizeof(WAVEHDR));
            }
            waveInClose(w->hwi);
            w->hwi = NULL;
        }
        if ( w->in_event ) { CloseHandle(w->in_event); w->in_event = NULL; }
        for ( int i=0; i<MM_NHDR; i++ ) { free(w->in_buf[i]); w->in_buf[i] = NULL; }
    } else {
        if ( w->hwo ) {
            /* drain: wait for all in-flight headers to finish */
            for ( int i=0; i<MM_NHDR; i++ ) {
                while ( (w->out_hdr[i].dwFlags & WHDR_PREPARED) &&
                       !(w->out_hdr[i].dwFlags & WHDR_DONE) )
                    WaitForSingleObject(w->out_event, 100);
            }
            waveOutReset(w->hwo);
            for ( int i=0; i<MM_NHDR; i++ ) {
                if ( w->out_hdr[i].dwFlags & WHDR_PREPARED )
                    waveOutUnprepareHeader(w->hwo, &w->out_hdr[i], sizeof(WAVEHDR));
            }
            waveOutClose(w->hwo);
            w->hwo = NULL;
        }
        if ( w->out_event ) { CloseHandle(w->out_event); w->out_event = NULL; }
        for ( int i=0; i<MM_NHDR; i++ ) { free(w->out_buf[i]); w->out_buf[i] = NULL; }
    }

    free(w);
    sa->backend_handle = NULL;
}


/* ---------------------------------------------------------------- write */
/* Blocking: returns only after all nframes have been queued to waveOut. */
static ssize_t
sa_winmm_write( simpleaudio *sa, void *buf, size_t nframes )
{
    winmm_state *w = (winmm_state *)sa->backend_handle;
    if ( !w || w->is_record )
        return -1;

    size_t framesize = sa->backend_framesize;     /* bytes per frame (caller's format) */
    size_t written = 0;
    const char *src = (const char *)buf;

    while ( written < nframes ) {
        WAVEHDR *h = &w->out_hdr[w->out_next];

        /* wait until this header is free (done or never used) */
        while ( (h->dwFlags & WHDR_PREPARED) && !(h->dwFlags & WHDR_DONE) )
            WaitForSingleObject(w->out_event, INFINITE);

        if ( h->dwFlags & WHDR_PREPARED ) {
            waveOutUnprepareHeader(w->hwo, h, sizeof(WAVEHDR));
            h->dwFlags = 0;
        }

        size_t cap_frames = w->out_buf_cap / (w->use_s16 ? sizeof(short)*w->channels
                                                          : sizeof(float)*w->channels);
        size_t chunk = nframes - written;
        if ( chunk > cap_frames )
            chunk = cap_frames;

        /* copy / convert into the header's device buffer */
        if ( w->use_s16 ) {
            /* caller buffer is float (simpleaudio float format) -> S16 */
            const float *fsrc = (const float *)(src + written * framesize);
            short *dst = (short *)w->out_buf[w->out_next];
            size_t nsamp = chunk * w->channels;
            for ( size_t i=0; i<nsamp; i++ ) {
                float v = fsrc[i];
                if ( v > 1.0f )  v = 1.0f;
                if ( v < -1.0f ) v = -1.0f;
                dst[i] = (short)(v * 32767.0f);
            }
            h->dwBufferLength = (DWORD)(nsamp * sizeof(short));
        } else {
            memcpy(w->out_buf[w->out_next], src + written * framesize,
                   chunk * framesize);
            h->dwBufferLength = (DWORD)(chunk * framesize);
        }

        h->lpData = w->out_buf[w->out_next];
        h->dwFlags = 0;
        if ( waveOutPrepareHeader(w->hwo, h, sizeof(WAVEHDR)) != MMSYSERR_NOERROR )
            return -1;
        if ( waveOutWrite(w->hwo, h, sizeof(WAVEHDR)) != MMSYSERR_NOERROR ) {
            waveOutUnprepareHeader(w->hwo, h, sizeof(WAVEHDR));
            return -1;
        }

        written += chunk;
        w->out_next = (w->out_next + 1) % MM_NHDR;
    }

    return (ssize_t)nframes;
}


/* ---------------------------------------------------------------- read */
/* Blocking: returns only after nframes have been read (Pitfall 2 recycle). */
static ssize_t
sa_winmm_read( simpleaudio *sa, void *buf, size_t nframes )
{
    winmm_state *w = (winmm_state *)sa->backend_handle;
    if ( !w || !w->is_record )
        return -1;

    size_t out_framesize = sa->backend_framesize;   /* caller's frame size (float) */
    size_t got = 0;
    char *out = (char *)buf;

    while ( got < nframes ) {
        WAVEHDR *h = &w->in_hdr[w->in_head];

        /* wait for this header to be filled */
        while ( !(h->dwFlags & WHDR_DONE) )
            WaitForSingleObject(w->in_event, INFINITE);

        size_t dev_framesize = w->use_s16 ? sizeof(short)*w->channels
                                          : sizeof(float)*w->channels;
        size_t avail_frames = h->dwBytesRecorded / dev_framesize;
        size_t take = avail_frames - w->in_partial_frames;
        if ( take > nframes - got )
            take = nframes - got;

        if ( w->use_s16 ) {
            const short *s = (const short *)(h->lpData +
                              w->in_partial_frames * dev_framesize);
            float *d = (float *)(out + got * out_framesize);
            size_t nsamp = take * w->channels;
            for ( size_t i=0; i<nsamp; i++ )
                d[i] = (float)s[i] / 32768.0f;
        } else {
            memcpy(out + got * out_framesize,
                   h->lpData + w->in_partial_frames * dev_framesize,
                   take * dev_framesize);
        }

        got += take;
        w->in_partial_frames += take;

        /* fully consumed this header? recycle it immediately */
        if ( w->in_partial_frames >= avail_frames ) {
            w->in_partial_frames = 0;
            h->dwFlags &= ~WHDR_DONE;
            h->dwBytesRecorded = 0;
            waveInAddBuffer(w->hwi, h, sizeof(WAVEHDR));
            w->in_head = (w->in_head + 1) % MM_NHDR;
        }
    }

    return (ssize_t)got;
}


/* ---------------------------------------------------------------- open */
static int
sa_winmm_open_stream(
        simpleaudio *sa,
        const char *backend_device,
        sa_direction_t sa_stream_direction,
        sa_format_t sa_format,
        unsigned int rate, unsigned int channels,
        char *app_name, char *stream_name )
{
    (void)app_name; (void)stream_name;

    winmm_state *w = calloc(1, sizeof(winmm_state));
    if ( !w )
        return 0;

    w->is_record = (sa_stream_direction == SA_STREAM_RECORD);
    w->channels = channels;
    w->rate = rate;
    /* device buffer matches the requested sa_format unless we must fall back */
    w->use_s16 = (sa_format == SA_SAMPLE_FORMAT_S16);

    UINT dev = mm_parse_device(backend_device);

    /* per-header buffer: ~quarter of a second worth, or read granularity.
     * Cap each header to a modest size; small enough for low latency, large
     * enough to avoid per-call churn at low baud. */
    size_t frames_per_hdr = rate / MM_NHDR;       /* ~0.25 s total across ring */
    if ( frames_per_hdr < 256 )
        frames_per_hdr = 256;

    WAVEFORMATEX wfx;

    if ( w->is_record ) {
        w->in_event = CreateEvent(NULL, FALSE, FALSE, NULL);
        if ( !w->in_event ) { free(w); return 0; }

        mm_make_format(&wfx, rate, channels, w->use_s16);
        MMRESULT mr = waveInOpen(&w->hwi, dev, &wfx,
                                 (DWORD_PTR)w->in_event, 0, CALLBACK_EVENT);
        if ( mr == WAVERR_BADFORMAT && !w->use_s16 ) {
            /* float not supported -> fall back to S16 + convert (A4) */
            w->use_s16 = 1;
            mm_make_format(&wfx, rate, channels, w->use_s16);
            mr = waveInOpen(&w->hwi, dev, &wfx,
                            (DWORD_PTR)w->in_event, 0, CALLBACK_EVENT);
        }
        if ( mr != MMSYSERR_NOERROR ) {
            CloseHandle(w->in_event);
            free(w);
            return 0;
        }

        size_t dev_framesize = w->use_s16 ? sizeof(short)*channels
                                          : sizeof(float)*channels;
        w->in_buf_cap = frames_per_hdr * dev_framesize;
        for ( int i=0; i<MM_NHDR; i++ ) {
            w->in_buf[i] = malloc(w->in_buf_cap);
            if ( !w->in_buf[i] ) {
                for ( int k=0; k<i; k++ ) free(w->in_buf[k]);
                waveInClose(w->hwi);
                CloseHandle(w->in_event);
                free(w);
                return 0;
            }
        }
        for ( int i=0; i<MM_NHDR; i++ ) {
            memset(&w->in_hdr[i], 0, sizeof(WAVEHDR));
            w->in_hdr[i].lpData = w->in_buf[i];
            w->in_hdr[i].dwBufferLength = (DWORD)w->in_buf_cap;
            waveInPrepareHeader(w->hwi, &w->in_hdr[i], sizeof(WAVEHDR));
            waveInAddBuffer(w->hwi, &w->in_hdr[i], sizeof(WAVEHDR));
        }
        w->in_head = 0;
        w->in_partial_frames = 0;
        waveInStart(w->hwi);

        /* The caller's frame size follows the REQUESTED sa_format; read()
         * converts the device's S16 frames to float when use_s16 fell back. */
        sa->backend_framesize = (sa_format == SA_SAMPLE_FORMAT_S16
                                 ? sizeof(short) : sizeof(float)) * channels;
    } else {
        w->out_event = CreateEvent(NULL, FALSE, FALSE, NULL);
        if ( !w->out_event ) { free(w); return 0; }

        mm_make_format(&wfx, rate, channels, w->use_s16);
        MMRESULT mr = waveOutOpen(&w->hwo, dev, &wfx,
                                  (DWORD_PTR)w->out_event, 0, CALLBACK_EVENT);
        if ( mr == WAVERR_BADFORMAT && !w->use_s16 ) {
            w->use_s16 = 1;
            mm_make_format(&wfx, rate, channels, w->use_s16);
            mr = waveOutOpen(&w->hwo, dev, &wfx,
                             (DWORD_PTR)w->out_event, 0, CALLBACK_EVENT);
        }
        if ( mr != MMSYSERR_NOERROR ) {
            CloseHandle(w->out_event);
            free(w);
            return 0;
        }

        size_t dev_framesize = w->use_s16 ? sizeof(short)*channels
                                          : sizeof(float)*channels;
        w->out_buf_cap = frames_per_hdr * dev_framesize;
        for ( int i=0; i<MM_NHDR; i++ ) {
            w->out_buf[i] = malloc(w->out_buf_cap);
            if ( !w->out_buf[i] ) {
                for ( int k=0; k<i; k++ ) free(w->out_buf[k]);
                waveOutClose(w->hwo);
                CloseHandle(w->out_event);
                free(w);
                return 0;
            }
            memset(&w->out_hdr[i], 0, sizeof(WAVEHDR));
        }
        w->out_next = 0;

        sa->backend_framesize = (sa_format == SA_SAMPLE_FORMAT_S16
                                 ? sizeof(short) : sizeof(float)) * channels;
    }

    sa->channels = channels;
    sa->rate = rate;
    sa->backend_handle = w;

    return 1;
}


const struct simpleaudio_backend simpleaudio_backend_winaudio = {
    sa_winmm_open_stream,
    sa_winmm_read,
    sa_winmm_write,
    sa_winmm_close,
};


/* ---------------------------------------------------------------- */
/* Device enumeration helpers (mirror ggwave integer-index API).     */
/* ---------------------------------------------------------------- */
int
mm_playback_device_count( void )
{
    return (int)waveOutGetNumDevs();
}

int
mm_capture_device_count( void )
{
    return (int)waveInGetNumDevs();
}

const char *
mm_playback_device_name( int deviceId )
{
    static char name[64];
    WAVEOUTCAPSA caps;
    if ( deviceId < 0 ) { strcpy(name, "Default"); return name; }
    if ( waveOutGetDevCapsA((UINT_PTR)deviceId, &caps, sizeof(caps))
            != MMSYSERR_NOERROR ) {
        name[0] = 0;
        return name;
    }
    snprintf(name, sizeof(name), "%s", caps.szPname);  /* szPname <= 31 chars */
    return name;
}

const char *
mm_capture_device_name( int deviceId )
{
    static char name[64];
    WAVEINCAPSA caps;
    if ( deviceId < 0 ) { strcpy(name, "Default"); return name; }
    if ( waveInGetDevCapsA((UINT_PTR)deviceId, &caps, sizeof(caps))
            != MMSYSERR_NOERROR ) {
        name[0] = 0;
        return name;
    }
    snprintf(name, sizeof(name), "%s", caps.szPname);
    return name;
}

#endif /* _WIN32 */
