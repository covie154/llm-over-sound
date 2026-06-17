#!/usr/bin/env python3
#%%
"""
minimodem Backend Server — entrypoint.

Listens for minimodem FSK audio messages from the AHK frontend, processes them
through the report-formatting pipeline, and transmits responses back over the
same FSK audio link.

Phase 7: transport swapped from the old ggwave/PyAudio stack to the minimodem
ctypes binding (lib/minimodem.py -> libminimodem_simple.so). Messages are single
newline-framed JSON frames (ci=0, cc=1) carrying a CRC32 of ``ct``; a CRC
mismatch triggers a full-message retransmit and never surfaces a partial report.
The 5-stage LLM pipeline is UNCHANGED.

NOTE (breaking change — Runtime State Inventory A7): the old protocol-id flag
(``-p``) is REMOVED and replaced by the baud flag (default 1200). Any Pi service
unit (systemd/cron/launch script) invoking ``backend.py -p N`` MUST be updated
to the baud flag or it will fail to start. This cannot be verified from the
repo — the operator must update the Pi's service configuration.
"""

import os
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
    minimodem,
    TestPipeline,
    LLMPipeline,
)

# Sleep between empty receive() polls. minimodem.receive() is non-blocking
# (returns None when no line is queued); without a small sleep the loop would
# busy-spin and peg the Pi CPU. ~10 ms mirrors the AHK 10 ms ProcessAudio cadence.
POLL_SLEEP = 0.01


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="minimodem backend server for AHK frontend.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend.py
  python backend.py -i 5 -o 3
  python backend.py -i 5 -o 3 -v 80 --baud 2400
  python backend.py -l

NOTE: the protocol-id flag was removed in Phase 7. Use --baud (both ends MUST match).
        """,
    )

    parser.add_argument(
        "-i", "--input-device",
        type=int, default=None,
        help="Input (capture) device index (default: system default)",
    )
    parser.add_argument(
        "-o", "--output-device",
        type=int, default=None,
        help="Output (playback) device index (default: system default)",
    )
    parser.add_argument(
        "-v", "--volume",
        type=int, default=50,
        help="Transmission volume level 0-100 (default: 50)",
    )
    parser.add_argument(
        "--baud",
        type=int, default=1200,
        help="minimodem baud rate; MUST match the frontend (default: 1200)",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available audio devices and exit",
    )

    return parser.parse_args()


def main():
    """Main loop — listen for minimodem input, process, and transmit response."""

    args = parse_args()

    input_device_index = args.input_device
    output_device_index = args.output_device
    volume = args.volume
    baud = args.baud

    # A7: surface the breaking protocol-id flag removal at startup.
    logger.info(
        "[CONFIG] The -p protocol-id flag was removed in Phase 7; transport is "
        "minimodem FSK. Any Pi service unit (systemd/cron) invoking backend.py "
        "with -p MUST be updated to --baud."
    )

    # minimodem device indices: -1 means "system default".
    playback_id = output_device_index if output_device_index is not None else -1
    capture_id = input_device_index if input_device_index is not None else -1

    # Initialize the minimodem transport (loads libminimodem_simple.so).
    init_result = minimodem.init(playback_id, capture_id, baud)
    if init_result < 0:
        logger.error(f"[INIT_FAIL] minimodem init failed: {minimodem.get_error()}")
        sys.exit(1)

    # List devices if requested (after init so the backend has enumerated them).
    if args.list:
        list_devices()
        minimodem.cleanup()
        return

    log_session_start()

    # Select the pipeline implementation via PIPELINE_MODE env var (UNCHANGED).
    pipeline_mode = os.environ.get("PIPELINE_MODE", "test")
    if pipeline_mode == "llm":
        pipeline = LLMPipeline()
        logger.info(f"Pipeline: LLMPipeline (mode={pipeline_mode})")
    else:
        pipeline = TestPipeline()
        logger.info(f"Pipeline: TestPipeline (mode={pipeline_mode})")

    # Log resolved device info.
    in_name = minimodem.get_capture_device_name(capture_id) if capture_id >= 0 else "default"
    out_name = minimodem.get_playback_device_name(playback_id) if playback_id >= 0 else "default"
    logger.info(f"Input  device: {input_device_index if input_device_index is not None else 'default'} ({in_name})")
    logger.info(f"Output device: {output_device_index if output_device_index is not None else 'default'} ({out_name})")
    logger.info(f"Baud: {baud} | Volume: {volume}")

    while True:
        try:
            # Housekeeping poll (near no-op; the wrapper RX thread does the demod).
            minimodem.process()

            # Drain ONE received newline-framed JSON line, if any.
            msg = minimodem.receive()

            if msg is None:
                # No message queued — sleep to avoid busy-spin, then check timeouts.
                time.sleep(POLL_SLEEP)
                for retx in check_chunk_timeouts():
                    retx_json = json.dumps(retx, separators=(",", ":")) + "\n"
                    try:
                        if minimodem.send(retx_json, volume) >= 0:
                            while minimodem.is_transmitting():
                                time.sleep(0.05)
                            logger.info(f"[RETX_SEND] Requesting retransmission: {retx_json.strip()}")
                        else:
                            logger.error(f"[RETX_FAIL] Send failed: {minimodem.get_error()}")
                    except Exception as retx_e:
                        logger.error(f"[RETX_FAIL] Failed to send retx request: {retx_e}")
                continue

            logger.info(f"[RECV_RAW] Bytes: {len(msg)} | Raw: {truncate_for_log(msg)}")

            try:
                # Parse JSON.
                try:
                    chunk_dict = json.loads(msg)
                except json.JSONDecodeError as je:
                    logger.error(f"[RECV_FAIL] Invalid JSON: {je} | Raw: {truncate_for_log(msg)}")
                    continue

                # Handle retransmission request from frontend.
                if chunk_dict.get("fn") == "retx":
                    handle_retransmission_request(chunk_dict, volume)
                    continue

                # Handle frame (CRC-verified single frame; None if mismatch/incomplete).
                complete_msg = handle_received_chunk(chunk_dict)
                if complete_msg is None:
                    continue

                # Process through the pipeline (UNCHANGED).
                msg_id = complete_msg.get("id", "[no-id]")
                response_dict = pipeline.process(complete_msg)

                status = response_dict.get("st", "?")
                if status == "S":
                    logger.info(f"[PROCESS_OK] ID: {msg_id} | Processed successfully")
                else:
                    logger.warning(f"[PROCESS_FAIL] ID: {msg_id} | Error: {response_dict.get('ct', '')}")

                # Build single CRC frame and send.
                chunks = chunk_message(response_dict)
                send_chunks(chunks, volume, msg_id)

            except Exception as inner_e:
                logger.error(f"[RECV_FAIL] Error processing message: {str(inner_e)}")

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            log_session_end("KeyboardInterrupt")
            minimodem.cleanup()
            break
        except Exception as e:
            logger.error(f"[ERROR] Exception: {str(e)}")

            # Try to send error response back to frontend.
            error_dict = {"id": "", "st": "E", "ct": str(e)}
            try:
                error_chunks = chunk_message(error_dict)
                send_chunks(error_chunks, volume)
            except Exception as send_e:
                logger.error(f"[SEND_FAIL] Failed to send error response: {str(send_e)}")

    log_session_end("Normal exit")
    sys.exit(0)


if __name__ == "__main__":
    main()
