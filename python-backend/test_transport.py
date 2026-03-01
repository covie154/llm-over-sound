#!/usr/bin/env python3
"""
Loopback test for MinimodemTransport.

Verifies that the transport layer can start TX/RX subprocesses, send data,
and (with an audio loopback) receive it back. Designed to run on the Pi.

Usage:
    python test_transport.py
    python test_transport.py --baud-rate 300
    python test_transport.py --alsa-dev hw:1
"""

import sys
import time
import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="Loopback test for MinimodemTransport.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    return parser.parse_args()


def report(test_name, status, detail=""):
    """Print a test result line."""
    tag = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    suffix = f" — {detail}" if detail else ""
    print(f"  [{tag}] {test_name}{suffix}")


def main():
    args = parse_args()

    # ------------------------------------------------------------------
    # Import transport (may fail if minimodem is not installed)
    # ------------------------------------------------------------------
    try:
        from lib.transport import MinimodemTransport
    except RuntimeError as e:
        print(f"ERROR: {e}")
        print("Cannot run tests without minimodem installed.")
        sys.exit(1)

    print(f"=== MinimodemTransport loopback test (baud={args.baud_rate}) ===\n")

    results = []  # list of (name, status)
    transport = None

    try:
        transport = MinimodemTransport(
            baud_rate=args.baud_rate,
            alsa_dev=args.alsa_dev,
        )
        transport.start()

        # Give RX subprocess time to initialise
        time.sleep(0.5)

        # --------------------------------------------------------------
        # Test 1 — Subprocess health
        # --------------------------------------------------------------
        test_name = "Test 1: Subprocess health"
        rx_alive = transport.rx_process and transport.rx_process.poll() is None
        tx_alive = transport.tx_process and transport.tx_process.poll() is None
        if rx_alive and tx_alive:
            report(test_name, "PASS")
            results.append((test_name, "PASS"))
        else:
            detail = []
            if not rx_alive:
                detail.append("RX not running")
            if not tx_alive:
                detail.append("TX not running")
            report(test_name, "FAIL", "; ".join(detail))
            results.append((test_name, "FAIL"))

        # --------------------------------------------------------------
        # Test 2 — Send without crash
        # --------------------------------------------------------------
        test_name = "Test 2: Send without crash"
        test_msg = '{"id":"TEST","fn":"ping","ct":"hello world"}'
        try:
            transport.send(test_msg)
            report(test_name, "PASS")
            results.append((test_name, "PASS"))
        except Exception as e:
            report(test_name, "FAIL", str(e))
            results.append((test_name, "FAIL"))

        # --------------------------------------------------------------
        # Test 3 — Loopback receive
        # --------------------------------------------------------------
        test_name = "Test 3: Loopback receive"
        loopback_works = False
        received = transport.receive(timeout=10)
        if received is None:
            report(test_name, "SKIP", "No data received — is audio loopback connected?")
            results.append((test_name, "SKIP"))
        elif received == test_msg:
            report(test_name, "PASS")
            results.append((test_name, "PASS"))
            loopback_works = True
        else:
            report(test_name, "FAIL", f"Expected: {test_msg!r}  Got: {received!r}")
            results.append((test_name, "FAIL"))
            loopback_works = True  # loopback exists but data differs

        # --------------------------------------------------------------
        # Test 4 — Multiple messages (only if loopback works)
        # --------------------------------------------------------------
        test_name = "Test 4: Multiple messages in order"
        if not loopback_works:
            report(test_name, "SKIP", "Skipped — loopback not available")
            results.append((test_name, "SKIP"))
        else:
            messages = [
                '{"id":"M1","fn":"ping","ct":"first"}',
                '{"id":"M2","fn":"ping","ct":"second"}',
                '{"id":"M3","fn":"ping","ct":"third"}',
            ]

            # Drain any leftover data in the queue (bounded to prevent infinite loop)
            for _ in range(50):
                if transport.receive(timeout=0.2) is None:
                    break

            for msg in messages:
                transport.send(msg)
                time.sleep(1)

            received_msgs = []
            for _ in range(len(messages)):
                r = transport.receive(timeout=10)
                if r is not None:
                    received_msgs.append(r)

            if received_msgs == messages:
                report(test_name, "PASS")
                results.append((test_name, "PASS"))
            else:
                report(test_name, "FAIL",
                       f"Expected {len(messages)} msgs, got {len(received_msgs)}. "
                       f"Received: {received_msgs!r}")
                results.append((test_name, "FAIL"))

    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        raise
    finally:
        if transport is not None:
            transport.stop()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    total = len(results)
    passed = sum(1 for _, s in results if s == "PASS")
    failed = sum(1 for _, s in results if s == "FAIL")
    skipped = sum(1 for _, s in results if s == "SKIP")
    print(f"Summary: {passed}/{total} passed, {failed} failed, {skipped} skipped")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
