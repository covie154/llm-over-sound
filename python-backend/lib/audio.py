"""
Audio device enumeration for minimodem (ALSA-based).
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


def list_devices():
    """List available ALSA audio devices to stdout."""
    print("\nAvailable ALSA Audio Devices:")
    print("=" * 80)

    # List capture (input) devices
    print("\n-- Capture (input) devices --")
    try:
        result = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("  (no capture devices found or arecord not available)")
    except FileNotFoundError:
        print("  (arecord not found — ALSA utils not installed)")
    except Exception as e:
        print(f"  (error listing capture devices: {e})")

    # List playback (output) devices
    print("-- Playback (output) devices --")
    try:
        result = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("  (no playback devices found or aplay not available)")
    except FileNotFoundError:
        print("  (aplay not found — ALSA utils not installed)")
    except Exception as e:
        print(f"  (error listing playback devices: {e})")

    print("=" * 80)
    print("Use --alsa-dev <device> to select a specific ALSA device (e.g., hw:1)")
    print()
