#!/usr/bin/env python3
"""
Test script to play a ggwave encoded message on a specified output device.
Usage: python test-output-audio.py -d 1
"""

import argparse
import pyaudio
import ggwave
import sys


def list_output_devices(p):
    """List all available output devices."""
    print("\nAvailable Output Devices:")
    print("=" * 80)
    
    device_count = p.get_device_count()
    output_devices = []
    
    for i in range(device_count):
        try:
            device_info = p.get_device_info_by_index(i)
            if device_info['maxOutputChannels'] > 0:
                output_devices.append(i)
                default_marker = ""
                try:
                    default_output = p.get_default_output_device_info()
                    if i == default_output['index']:
                        default_marker = " [DEFAULT]"
                except IOError:
                    pass
                
                print(f"Device {i}: {device_info['name']}{default_marker}")
                print(f"  Max Output Channels: {device_info['maxOutputChannels']}")
                print(f"  Default Sample Rate: {device_info['defaultSampleRate']:.0f} Hz")
                print()
        except Exception as e:
            pass
    
    return output_devices


def play_message(device_index, message="Hello World!", protocol_id=1, volume=50):
    """
    Encode and play a message using ggwave.
    
    Args:
        device_index: PyAudio device index for output
        message: Text message to encode and play
        protocol_id: ggwave protocol ID (1 = Audible Fast)
        volume: Volume level (0-100)
    """
    p = pyaudio.PyAudio()
    
    try:
        # Validate device
        device_info = p.get_device_info_by_index(device_index)
        if device_info['maxOutputChannels'] == 0:
            print(f"Error: Device {device_index} is not an output device!")
            list_output_devices(p)
            p.terminate()
            return False
        
        print(f"Using Output Device: {device_index} - {device_info['name']}")
        print(f"Message: \"{message}\"")
        print(f"Protocol: {protocol_id} (Audible Fast)")
        print(f"Volume: {volume}")
        print()
        
        # Initialize ggwave
        instance = ggwave.init()
        
        # Encode the message
        print("Encoding message...")
        waveform = ggwave.encode(message, protocolId=protocol_id, volume=volume)
        
        # Open output stream
        stream_output = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=48000,
            output=True,
            output_device_index=device_index,
            frames_per_buffer=4096
        )
        
        # Play the waveform
        print("Playing audio...")
        stream_output.write(waveform, len(waveform)//4)
        print("Playback complete!")
        
        # Cleanup
        stream_output.stop_stream()
        stream_output.close()
        ggwave.free(instance)
        p.terminate()
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        p.terminate()
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Play a ggwave encoded message on a specified output device.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test-output-audio.py -d 1
  python test-output-audio.py --device 3 --message "Test message"
  python test-output-audio.py -l
        """
    )
    
    parser.add_argument(
        '-d', '--device',
        type=int,
        help='Output device index'
    )
    
    parser.add_argument(
        '-m', '--message',
        type=str,
        default='Hello World!',
        help='Message to encode and play (default: "Hello World!")'
    )
    
    parser.add_argument(
        '-p', '--protocol',
        type=int,
        default=1,
        help='ggwave protocol ID (default: 1 = Audible Fast)'
    )
    
    parser.add_argument(
        '-v', '--volume',
        type=int,
        default=50,
        help='Volume level 0-100 (default: 50)'
    )
    
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List available output devices and exit'
    )
    
    args = parser.parse_args()
    
    # List devices if requested
    if args.list:
        p = pyaudio.PyAudio()
        list_output_devices(p)
        p.terminate()
        return
    
    # Check if device was specified
    if args.device is None:
        print("Error: Please specify an output device using -d or --device")
        print("Use -l or --list to see available devices")
        print()
        parser.print_help()
        sys.exit(1)
    
    # Play the message
    success = play_message(
        device_index=args.device,
        message=args.message,
        protocol_id=args.protocol,
        volume=args.volume
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
