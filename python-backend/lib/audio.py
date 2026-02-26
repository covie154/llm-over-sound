"""
Audio device enumeration and PyAudio helpers.
"""

import pyaudio


def list_devices(pa: pyaudio.PyAudio):
    """List all available audio devices to stdout."""
    print("\nAvailable Audio Devices:")
    print("=" * 80)

    device_count = pa.get_device_count()
    try:
        default_input = pa.get_default_input_device_info()["index"]
    except IOError:
        default_input = None
    try:
        default_output = pa.get_default_output_device_info()["index"]
    except IOError:
        default_output = None

    for i in range(device_count):
        try:
            info = pa.get_device_info_by_index(i)
            markers: list[str] = []
            if i == default_input:
                markers.append("DEFAULT INPUT")
            if i == default_output:
                markers.append("DEFAULT OUTPUT")
            marker_str = f" [{', '.join(markers)}]" if markers else ""

            in_ch = info["maxInputChannels"]
            out_ch = info["maxOutputChannels"]
            if in_ch > 0 or out_ch > 0:
                direction: list[str] = []
                if in_ch > 0:
                    direction.append(f"In:{in_ch}")
                if out_ch > 0:
                    direction.append(f"Out:{out_ch}")
                print(f"Device {i}: {info['name']}{marker_str}")
                print(f"  Channels: {', '.join(direction)}  |  Sample Rate: {info['defaultSampleRate']:.0f} Hz")
                print()
        except Exception:
            pass
