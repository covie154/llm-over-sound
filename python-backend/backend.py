#!/usr/bin/env python3
#%%
"""
Minimodem Backend Server — entrypoint.

Listens for minimodem audio messages from the AHK frontend, processes them
through the report-formatting pipeline, and transmits responses back.
"""

import sys
import json
import argparse
import time

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
    MinimodemTransport,
    TestPipeline,
)
from lib.config import INTER_CHUNK_DELAY


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Minimodem backend server for AHK frontend.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend.py
  python backend.py -b 1200
  python backend.py -b 1200 --alsa-dev hw:1
  python backend.py -l
        """,
    )

    parser.add_argument(
        "-b", "--baud-rate",
        type=int, default=1200,
        help="Minimodem baud rate (default: 1200)",
    )
    parser.add_argument(
        "--alsa-dev",
        type=str, default=None,
        help="ALSA device name for minimodem (e.g., hw:1). Default: system default.",
    )
    parser.add_argument(
        "-v", "--volume",
        type=int, default=50,
        help="Transmission volume level 0-100 (default: 50, reserved for future use)",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available ALSA audio devices and exit",
    )

    return parser.parse_args()


def main():
    """Main loop — listen for minimodem input, process, and transmit response."""

    args = parse_args()

    # List devices if requested
    if args.list:
        list_devices()
        return

    log_session_start()

    # Select the pipeline implementation
    # Swap TestPipeline for LLMPipeline when the LLM stages are ready.
    pipeline = TestPipeline()

    # Start minimodem transport
    transport = MinimodemTransport(baud_rate=args.baud_rate, alsa_dev=args.alsa_dev)
    transport.start()

    logger.info(f"Baud rate: {args.baud_rate} | ALSA device: {args.alsa_dev or 'default'} | Volume: {args.volume}")

    try:
        while True:
            try:
                received = transport.receive(timeout=0.1)

                if received is not None:
                    try:
                        logger.info(f"[RECV_RAW] Bytes: {len(received)} | Raw: {truncate_for_log(received)}")

                        # Parse JSON
                        try:
                            chunk_dict = json.loads(received)
                        except json.JSONDecodeError as je:
                            logger.error(f"[RECV_FAIL] Invalid JSON: {je} | Raw: {truncate_for_log(received)}")
                            continue

                        # Handle retransmission request from frontend
                        if chunk_dict.get("fn") == "retx":
                            handle_retransmission_request(chunk_dict, transport)
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
                        send_chunks(chunks, transport, msg_id)

                    except Exception as inner_e:
                        logger.error(f"[RECV_FAIL] Error processing message: {str(inner_e)}")

                # Periodically check for chunk reassembly timeouts
                retx_requests = check_chunk_timeouts()
                for retx in retx_requests:
                    retx_json = json.dumps(retx, separators=(",", ":"))
                    try:
                        transport.send(retx_json)
                        logger.info(f"[RETX_SEND] Requesting retransmission: {retx_json}")
                        time.sleep(INTER_CHUNK_DELAY)
                    except Exception as retx_e:
                        logger.error(f"[RETX_FAIL] Failed to send retx request: {retx_e}")

            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"[ERROR] Exception: {str(e)}")

                # Try to send error response back to frontend
                error_dict = {"id": "", "st": "E", "ct": str(e)}
                try:
                    error_chunks = chunk_message(error_dict)
                    send_chunks(error_chunks, transport)
                except Exception as send_e:
                    logger.error(f"[SEND_FAIL] Failed to send error response: {str(send_e)}")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        transport.stop()
        log_session_end("Normal exit")

    sys.exit(0)


if __name__ == "__main__":
    main()
