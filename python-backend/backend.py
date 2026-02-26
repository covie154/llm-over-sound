#!/usr/bin/env python3
#%%
"""
ggwave Backend Server — entrypoint.

Listens for ggwave audio messages from the AHK frontend, processes them
through the report-formatting pipeline, and transmits responses back.
"""

import sys
import json
import argparse
import time

import ggwave
import pyaudio

from lib import (
    logger,
    truncate_for_log,
    log_session_start,
    log_session_end,
    chunk_message,
    handle_received_chunk,
    check_chunk_timeouts,
    send_chunks,
    handle_retransmission_request,
    list_devices,
    TestPipeline,
)
from lib.config import INTER_CHUNK_DELAY


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ggwave backend server for AHK frontend.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend.py
  python backend.py -i 5 -o 3
  python backend.py -i 5 -o 3 -v 80 -p 2
  python backend.py -l
        """,
    )

    parser.add_argument(
        "-i", "--input-device",
        type=int, default=None,
        help="Input device index (default: system default)",
    )
    parser.add_argument(
        "-o", "--output-device",
        type=int, default=None,
        help="Output device index (default: system default)",
    )
    parser.add_argument(
        "-v", "--volume",
        type=int, default=50,
        help="Transmission volume level 0-100 (default: 50)",
    )
    parser.add_argument(
        "-p", "--protocol",
        type=int, default=1,
        help="ggwave protocol ID (default: 1 = Audible Fast)",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available audio devices and exit",
    )

    return parser.parse_args()


def main():
    """Main loop — listen for ggwave input, process, and transmit response."""

    args = parse_args()
    p = pyaudio.PyAudio()

    # List devices if requested
    if args.list:
        list_devices(p)
        p.terminate()
        return

    log_session_start()

    # Select the pipeline implementation
    # Swap TestPipeline for LLMPipeline when the LLM stages are ready.
    pipeline = TestPipeline()

    input_device_index = args.input_device
    output_device_index = args.output_device
    volume = args.volume
    protocol_id = args.protocol

    # Build stream kwargs — None means "use system default"
    input_kwargs = dict(
        format=pyaudio.paFloat32, channels=1, rate=48000,
        input=True, frames_per_buffer=1024,
    )
    if input_device_index is not None:
        input_kwargs["input_device_index"] = input_device_index

    output_kwargs = dict(
        format=pyaudio.paFloat32, channels=1, rate=48000,
        output=True, frames_per_buffer=4096,
    )
    if output_device_index is not None:
        output_kwargs["output_device_index"] = output_device_index

    stream_input = p.open(**input_kwargs)
    stream_output = p.open(**output_kwargs)
    instance = ggwave.init()

    # Log resolved device info
    in_name = p.get_device_info_by_index(
        input_device_index if input_device_index is not None
        else p.get_default_input_device_info()["index"]
    ).get("name")
    out_name = p.get_device_info_by_index(
        output_device_index if output_device_index is not None
        else p.get_default_output_device_info()["index"]
    ).get("name")
    logger.info(f"Input  device: {input_device_index or 'default'} ({in_name})")
    logger.info(f"Output device: {output_device_index or 'default'} ({out_name})")
    logger.info(f"Protocol: {protocol_id} | Volume: {volume}")

    while True:
        try:
            data = stream_input.read(1024, exception_on_overflow=False)
            res = ggwave.decode(instance, data)

            if res is not None:
                try:
                    msg = res.decode("utf-8")
                    logger.info(f"[RECV_RAW] Bytes: {len(res)} | Raw: {truncate_for_log(msg)}")

                    # Parse JSON
                    try:
                        chunk_dict = json.loads(msg)
                    except json.JSONDecodeError as je:
                        logger.error(f"[RECV_FAIL] Invalid JSON: {je} | Raw: {truncate_for_log(msg)}")
                        continue

                    # Handle retransmission request from frontend
                    if chunk_dict.get("fn") == "retx":
                        handle_retransmission_request(chunk_dict, stream_output, protocol_id, volume)
                        continue

                    # Handle chunk (may return None if waiting for more chunks)
                    complete_msg = handle_received_chunk(chunk_dict)
                    if complete_msg is None:
                        continue

                    # Process through the pipeline
                    msg_id = complete_msg.get("id", "[no-id]")
                    response_dict = pipeline.process(complete_msg)

                    status = response_dict.get("st", "?")
                    if status == "S":
                        logger.info(f"[PROCESS_OK] ID: {msg_id} | Processed successfully")
                    else:
                        logger.warning(f"[PROCESS_FAIL] ID: {msg_id} | Error: {response_dict.get('ct', '')}")

                    # Chunk and send response
                    chunks = chunk_message(response_dict)
                    send_chunks(chunks, stream_output, protocol_id, volume, msg_id)

                except Exception as inner_e:
                    logger.error(f"[RECV_FAIL] Error processing message: {str(inner_e)}")

            # Periodically check for chunk reassembly timeouts
            retx_requests = check_chunk_timeouts()
            for retx in retx_requests:
                retx_json = json.dumps(retx, separators=(",", ":"))
                try:
                    waveform = ggwave.encode(retx_json, protocolId=protocol_id, volume=volume)
                    stream_output.write(waveform, len(waveform) // 4)
                    logger.info(f"[RETX_SEND] Requesting retransmission: {retx_json}")
                    time.sleep(INTER_CHUNK_DELAY)
                except Exception as retx_e:
                    logger.error(f"[RETX_FAIL] Failed to send retx request: {retx_e}")

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
            logger.error(f"[ERROR] Exception: {str(e)}")

            # Try to send error response back to frontend
            error_dict = {"id": "", "st": "E", "ct": str(e)}
            try:
                error_chunks = chunk_message(error_dict)
                send_chunks(error_chunks, stream_output, protocol_id, volume)
            except Exception as send_e:
                logger.error(f"[SEND_FAIL] Failed to send error response: {str(send_e)}")

    log_session_end("Normal exit")
    sys.exit(0)


if __name__ == "__main__":
    main()