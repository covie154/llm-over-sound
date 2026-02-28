#ifndef MINIMODEM_SIMPLE_H
#define MINIMODEM_SIMPLE_H

#include <stdint.h>

#ifdef _WIN32
#  ifdef MINIMODEM_SIMPLE_BUILD
#    define MINIMODEM_API __declspec(dllexport)
#  else
#    define MINIMODEM_API __declspec(dllimport)
#  endif
#else
#  define MINIMODEM_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Initialize the modem. Opens audio devices and starts background threads.
 * playbackDeviceId: PortAudio wrapper device index for output (-1 = default)
 * captureDeviceId:  PortAudio wrapper device index for input (-1 = default)
 * baud_rate:        FSK baud rate (1200, 2400, 4800, etc.)
 * Returns 0 on success, negative on error. */
MINIMODEM_API int minimodem_simple_init(int playbackDeviceId, int captureDeviceId, int baud_rate);

/* Clean up all resources. Stops threads, closes audio streams. */
MINIMODEM_API void minimodem_simple_cleanup(void);

/* Transmit binary data as FSK audio.
 * data: pointer to bytes to send
 * len:  number of bytes
 * Returns 0 on success, negative on error.
 * Non-blocking: queues waveform for background playback. */
MINIMODEM_API int minimodem_simple_send(const uint8_t *data, int len);

/* Check if a transmission is still in progress.
 * Returns 1 if transmitting, 0 if idle. */
MINIMODEM_API int minimodem_simple_is_transmitting(void);

/* Receive decoded data. Non-blocking.
 * buffer:     output buffer for received bytes
 * bufferSize: max bytes to write
 * Returns number of bytes received (0 if nothing available), negative on error. */
MINIMODEM_API int minimodem_simple_receive(uint8_t *buffer, int bufferSize);

/* Change baud rate. Reinitializes FSK parameters.
 * Returns 0 on success, negative on error. */
MINIMODEM_API int minimodem_simple_set_baud_rate(int baud_rate);

/* Get maximum recommended payload size per send() call.
 * With minimodem there is no hard per-frame limit — this returns a
 * practical maximum (e.g. 4096) for callers that need a bound. */
MINIMODEM_API int minimodem_simple_get_frame_len(void);

/* Device enumeration */
MINIMODEM_API int         minimodem_simple_get_playback_device_count(void);
MINIMODEM_API int         minimodem_simple_get_capture_device_count(void);
MINIMODEM_API const char* minimodem_simple_get_playback_device_name(int id);
MINIMODEM_API const char* minimodem_simple_get_capture_device_name(int id);

/* Get last error message (empty string if no error). */
MINIMODEM_API const char* minimodem_simple_get_error(void);

#ifdef __cplusplus
}
#endif

#endif /* MINIMODEM_SIMPLE_H */
