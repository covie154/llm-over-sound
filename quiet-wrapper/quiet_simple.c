/**
 * quiet_simple.c — Simple DLL wrapper for libquiet + PortAudio
 *
 * Architecture:
 *   Encoder: raw quiet_encoder + our own PortAudio output stream.
 *            A custom callback calls quiet_encoder_emit() so we can
 *            detect when the transmit queue drains (is_transmitting).
 *   Decoder: quiet_portaudio_decoder which runs its own background
 *            thread and ring buffer. We poll with non-blocking recv.
 *
 * Thread safety:
 *   A pthread mutex guards all API calls that touch shared state.
 *   The PA callback reads g_state.encoder and writes the volatile
 *   is_transmitting flag without the mutex (safe on x86 for aligned
 *   single-word reads/writes; the callback must not block).
 */

#define QUIET_SIMPLE_BUILD

#include "quiet_simple.h"

#include <quiet.h>
#include <quiet-portaudio.h>
#include <portaudio.h>
#include <pthread.h>

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* MinGW may not define ssize_t in all C99 configurations */
#ifdef _WIN32
#  include <sys/types.h>
#  ifndef _SSIZE_T_DEFINED
     typedef intptr_t ssize_t;
#    define _SSIZE_T_DEFINED
#  endif
#endif

/* PortAudio callback buffer size — 16384 samples as recommended by quiet */
#define TX_BUFFER_SIZE  16384

#define MAX_ERR   512
#define MAX_PROF  256
#define MAX_PATH_ 1024

/* ================================================================
 * Global state (single-instance, same pattern as ggwave_simple)
 * ================================================================ */
static struct {
    int initialized;
    int pa_initialized;

    /* --- encoder (raw quiet + our PA stream) --- */
    quiet_encoder              *encoder;
    PaStream                   *tx_stream;
    float                      *tx_mono_buffer;
    size_t                      tx_buffer_size;
    int                         tx_num_channels;
    volatile int                is_transmitting;

    /* --- decoder (quiet portaudio wrapper) --- */
    quiet_portaudio_decoder    *decoder;

    /* --- profile / config --- */
    char    profile_name[MAX_PROF];
    char    profiles_path[MAX_PATH_];
    size_t  frame_len;

    /* --- device mapping (wrapper index -> PA index) --- */
    PaDeviceIndex *playback_map;
    PaDeviceIndex *capture_map;
    int            playback_count;
    int            capture_count;

    /* stored wrapper device IDs for set_profile re-creation */
    int playback_device_id;
    int capture_device_id;

    /* --- error --- */
    char last_error[MAX_ERR];

    pthread_mutex_t mutex;
} g_state = { .mutex = PTHREAD_MUTEX_INITIALIZER };

/* ------------------------------------------------------------------ */

static void set_error(const char *msg) {
    if (msg) {
        snprintf(g_state.last_error, MAX_ERR, "%s", msg);
    } else {
        g_state.last_error[0] = '\0';
    }
}

static void set_error_fmt(const char *fmt, const char *detail) {
    snprintf(g_state.last_error, MAX_ERR, fmt, detail);
}

/* ================================================================
 * PortAudio initialisation and device enumeration
 * ================================================================ */

static void build_device_maps(void) {
    int n = Pa_GetDeviceCount();
    if (n <= 0) {
        g_state.playback_count = 0;
        g_state.capture_count  = 0;
        return;
    }

    /* Count */
    int pb = 0, cap = 0;
    for (int i = 0; i < n; i++) {
        const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
        if (!info) continue;
        if (info->maxOutputChannels > 0) pb++;
        if (info->maxInputChannels  > 0) cap++;
    }

    free(g_state.playback_map);
    free(g_state.capture_map);
    g_state.playback_map = NULL;
    g_state.capture_map  = NULL;

    if (pb > 0) {
        g_state.playback_map = (PaDeviceIndex *)malloc(pb * sizeof(PaDeviceIndex));
        if (!g_state.playback_map) { g_state.playback_count = 0; g_state.capture_count = 0; return; }
    }
    if (cap > 0) {
        g_state.capture_map = (PaDeviceIndex *)malloc(cap * sizeof(PaDeviceIndex));
        if (!g_state.capture_map) { free(g_state.playback_map); g_state.playback_map = NULL; g_state.playback_count = 0; g_state.capture_count = 0; return; }
    }

    int pi = 0, ci = 0;
    for (int i = 0; i < n; i++) {
        const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
        if (!info) continue;
        if (info->maxOutputChannels > 0) g_state.playback_map[pi++] = i;
        if (info->maxInputChannels  > 0) g_state.capture_map[ci++]  = i;
    }
    g_state.playback_count = pb;
    g_state.capture_count  = cap;
}

static int ensure_pa(void) {
    if (g_state.pa_initialized) return 0;
    PaError err = Pa_Initialize();
    if (err != paNoError) {
        set_error_fmt("Pa_Initialize: %s", Pa_GetErrorText(err));
        return -1;
    }
    g_state.pa_initialized = 1;
    build_device_maps();
    return 0;
}

/* ================================================================
 * Encoder PortAudio callback
 * ================================================================ */

static int encoder_callback(const void *input,
                            void *output_v,
                            unsigned long frame_count,
                            const PaStreamCallbackTimeInfo *time_info,
                            PaStreamCallbackFlags flags,
                            void *user_data) {
    (void)input; (void)time_info; (void)flags; (void)user_data;

    float *output = (float *)output_v;
    int    nch    = g_state.tx_num_channels;
    quiet_encoder *enc = g_state.encoder;

    /* Zero everything first (silence by default) */
    memset(output, 0, frame_count * nch * sizeof(float));

    /* Defensive: encoder may be NULL during destroy/recreate transitions */
    if (!enc || !g_state.tx_mono_buffer) {
        g_state.is_transmitting = 0;
        return paContinue;
    }

    memset(g_state.tx_mono_buffer, 0, frame_count * sizeof(float));

    ssize_t written = quiet_encoder_emit(enc,
                                         g_state.tx_mono_buffer,
                                         frame_count);
    if (written > 0) {
        /* Copy mono samples into channel 0 of the interleaved buffer */
        for (unsigned long i = 0; i < (unsigned long)written; i++) {
            output[nch * i] = g_state.tx_mono_buffer[i];
        }
        g_state.is_transmitting = 1;
    } else {
        /* Queue empty (written < 0) or closed (written == 0) */
        g_state.is_transmitting = 0;
    }

    return paContinue;
}

/* ================================================================
 * Internal audio create / destroy (shared by init & set_profile)
 * ================================================================ */

static void destroy_audio(void) {
    if (g_state.tx_stream) {
        Pa_AbortStream(g_state.tx_stream);
        Pa_CloseStream(g_state.tx_stream);
        g_state.tx_stream = NULL;
    }
    if (g_state.encoder) {
        quiet_encoder_destroy(g_state.encoder);
        g_state.encoder = NULL;
    }
    if (g_state.decoder) {
        quiet_portaudio_decoder_close(g_state.decoder);
        quiet_portaudio_decoder_destroy(g_state.decoder);
        g_state.decoder = NULL;
    }
    free(g_state.tx_mono_buffer);
    g_state.tx_mono_buffer = NULL;
    g_state.is_transmitting = 0;
    g_state.frame_len = 0;
}

/**
 * Create encoder stream + decoder for the profile stored in g_state.
 * Caller must hold the mutex.  PortAudio must already be initialised.
 */
static int create_audio(void) {
    /* --- resolve PA device indices --- */
    PaDeviceIndex pa_out, pa_in;

    if (g_state.playback_device_id < 0) {
        pa_out = Pa_GetDefaultOutputDevice();
    } else if (g_state.playback_device_id < g_state.playback_count) {
        pa_out = g_state.playback_map[g_state.playback_device_id];
    } else {
        set_error("playback device index out of range");
        return -1;
    }

    if (g_state.capture_device_id < 0) {
        pa_in = Pa_GetDefaultInputDevice();
    } else if (g_state.capture_device_id < g_state.capture_count) {
        pa_in = g_state.capture_map[g_state.capture_device_id];
    } else {
        set_error("capture device index out of range");
        return -1;
    }

    if (pa_out == paNoDevice) { set_error("no output device"); return -2; }
    if (pa_in  == paNoDevice) { set_error("no input device");  return -3; }

    /* --- load profiles --- */
    quiet_encoder_options *enc_opt =
        quiet_encoder_profile_filename(g_state.profiles_path,
                                       g_state.profile_name);
    if (!enc_opt) {
        set_error_fmt("failed to load encoder profile '%s'",
                      g_state.profile_name);
        return -4;
    }

    quiet_decoder_options *dec_opt =
        quiet_decoder_profile_filename(g_state.profiles_path,
                                       g_state.profile_name);
    if (!dec_opt) {
        free(enc_opt);
        set_error_fmt("failed to load decoder profile '%s'",
                      g_state.profile_name);
        return -5;
    }

    /* --- output device info --- */
    const PaDeviceInfo *out_info = Pa_GetDeviceInfo(pa_out);
    double out_rate = out_info->defaultSampleRate;
    int nch = out_info->maxOutputChannels;
    if (nch > 2) nch = 2;

    /* --- create raw quiet encoder --- */
    g_state.encoder = quiet_encoder_create(enc_opt, (float)out_rate);
    if (!g_state.encoder) {
        free(enc_opt); free(dec_opt);
        set_error("quiet_encoder_create failed");
        return -6;
    }
    g_state.frame_len = quiet_encoder_get_frame_len(g_state.encoder);

    /* --- allocate mono buffer for the callback --- */
    g_state.tx_buffer_size  = TX_BUFFER_SIZE;
    g_state.tx_num_channels = nch;
    g_state.tx_mono_buffer  = (float *)calloc(TX_BUFFER_SIZE, sizeof(float));
    if (!g_state.tx_mono_buffer) {
        quiet_encoder_destroy(g_state.encoder);
        g_state.encoder = NULL;
        free(enc_opt); free(dec_opt);
        set_error("failed to allocate tx mono buffer");
        return -7;
    }

    /* --- open PA output stream with our callback --- */
    PaStreamParameters out_params;
    memset(&out_params, 0, sizeof(out_params));
    out_params.device           = pa_out;
    out_params.channelCount     = nch;
    out_params.sampleFormat     = paFloat32;
    out_params.suggestedLatency = out_info->defaultLowOutputLatency;

    PaError err = Pa_OpenStream(&g_state.tx_stream,
                                NULL,          /* no input */
                                &out_params,
                                out_rate,
                                TX_BUFFER_SIZE,
                                paNoFlag,
                                encoder_callback,
                                NULL);
    if (err != paNoError) {
        quiet_encoder_destroy(g_state.encoder);
        g_state.encoder = NULL;
        free(g_state.tx_mono_buffer);
        g_state.tx_mono_buffer = NULL;
        free(enc_opt); free(dec_opt);
        set_error_fmt("Pa_OpenStream (output): %s", Pa_GetErrorText(err));
        return -8;
    }

    err = Pa_StartStream(g_state.tx_stream);
    if (err != paNoError) {
        Pa_CloseStream(g_state.tx_stream);
        g_state.tx_stream = NULL;
        quiet_encoder_destroy(g_state.encoder);
        g_state.encoder = NULL;
        free(g_state.tx_mono_buffer);
        g_state.tx_mono_buffer = NULL;
        free(enc_opt); free(dec_opt);
        set_error_fmt("Pa_StartStream (output): %s", Pa_GetErrorText(err));
        return -9;
    }

    /* --- create portaudio decoder (background thread) --- */
    const PaDeviceInfo *in_info = Pa_GetDeviceInfo(pa_in);
    double in_rate = in_info->defaultSampleRate;

    g_state.decoder = quiet_portaudio_decoder_create(
        dec_opt, pa_in, in_info->defaultLowInputLatency, in_rate);
    if (!g_state.decoder) {
        /* Tear down encoder side */
        Pa_AbortStream(g_state.tx_stream);
        Pa_CloseStream(g_state.tx_stream);
        g_state.tx_stream = NULL;
        quiet_encoder_destroy(g_state.encoder);
        g_state.encoder = NULL;
        free(g_state.tx_mono_buffer);
        g_state.tx_mono_buffer = NULL;
        free(enc_opt); free(dec_opt);
        set_error("quiet_portaudio_decoder_create failed");
        return -10;
    }

    free(enc_opt);
    free(dec_opt);
    return 0;
}

/* ================================================================
 * Public API — Device enumeration
 * ================================================================ */

QUIET_SIMPLE_API int quiet_simple_get_playback_device_count(void) {
    pthread_mutex_lock(&g_state.mutex);
    if (ensure_pa() != 0) { pthread_mutex_unlock(&g_state.mutex); return -1; }
    int count = g_state.playback_count;
    pthread_mutex_unlock(&g_state.mutex);
    return count;
}

QUIET_SIMPLE_API int quiet_simple_get_capture_device_count(void) {
    pthread_mutex_lock(&g_state.mutex);
    if (ensure_pa() != 0) { pthread_mutex_unlock(&g_state.mutex); return -1; }
    int count = g_state.capture_count;
    pthread_mutex_unlock(&g_state.mutex);
    return count;
}

QUIET_SIMPLE_API const char *quiet_simple_get_playback_device_name(int deviceId) {
    pthread_mutex_lock(&g_state.mutex);
    if (ensure_pa() != 0) { pthread_mutex_unlock(&g_state.mutex); return NULL; }
    if (deviceId < 0 || deviceId >= g_state.playback_count) { pthread_mutex_unlock(&g_state.mutex); return NULL; }
    const PaDeviceInfo *info = Pa_GetDeviceInfo(g_state.playback_map[deviceId]);
    const char *name = info ? info->name : NULL;
    pthread_mutex_unlock(&g_state.mutex);
    return name;
}

QUIET_SIMPLE_API const char *quiet_simple_get_capture_device_name(int deviceId) {
    pthread_mutex_lock(&g_state.mutex);
    if (ensure_pa() != 0) { pthread_mutex_unlock(&g_state.mutex); return NULL; }
    if (deviceId < 0 || deviceId >= g_state.capture_count) { pthread_mutex_unlock(&g_state.mutex); return NULL; }
    const PaDeviceInfo *info = Pa_GetDeviceInfo(g_state.capture_map[deviceId]);
    const char *name = info ? info->name : NULL;
    pthread_mutex_unlock(&g_state.mutex);
    return name;
}

/* ================================================================
 * Public API — Lifecycle
 * ================================================================ */

QUIET_SIMPLE_API int quiet_simple_init(int playbackDeviceId,
                                       int captureDeviceId,
                                       const char *profileName,
                                       const char *profilesPath) {
    pthread_mutex_lock(&g_state.mutex);

    if (g_state.initialized) {
        set_error("already initialized");
        pthread_mutex_unlock(&g_state.mutex);
        return -1;
    }

    if (!profileName || !profilesPath) {
        set_error("profileName and profilesPath are required");
        pthread_mutex_unlock(&g_state.mutex);
        return -2;
    }

    if (ensure_pa() != 0) {
        pthread_mutex_unlock(&g_state.mutex);
        return -3;
    }

    /* Store config */
    snprintf(g_state.profile_name,  MAX_PROF,  "%s", profileName);
    snprintf(g_state.profiles_path, MAX_PATH_, "%s", profilesPath);
    g_state.playback_device_id = playbackDeviceId;
    g_state.capture_device_id  = captureDeviceId;

    int rc = create_audio();
    if (rc != 0) {
        pthread_mutex_unlock(&g_state.mutex);
        return rc;
    }

    g_state.initialized = 1;
    pthread_mutex_unlock(&g_state.mutex);
    return 0;
}

QUIET_SIMPLE_API void quiet_simple_cleanup(void) {
    pthread_mutex_lock(&g_state.mutex);

    destroy_audio();

    free(g_state.playback_map);
    g_state.playback_map   = NULL;
    g_state.playback_count = 0;

    free(g_state.capture_map);
    g_state.capture_map   = NULL;
    g_state.capture_count = 0;

    if (g_state.pa_initialized) {
        /* Allow the decoder's background consume thread to exit
         * before tearing down PortAudio (it polls Pa_IsStreamActive). */
        Pa_Sleep(150);
        Pa_Terminate();
        g_state.pa_initialized = 0;
    }

    g_state.initialized = 0;
    g_state.last_error[0] = '\0';

    pthread_mutex_unlock(&g_state.mutex);
}

/* ================================================================
 * Public API — Send / Receive
 * ================================================================ */

QUIET_SIMPLE_API int quiet_simple_send(const uint8_t *data, int len) {
    pthread_mutex_lock(&g_state.mutex);

    if (!g_state.initialized) {
        set_error("not initialized");
        pthread_mutex_unlock(&g_state.mutex);
        return -1;
    }
    if (!data || len <= 0) {
        set_error("invalid data or length");
        pthread_mutex_unlock(&g_state.mutex);
        return -2;
    }
    if ((size_t)len > g_state.frame_len) {
        set_error("data exceeds frame length");
        pthread_mutex_unlock(&g_state.mutex);
        return -3;
    }

    /* Mark transmitting BEFORE queuing so a racing callback can't
     * clear the flag before the data is visible in the queue. */
    g_state.is_transmitting = 1;

    ssize_t sent = quiet_encoder_send(g_state.encoder, data, (size_t)len);
    if (sent <= 0) {
        g_state.is_transmitting = 0;
        set_error(sent == 0 ? "encoder queue closed" : "quiet_encoder_send failed");
        pthread_mutex_unlock(&g_state.mutex);
        return -4;
    }

    pthread_mutex_unlock(&g_state.mutex);
    return 0;
}

QUIET_SIMPLE_API int quiet_simple_receive(uint8_t *buffer, int bufferSize) {
    pthread_mutex_lock(&g_state.mutex);

    if (!g_state.initialized) {
        set_error("not initialized");
        pthread_mutex_unlock(&g_state.mutex);
        return -1;
    }
    if (!buffer || bufferSize <= 0) {
        set_error("invalid buffer");
        pthread_mutex_unlock(&g_state.mutex);
        return -2;
    }

    ssize_t n = quiet_portaudio_decoder_recv(g_state.decoder,
                                             buffer,
                                             (size_t)bufferSize);
    if (n < 0) {
        /* quiet_would_block means no frame available yet — not an error */
        if (quiet_get_last_error() == quiet_would_block) {
            pthread_mutex_unlock(&g_state.mutex);
            return 0;
        }
        set_error("quiet_portaudio_decoder_recv failed");
        pthread_mutex_unlock(&g_state.mutex);
        return -3;
    }

    pthread_mutex_unlock(&g_state.mutex);
    return (int)n;
}

/* ================================================================
 * Public API — Status / Config
 * ================================================================ */

QUIET_SIMPLE_API int quiet_simple_get_frame_len(void) {
    pthread_mutex_lock(&g_state.mutex);
    int len = g_state.initialized ? (int)g_state.frame_len : 0;
    pthread_mutex_unlock(&g_state.mutex);
    return len;
}

QUIET_SIMPLE_API int quiet_simple_is_transmitting(void) {
    /* Volatile read — no mutex needed (single aligned int on x86). */
    return g_state.is_transmitting ? 1 : 0;
}

QUIET_SIMPLE_API int quiet_simple_set_profile(const char *profileName) {
    pthread_mutex_lock(&g_state.mutex);

    if (!g_state.initialized) {
        set_error("not initialized");
        pthread_mutex_unlock(&g_state.mutex);
        return -1;
    }
    if (!profileName) {
        set_error("profileName is required");
        pthread_mutex_unlock(&g_state.mutex);
        return -2;
    }

    destroy_audio();
    snprintf(g_state.profile_name, MAX_PROF, "%s", profileName);

    int rc = create_audio();
    if (rc != 0) {
        /* create_audio already set the error */
        g_state.initialized = 0;
        pthread_mutex_unlock(&g_state.mutex);
        return rc;
    }

    pthread_mutex_unlock(&g_state.mutex);
    return 0;
}

QUIET_SIMPLE_API const char *quiet_simple_get_error(void) {
    return g_state.last_error;
}
