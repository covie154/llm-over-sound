"""
Audio device enumeration via the minimodem wrapper.

PyAudio has left the transport path (Phase 7): device enumeration now goes
through the wrapper's playback/capture device count/name calls instead of
``pyaudio.PyAudio()``. The printed format is preserved so ``--list`` output
stays familiar.
"""

from . import minimodem


def list_devices():
    """List available audio devices (via the minimodem wrapper) to stdout.

    Requires the wrapper to be initialized (``minimodem.init(...)``) so the
    underlying audio backend has enumerated its devices.
    """
    print("\nAvailable Audio Devices:")
    print("=" * 80)

    try:
        playback_count = minimodem.get_playback_device_count()
    except Exception:
        playback_count = 0
    try:
        capture_count = minimodem.get_capture_device_count()
    except Exception:
        capture_count = 0

    print("Playback (output) devices:")
    if playback_count <= 0:
        print("  (none)")
    for i in range(playback_count):
        try:
            name = minimodem.get_playback_device_name(i)
        except Exception:
            name = "<error>"
        print(f"  Device {i}: {name}  |  Out")
    print()

    print("Capture (input) devices:")
    if capture_count <= 0:
        print("  (none)")
    for i in range(capture_count):
        try:
            name = minimodem.get_capture_device_name(i)
        except Exception:
            name = "<error>"
        print(f"  Device {i}: {name}  |  In")
    print()
