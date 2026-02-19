#!/usr/bin/env python3
#%%
"""
Dummy Backend Server for AHK ggwave 
"""

import sys
import json
import argparse
import ggwave
import sounddevice
import pyaudio
import logging
import os
from datetime import datetime

# ==================== Logging Configuration ====================
LOG_ENABLED = True
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_log.txt")
LOG_MAX_CONTENT_LENGTH = 500  # Truncate long messages in log

# Setup logging
def setup_logging():
    """Configure logging with both file and console output."""
    if not LOG_ENABLED:
        logging.disable(logging.CRITICAL)
        return
    
    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Setup logger
    logger = logging.getLogger('ggwave_backend')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def truncate_for_log(text: str) -> str:
    """Truncate long text for logging."""
    text = text.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')
    if len(text) > LOG_MAX_CONTENT_LENGTH:
        return text[:LOG_MAX_CONTENT_LENGTH] + f"... [truncated, {len(text)} total chars]"
    return text

def log_session_start():
    """Log session start with separator."""
    separator = "=" * 80
    logger.info(separator)
    logger.info("ggwave Backend Session Started")
    logger.info(separator)

def log_session_end(reason: str = "Normal"):
    """Log session end."""
    logger.info(f"Session ending - Reason: {reason}")

p = pyaudio.PyAudio()


def list_devices(p):
    """List all available audio devices."""
    print("\nAvailable Audio Devices:")
    print("=" * 80)

    device_count = p.get_device_count()
    try:
        default_input = p.get_default_input_device_info()['index']
    except IOError:
        default_input = None
    try:
        default_output = p.get_default_output_device_info()['index']
    except IOError:
        default_output = None

    for i in range(device_count):
        try:
            info = p.get_device_info_by_index(i)
            markers = []
            if i == default_input:
                markers.append("DEFAULT INPUT")
            if i == default_output:
                markers.append("DEFAULT OUTPUT")
            marker_str = f" [{', '.join(markers)}]" if markers else ""

            in_ch = info['maxInputChannels']
            out_ch = info['maxOutputChannels']
            if in_ch > 0 or out_ch > 0:
                direction = []
                if in_ch > 0:
                    direction.append(f"In:{in_ch}")
                if out_ch > 0:
                    direction.append(f"Out:{out_ch}")
                print(f"Device {i}: {info['name']}{marker_str}")
                print(f"  Channels: {', '.join(direction)}  |  Sample Rate: {info['defaultSampleRate']:.0f} Hz")
                print()
        except Exception:
            pass


def process_input(message: str) -> dict:
    """
    Process the input message and return a response.
    
    
    
    Args:
        message: The input message from the AHK frontend in JSON
        
        Message format:
        {
            "id": <unique_id, str of len 7>,
            "fn": <function_name, str>,
            "ct": <content, str>
        }
        
    Returns:
        The processed response to send back
        
        Message format:
        {
            "id": <unique_id, str of len 7>,
            "st": <status, S for success, E for error>,
            "ct": <content, str>
        }
    """
    
    # Validation
    try:
        msg_dict = json.loads(message)
    except json.JSONDecodeError:
        return {
            "id": "",
            "st": "E",
            "ct": "Invalid JSON format"
        }
    
    
    response = {
        "id": msg_dict["id"],
        "st": "S",
        "ct": f"Processed function {msg_dict.get('fn', '')} with content: {msg_dict.get('ct', '')}"
        
    }
    return response


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='ggwave backend server for AHK frontend.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend.py
  python backend.py -i 5 -o 3
  python backend.py -i 5 -o 3 -v 80 -p 2
  python backend.py -l
        """
    )

    parser.add_argument(
        '-i', '--input-device',
        type=int,
        default=None,
        help='Input device index (default: system default)'
    )
    parser.add_argument(
        '-o', '--output-device',
        type=int,
        default=None,
        help='Output device index (default: system default)'
    )
    parser.add_argument(
        '-v', '--volume',
        type=int,
        default=50,
        help='Transmission volume level 0-100 (default: 50)'
    )
    parser.add_argument(
        '-p', '--protocol',
        type=int,
        default=1,
        help='ggwave protocol ID (default: 1 = Audible Fast)'
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List available audio devices and exit'
    )

    return parser.parse_args()


def main():
    """Main loop - Listen for input from ggwave, then process and transmit response."""
    
    args = parse_args()

    # List devices if requested
    if args.list:
        list_devices(p)
        p.terminate()
        return

    log_session_start()

    input_device_index = args.input_device
    output_device_index = args.output_device
    volume = args.volume
    protocol_id = args.protocol

    # Build stream kwargs so None means "use system default"
    input_kwargs = dict(format=pyaudio.paFloat32, channels=1, rate=48000, input=True, frames_per_buffer=1024)
    if input_device_index is not None:
        input_kwargs['input_device_index'] = input_device_index

    output_kwargs = dict(format=pyaudio.paFloat32, channels=1, rate=48000, output=True, frames_per_buffer=4096)
    if output_device_index is not None:
        output_kwargs['output_device_index'] = output_device_index

    stream_input = p.open(**input_kwargs)
    stream_output = p.open(**output_kwargs)
    instance = ggwave.init()

    # Log resolved device info
    in_name = p.get_device_info_by_index(
        input_device_index if input_device_index is not None else p.get_default_input_device_info()['index']
    ).get('name')
    out_name = p.get_device_info_by_index(
        output_device_index if output_device_index is not None else p.get_default_output_device_info()['index']
    ).get('name')
    logger.info(f"Input  device: {input_device_index or 'default'} ({in_name})")
    logger.info(f"Output device: {output_device_index or 'default'} ({out_name})")
    logger.info(f"Protocol: {protocol_id} | Volume: {volume}")
    
    while True:
        msg = ""    # Initialise the incoming message variable
        
        try:
            data = stream_input.read(1024, exception_on_overflow=False)
            res = ggwave.decode(instance, data)
            if (not res is None):
                try:
                    msg = res.decode("utf-8")
                    logger.info(f"[RECV_RAW] Bytes: {len(res)} | Raw: {truncate_for_log(msg)}")
                    
                    # Process the input and get response
                    response_dict = process_input(msg)
                    response = json.dumps(response_dict)
                    
                    msg_id = response_dict.get("id", "[no-id]")
                    status = response_dict.get("st", "?")
                    
                    if status == "S":
                        logger.info(f"[RECV_OK] ID: {msg_id} | Processed successfully")
                    else:
                        logger.warning(f"[RECV_FAIL] ID: {msg_id} | Processing error: {response_dict.get('ct', '')}")
                    
                    # Transmit response via ggwave
                    waveform = ggwave.encode(response, protocolId=protocol_id, volume=volume)

                    logger.info(f"[SEND_START] ID: {msg_id} | Content: {truncate_for_log(response)}")
                    stream_output.write(waveform, len(waveform)//4)
                    logger.info(f"[SEND_OK] ID: {msg_id} | Transmission complete")
                    
                except Exception as inner_e:
                    logger.error(f"[RECV_FAIL] Error processing message: {str(inner_e)}")
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            log_session_end("KeyboardInterrupt")
            
            ggwave.free(instance)

            stream_input.stop_stream()
            stream_output.stop_stream()

            stream_input.close()
            stream_output.close()

            p.terminate()
            break
        except Exception as e:
            # Send error back to frontend
            logger.error(f"[ERROR] Exception: {str(e)}")
            
            response_dict = {
                "id": "",
                "st": "E",
                "ct": str(e)
            }
            response = json.dumps(response_dict)
            
            try:
                waveform = ggwave.encode(response, protocolId=protocol_id, volume=volume)
                logger.info(f"[SEND_START] Error response | Content: {truncate_for_log(response)}")
                stream_output.write(waveform, len(waveform)//4)
                logger.info(f"[SEND_OK] Error response transmitted")
            except Exception as send_e:
                logger.error(f"[SEND_FAIL] Failed to send error response: {str(send_e)}")
    
    log_session_end("Normal exit")
    sys.exit(0)


if __name__ == "__main__":
    main()