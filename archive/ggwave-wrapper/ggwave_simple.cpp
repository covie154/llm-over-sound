/**
 * ggwave_simple.cpp - Simple wrapper for ggwave library
 * 
 * Provides easy-to-use functions for AHK integration
 */

#define GGWAVE_SIMPLE_BUILD

#include "ggwave_simple.h"
#include "../ggwave/include/ggwave/ggwave.h"

#include <SDL.h>
#include <string>
#include <vector>
#include <cstring>
#include <mutex>

// Internal state
static struct {
    bool initialized = false;
    ggwave_Instance instance = -1;
    int protocolId = 1;  // AUDIBLE_FAST by default
    
    SDL_AudioDeviceID devIdInp = 0;
    SDL_AudioDeviceID devIdOut = 0;
    SDL_AudioSpec obtainedSpecInp;
    SDL_AudioSpec obtainedSpecOut;
    
    std::string lastError;
    std::string receivedMessage;
    bool hasReceivedMessage = false;
    
    std::vector<uint8_t> txWaveform;
    size_t txWaveformPos = 0;
    bool isTransmitting = false;
    
    std::mutex mutex;
} g_state;

static void setError(const char* msg) {
    g_state.lastError = msg;
}

// ============== Device Enumeration ==============

GGWAVE_SIMPLE_API int ggwave_simple_get_playback_device_count(void) {
    if (SDL_Init(SDL_INIT_AUDIO) < 0) {
        setError(SDL_GetError());
        return -1;
    }
    return SDL_GetNumAudioDevices(SDL_FALSE);
}

GGWAVE_SIMPLE_API int ggwave_simple_get_capture_device_count(void) {
    if (SDL_Init(SDL_INIT_AUDIO) < 0) {
        setError(SDL_GetError());
        return -1;
    }
    return SDL_GetNumAudioDevices(SDL_TRUE);
}

GGWAVE_SIMPLE_API const char* ggwave_simple_get_playback_device_name(int deviceId) {
    return SDL_GetAudioDeviceName(deviceId, SDL_FALSE);
}

GGWAVE_SIMPLE_API const char* ggwave_simple_get_capture_device_name(int deviceId) {
    return SDL_GetAudioDeviceName(deviceId, SDL_TRUE);
}

// ============== Initialization ==============

GGWAVE_SIMPLE_API int ggwave_simple_init(int playbackDeviceId, int captureDeviceId, int protocolId) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    
    if (g_state.initialized) {
        setError("Already initialized");
        return -1;
    }
    
    // Initialize SDL
    if (SDL_Init(SDL_INIT_AUDIO) < 0) {
        setError(SDL_GetError());
        return -2;
    }
    
    SDL_SetHintWithPriority(SDL_HINT_AUDIO_RESAMPLING_MODE, "medium", SDL_HINT_OVERRIDE);
    
    g_state.protocolId = protocolId;
    
    // Setup playback device
    SDL_AudioSpec playbackSpec;
    SDL_zero(playbackSpec);
    playbackSpec.freq = 48000;  // GGWave::kDefaultSampleRate
    playbackSpec.format = AUDIO_S16SYS;
    playbackSpec.channels = 1;
    playbackSpec.samples = 16 * 1024;
    playbackSpec.callback = NULL;
    
    SDL_zero(g_state.obtainedSpecOut);
    
    if (playbackDeviceId >= 0) {
        g_state.devIdOut = SDL_OpenAudioDevice(
            SDL_GetAudioDeviceName(playbackDeviceId, SDL_FALSE),
            SDL_FALSE, &playbackSpec, &g_state.obtainedSpecOut, 0);
    } else {
        g_state.devIdOut = SDL_OpenAudioDevice(NULL, SDL_FALSE, &playbackSpec, &g_state.obtainedSpecOut, 0);
    }
    
    if (!g_state.devIdOut) {
        setError(SDL_GetError());
        return -3;
    }
    
    // Setup capture device
    SDL_AudioSpec captureSpec;
    captureSpec = g_state.obtainedSpecOut;
    captureSpec.freq = 48000;
    captureSpec.format = AUDIO_F32SYS;
    captureSpec.samples = 1024;
    
    SDL_zero(g_state.obtainedSpecInp);
    
    if (captureDeviceId >= 0) {
        g_state.devIdInp = SDL_OpenAudioDevice(
            SDL_GetAudioDeviceName(captureDeviceId, SDL_TRUE),
            SDL_TRUE, &captureSpec, &g_state.obtainedSpecInp, 0);
    } else {
        g_state.devIdInp = SDL_OpenAudioDevice(NULL, SDL_TRUE, &captureSpec, &g_state.obtainedSpecInp, 0);
    }
    
    if (!g_state.devIdInp) {
        SDL_CloseAudioDevice(g_state.devIdOut);
        g_state.devIdOut = 0;
        setError(SDL_GetError());
        return -4;
    }
    
    // Initialize ggwave
    ggwave_Parameters params = ggwave_getDefaultParameters();
    params.payloadLength = -1;  // Variable length
    params.sampleRateInp = (float)g_state.obtainedSpecInp.freq;
    params.sampleRateOut = (float)g_state.obtainedSpecOut.freq;
    params.sampleRate = 48000.0f;
    params.samplesPerFrame = 1024;
    params.sampleFormatInp = GGWAVE_SAMPLE_FORMAT_F32;
    params.sampleFormatOut = GGWAVE_SAMPLE_FORMAT_I16;
    params.operatingMode = GGWAVE_OPERATING_MODE_RX_AND_TX;
    
    g_state.instance = ggwave_init(params);
    if (g_state.instance < 0) {
        SDL_CloseAudioDevice(g_state.devIdInp);
        SDL_CloseAudioDevice(g_state.devIdOut);
        g_state.devIdInp = 0;
        g_state.devIdOut = 0;
        setError("Failed to initialize ggwave");
        return -5;
    }
    
    // Start audio devices
    SDL_PauseAudioDevice(g_state.devIdOut, SDL_FALSE);
    SDL_PauseAudioDevice(g_state.devIdInp, SDL_FALSE);
    
    g_state.initialized = true;
    return 0;
}

// ============== Send/Receive ==============

GGWAVE_SIMPLE_API int ggwave_simple_send(const char* message, int volume) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    
    if (!g_state.initialized) {
        setError("Not initialized");
        return -1;
    }
    
    if (!message || strlen(message) == 0) {
        setError("Empty message");
        return -2;
    }
    
    int msgLen = (int)strlen(message);
    
    // Query waveform size
    int waveformBytes = ggwave_encode(
        g_state.instance,
        message,
        msgLen,
        (ggwave_ProtocolId)g_state.protocolId,
        volume,
        nullptr,
        1);  // query = 1 to get size
    
    if (waveformBytes <= 0) {
        setError("Failed to encode message");
        return -3;
    }
    
    // Allocate and generate waveform
    g_state.txWaveform.resize(waveformBytes);
    
    int result = ggwave_encode(
        g_state.instance,
        message,
        msgLen,
        (ggwave_ProtocolId)g_state.protocolId,
        volume,
        g_state.txWaveform.data(),
        0);  // query = 0 to encode
    
    if (result <= 0) {
        setError("Failed to generate waveform");
        return -4;
    }
    
    // Queue the audio for playback
    if (SDL_QueueAudio(g_state.devIdOut, g_state.txWaveform.data(), waveformBytes) < 0) {
        setError(SDL_GetError());
        return -5;
    }
    
    g_state.isTransmitting = true;
    g_state.txWaveformPos = 0;
    
    return 0;
}

GGWAVE_SIMPLE_API int ggwave_simple_is_transmitting(void) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    
    if (!g_state.initialized) return 0;
    
    // Check if there's still audio queued for playback
    Uint32 queued = SDL_GetQueuedAudioSize(g_state.devIdOut);
    g_state.isTransmitting = (queued > 0);
    
    return g_state.isTransmitting ? 1 : 0;
}

GGWAVE_SIMPLE_API int ggwave_simple_process(void) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    
    if (!g_state.initialized) {
        setError("Not initialized");
        return -1;
    }
    
    // Only process input when not transmitting
    if (g_state.isTransmitting) {
        Uint32 queued = SDL_GetQueuedAudioSize(g_state.devIdOut);
        if (queued == 0) {
            g_state.isTransmitting = false;
        }
        return 0;
    }
    
    // Check for captured audio
    const int samplesPerFrame = 1024;
    const int bytesPerSample = sizeof(float);  // F32 format
    const int bytesNeeded = samplesPerFrame * bytesPerSample;
    
    Uint32 available = SDL_GetQueuedAudioSize(g_state.devIdInp);
    
    if ((int)available >= bytesNeeded) {
        std::vector<uint8_t> captureBuffer(bytesNeeded);
        
        if (SDL_DequeueAudio(g_state.devIdInp, captureBuffer.data(), bytesNeeded) == (Uint32)bytesNeeded) {
            char payload[256];
            
            int decoded = ggwave_ndecode(
                g_state.instance,
                captureBuffer.data(),
                bytesNeeded,
                payload,
                sizeof(payload) - 1);
            
            if (decoded > 0) {
                payload[decoded] = '\0';
                g_state.receivedMessage = payload;
                g_state.hasReceivedMessage = true;
            }
        }
        
        // Clear excess audio to prevent lag
        if (available > (Uint32)(bytesNeeded * 32)) {
            SDL_ClearQueuedAudio(g_state.devIdInp);
        }
    }
    
    return 0;
}

GGWAVE_SIMPLE_API int ggwave_simple_receive(char* buffer, int bufferSize) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    
    if (!g_state.hasReceivedMessage) {
        return 0;
    }
    
    int len = (int)g_state.receivedMessage.length();
    if (len >= bufferSize) {
        len = bufferSize - 1;
    }
    
    memcpy(buffer, g_state.receivedMessage.c_str(), len);
    buffer[len] = '\0';
    
    g_state.hasReceivedMessage = false;
    g_state.receivedMessage.clear();
    
    return len;
}

GGWAVE_SIMPLE_API int ggwave_simple_set_protocol(int protocolId) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    
    if (protocolId < 0 || protocolId >= GGWAVE_PROTOCOL_COUNT) {
        setError("Invalid protocol ID");
        return -1;
    }
    
    g_state.protocolId = protocolId;
    return 0;
}

// ============== Cleanup ==============

GGWAVE_SIMPLE_API void ggwave_simple_cleanup(void) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    
    if (!g_state.initialized) return;
    
    if (g_state.instance >= 0) {
        ggwave_free(g_state.instance);
        g_state.instance = -1;
    }
    
    if (g_state.devIdInp) {
        SDL_PauseAudioDevice(g_state.devIdInp, 1);
        SDL_CloseAudioDevice(g_state.devIdInp);
        g_state.devIdInp = 0;
    }
    
    if (g_state.devIdOut) {
        SDL_PauseAudioDevice(g_state.devIdOut, 1);
        SDL_CloseAudioDevice(g_state.devIdOut);
        g_state.devIdOut = 0;
    }
    
    SDL_Quit();
    
    g_state.initialized = false;
    g_state.txWaveform.clear();
    g_state.receivedMessage.clear();
    g_state.hasReceivedMessage = false;
}

GGWAVE_SIMPLE_API const char* ggwave_simple_get_error(void) {
    return g_state.lastError.c_str();
}
