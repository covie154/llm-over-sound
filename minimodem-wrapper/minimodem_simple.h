/**
 * minimodem_simple.h - Simple wrapper for the minimodem FSK modem
 *
 * Mirrors the ggwave_simple.h API surface exactly so the AHK frontend keeps
 * its DllCall model and the Python ctypes binding stays symmetric. The only
 * API change vs. ggwave_simple is that the old `protocolId` parameter becomes
 * `baud` (and `set_protocol` becomes `set_baud`).
 *
 * NOTE: In Plan 07-01 these are declarations only; the bodies (public API +
 * background RX thread + queue) are implemented in Plan 07-02.
 */

#ifndef MINIMODEM_SIMPLE_H
#define MINIMODEM_SIMPLE_H

#ifdef _WIN32
    #ifdef MINIMODEM_SIMPLE_BUILD
        #define MINIMODEM_SIMPLE_API __declspec(dllexport)
    #else
        #define MINIMODEM_SIMPLE_API __declspec(dllimport)
    #endif
#else
    /* Linux/.so build: default visibility export */
    #ifdef MINIMODEM_SIMPLE_BUILD
        #define MINIMODEM_SIMPLE_API __attribute__((visibility("default")))
    #else
        #define MINIMODEM_SIMPLE_API
    #endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize the minimodem system with specified audio devices.
 *
 * @param playbackDeviceId  Index of the playback device (speaker), -1 for default
 * @param captureDeviceId   Index of the capture device (microphone), -1 for default
 * @param baud              FSK baud rate (link parameter; both ends MUST match).
 *                          Default recommended: 1200.
 * @return 0 on success, negative on error
 */
MINIMODEM_SIMPLE_API int minimodem_simple_init(int playbackDeviceId, int captureDeviceId, int baud);

/**
 * Get the number of available playback devices.
 * @return Number of playback devices
 */
MINIMODEM_SIMPLE_API int minimodem_simple_get_playback_device_count(void);

/**
 * Get the number of available capture devices.
 * @return Number of capture devices
 */
MINIMODEM_SIMPLE_API int minimodem_simple_get_capture_device_count(void);

/**
 * Get the name of a playback device.
 * @param deviceId  Device index
 * @return Device name string (valid until next call or cleanup)
 */
MINIMODEM_SIMPLE_API const char* minimodem_simple_get_playback_device_name(int deviceId);

/**
 * Get the name of a capture device.
 * @param deviceId  Device index
 * @return Device name string (valid until next call or cleanup)
 */
MINIMODEM_SIMPLE_API const char* minimodem_simple_get_capture_device_name(int deviceId);

/**
 * Send a text message via audio (FSK modulation to the playback device).
 *
 * @param message   Null-terminated string to send
 * @param volume    Volume level (1-100); maps to TX tone amplitude
 * @return 0 on success, negative on error
 */
MINIMODEM_SIMPLE_API int minimodem_simple_send(const char* message, int volume);

/**
 * Check if currently transmitting.
 * @return 1 if transmitting, 0 if not
 */
MINIMODEM_SIMPLE_API int minimodem_simple_is_transmitting(void);

/**
 * Process housekeeping (called regularly by the frontend loop).
 * With the background RX thread doing the demod pumping, this is a near no-op
 * kept for API compatibility with the ggwave wrapper.
 * @return 0 on success, negative on error
 */
MINIMODEM_SIMPLE_API int minimodem_simple_process(void);

/**
 * Drain one received newline-delimited message into buffer.
 * @return Length of received message, 0 if none, negative on error
 */
MINIMODEM_SIMPLE_API int minimodem_simple_receive(char* buffer, int bufferSize);

/**
 * Set the FSK baud rate (rebuilds the fsk plan). Replaces set_protocol.
 * @param baud  Baud rate (both ends MUST match)
 * @return 0 on success, negative on error
 */
MINIMODEM_SIMPLE_API int minimodem_simple_set_baud(int baud);

/**
 * Clean up and release all resources (joins the RX thread, closes streams).
 */
MINIMODEM_SIMPLE_API void minimodem_simple_cleanup(void);

/**
 * Get the last error message.
 * @return Error message string
 */
MINIMODEM_SIMPLE_API const char* minimodem_simple_get_error(void);

#ifdef __cplusplus
}
#endif

#endif // MINIMODEM_SIMPLE_H
