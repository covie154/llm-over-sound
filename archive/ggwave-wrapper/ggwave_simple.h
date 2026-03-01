/**
 * ggwave_simple.h - Simple wrapper for ggwave library
 * 
 * Provides easy-to-use functions for AHK integration
 */

#ifndef GGWAVE_SIMPLE_H
#define GGWAVE_SIMPLE_H

#ifdef GGWAVE_SIMPLE_BUILD
    #define GGWAVE_SIMPLE_API __declspec(dllexport)
#else
    #define GGWAVE_SIMPLE_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize the ggwave system with specified audio devices
 * 
 * @param playbackDeviceId  Index of the playback device (speaker), -1 for default
 * @param captureDeviceId   Index of the capture device (microphone), -1 for default
 * @param protocolId        Protocol to use for transmission (1 = AUDIBLE_FAST recommended)
 * @return 0 on success, negative on error
 */
GGWAVE_SIMPLE_API int ggwave_simple_init(int playbackDeviceId, int captureDeviceId, int protocolId);

/**
 * Get the number of available playback devices
 * @return Number of playback devices
 */
GGWAVE_SIMPLE_API int ggwave_simple_get_playback_device_count(void);

/**
 * Get the number of available capture devices
 * @return Number of capture devices
 */
GGWAVE_SIMPLE_API int ggwave_simple_get_capture_device_count(void);

/**
 * Get the name of a playback device
 * @param deviceId  Device index
 * @return Device name string (valid until next call or cleanup)
 */
GGWAVE_SIMPLE_API const char* ggwave_simple_get_playback_device_name(int deviceId);

/**
 * Get the name of a capture device
 * @param deviceId  Device index
 * @return Device name string (valid until next call or cleanup)
 */
GGWAVE_SIMPLE_API const char* ggwave_simple_get_capture_device_name(int deviceId);

/**
 * Send a text message via audio
 * 
 * @param message   Null-terminated string to send
 * @param volume    Volume level (1-100, recommended: 25-50)
 * @return 0 on success, negative on error
 */
GGWAVE_SIMPLE_API int ggwave_simple_send(const char* message, int volume);

/**
 * Check if currently transmitting
 * @return 1 if transmitting, 0 if not
 */
GGWAVE_SIMPLE_API int ggwave_simple_is_transmitting(void);

/**
 * Process audio (must be called regularly in a loop)
 * This handles both sending and receiving
 * @return 0 on success, negative on error
 */
GGWAVE_SIMPLE_API int ggwave_simple_process(void);

/**
 * Check if a message has been received
 * @return Length of received message, 0 if none, negative on error
 */
GGWAVE_SIMPLE_API int ggwave_simple_receive(char* buffer, int bufferSize);

/**
 * Set the transmission protocol
 * @param protocolId  Protocol ID (see ggwave_ProtocolId enum)
 * @return 0 on success, negative on error
 * 
 * Common protocols:
 *   0 = AUDIBLE_NORMAL
 *   1 = AUDIBLE_FAST
 *   2 = AUDIBLE_FASTEST
 *   3 = ULTRASOUND_NORMAL
 *   4 = ULTRASOUND_FAST
 *   5 = ULTRASOUND_FASTEST
 */
GGWAVE_SIMPLE_API int ggwave_simple_set_protocol(int protocolId);

/**
 * Clean up and release all resources
 */
GGWAVE_SIMPLE_API void ggwave_simple_cleanup(void);

/**
 * Get the last error message
 * @return Error message string
 */
GGWAVE_SIMPLE_API const char* ggwave_simple_get_error(void);

#ifdef __cplusplus
}
#endif

#endif // GGWAVE_SIMPLE_H
