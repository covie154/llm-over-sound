import pyaudio

def list_audio_devices():
    """List all available audio input and output devices."""
    p = pyaudio.PyAudio()
    
    print("=" * 80)
    print("AUDIO DEVICES")
    print("=" * 80)
    
    device_count = p.get_device_count()
    print(f"\nTotal devices found: {device_count}\n")
    
    # Get default devices
    try:
        default_input = p.get_default_input_device_info()
        default_input_index = default_input['index']
    except IOError:
        default_input_index = None
    
    try:
        default_output = p.get_default_output_device_info()
        default_output_index = default_output['index']
    except IOError:
        default_output_index = None
    
    # List all devices
    for i in range(device_count):
        try:
            device_info = p.get_device_info_by_index(i)
            
            # Determine device type
            is_input = device_info['maxInputChannels'] > 0
            is_output = device_info['maxOutputChannels'] > 0
            
            device_type = []
            if is_input:
                device_type.append("INPUT")
            if is_output:
                device_type.append("OUTPUT")
            
            type_str = " + ".join(device_type) if device_type else "NONE"
            
            # Check if default
            default_marker = ""
            if i == default_input_index:
                default_marker += " [DEFAULT INPUT]"
            if i == default_output_index:
                default_marker += " [DEFAULT OUTPUT]"
            
            # Print device info
            print(f"Device {i}: {device_info['name']}{default_marker}")
            print(f"  Type: {type_str}")
            print(f"  Max Input Channels: {device_info['maxInputChannels']}")
            print(f"  Max Output Channels: {device_info['maxOutputChannels']}")
            print(f"  Default Sample Rate: {device_info['defaultSampleRate']:.0f} Hz")
            print(f"  Host API: {p.get_host_api_info_by_index(device_info['hostApi'])['name']}")
            print()
            
        except Exception as e:
            print(f"Device {i}: Error reading device info - {e}\n")
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if default_input_index is not None:
        print(f"Default Input: Device {default_input_index} - {default_input['name']}")
    else:
        print("Default Input: Not available")
    
    if default_output_index is not None:
        print(f"Default Output: Device {default_output_index} - {default_output['name']}")
    else:
        print("Default Output: Not available")
    
    p.terminate()

if __name__ == "__main__":
    list_audio_devices()
