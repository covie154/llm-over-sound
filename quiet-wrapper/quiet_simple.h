/**
 * quiet_simple.h — Simple DLL wrapper for libquiet + PortAudio
 *
 * Mirrors the ggwave_simple API pattern but uses quiet's modem profiles
 * for higher throughput (up to ~7500 bytes/frame with cable-64k).
 *
 * Key differences from ggwave_simple:
 *   - init() takes a profile name string instead of a numeric protocol ID
 *   - send() takes (data, len) for binary payloads (not null-terminated)
 *   - No process() function — PortAudio callbacks handle I/O automatically
 *   - get_frame_len() returns the max payload per frame for the active profile
 */

#ifndef QUIET_SIMPLE_H
#define QUIET_SIMPLE_H

#include <stdint.h>

#ifdef QUIET_SIMPLE_BUILD
    #define QUIET_SIMPLE_API __declspec(dllexport)
#else
    #define QUIET_SIMPLE_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize the quiet audio system.
 *
 * @param playbackDeviceId  Wrapper index of the output device, -1 for default
 * @param captureDeviceId   Wrapper index of the input device, -1 for default
 * @param profileName       Profile name from quiet-profiles.json (e.g. "cable-64k")
 * @param profilesPath      Path to quiet-profiles.json
 * @return 0 on success, negative on error
 */
QUIET_SIMPLE_API int quiet_simple_init(int playbackDeviceId, int captureDeviceId,
                                       const char *profileName,
                                       const char *profilesPath);

/**
 * Clean up and release all resources.
 * Safe to call even if init() was not called.
 */
QUIET_SIMPLE_API void quiet_simple_cleanup(void);

/**
 * Queue binary data for transmission.
 *
 * Data must not exceed get_frame_len() bytes. For larger payloads the
 * caller must chunk the data.
 *
 * @param data  Pointer to the payload bytes
 * @param len   Number of bytes to send
 * @return 0 on success, negative on error
 */
QUIET_SIMPLE_API int quiet_simple_send(const uint8_t *data, int len);

/**
 * Non-blocking receive.
 *
 * @param buffer      User buffer to write received frame into
 * @param bufferSize  Size of user buffer in bytes
 * @return Number of bytes written to buffer, 0 if no frame available,
 *         negative on error
 */
QUIET_SIMPLE_API int quiet_simple_receive(uint8_t *buffer, int bufferSize);

/**
 * Get the maximum frame payload length for the current profile.
 * @return Frame length in bytes, or 0 if not initialized
 */
QUIET_SIMPLE_API int quiet_simple_get_frame_len(void);

/**
 * Check if the encoder is still transmitting audio.
 * @return 1 if transmitting, 0 if idle
 */
QUIET_SIMPLE_API int quiet_simple_is_transmitting(void);

/**
 * Switch to a different profile (re-creates encoder and decoder).
 *
 * @param profileName  Profile name from quiet-profiles.json
 * @return 0 on success, negative on error
 */
QUIET_SIMPLE_API int quiet_simple_set_profile(const char *profileName);

/**
 * Get the number of available playback (output) devices.
 * @return Number of devices, or negative on error
 */
QUIET_SIMPLE_API int quiet_simple_get_playback_device_count(void);

/**
 * Get the number of available capture (input) devices.
 * @return Number of devices, or negative on error
 */
QUIET_SIMPLE_API int quiet_simple_get_capture_device_count(void);

/**
 * Get the name of a playback device by wrapper index.
 * @param deviceId  Wrapper device index (0-based)
 * @return Device name string (valid until cleanup), or NULL on error
 */
QUIET_SIMPLE_API const char *quiet_simple_get_playback_device_name(int deviceId);

/**
 * Get the name of a capture device by wrapper index.
 * @param deviceId  Wrapper device index (0-based)
 * @return Device name string (valid until cleanup), or NULL on error
 */
QUIET_SIMPLE_API const char *quiet_simple_get_capture_device_name(int deviceId);

/**
 * Get the last error message.
 * @return Error string (never NULL, empty if no error)
 */
QUIET_SIMPLE_API const char *quiet_simple_get_error(void);

#ifdef __cplusplus
}
#endif

#endif /* QUIET_SIMPLE_H */
