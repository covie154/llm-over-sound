#!/usr/bin/env python3
#%%
"""
Dummy Backend Server for AHK ggwave 
"""

import sys
import json
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


def main():
    """Main loop - Listen for input from ggwave, then process and transmit response."""
    
    log_session_start()

    input_device_index = 5  # Change this to your input device index
    stream_input = p.open(format=pyaudio.paFloat32, channels=1, rate=48000, input=True, input_device_index=input_device_index, frames_per_buffer=1024)
    stream_output = p.open(format=pyaudio.paFloat32, channels=1, rate=48000, output=True, frames_per_buffer=4096)
    instance = ggwave.init()
    
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')

    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            print("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get('name'))
    
    device_name = p.get_device_info_by_index(input_device_index).get('name')
    logger.info(f"Initialized pyaudio input stream - Device: {input_device_index} ({device_name})")
    
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
                    waveform = ggwave.encode(response, protocolId = 1, volume = 50)

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
                waveform = ggwave.encode(response, protocolId = 1, volume = 50)
                logger.info(f"[SEND_START] Error response | Content: {truncate_for_log(response)}")
                stream_output.write(waveform, len(waveform)//4)
                logger.info(f"[SEND_OK] Error response transmitted")
            except Exception as send_e:
                logger.error(f"[SEND_FAIL] Failed to send error response: {str(send_e)}")
    
    log_session_end("Normal exit")
    sys.exit(0)


if __name__ == "__main__":
    main()