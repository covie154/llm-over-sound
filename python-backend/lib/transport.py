"""Minimodem subprocess transport for Raspberry Pi."""

import subprocess
import threading
import queue
import logging
import shutil
from .config import BAUD_RATE

logger = logging.getLogger(__name__)


class MinimodemTransport:
    """Manages minimodem TX/RX subprocesses for audio data transport."""

    def __init__(self, baud_rate=BAUD_RATE, alsa_dev=None):
        self.baud_rate = baud_rate
        self.alsa_dev = alsa_dev
        self.rx_process = None
        self.tx_process = None
        self.rx_thread = None
        self.rx_queue = queue.Queue()
        self._running = False
        self._line_buffer = ""

        if not shutil.which("minimodem"):
            raise RuntimeError("minimodem not found. Install with: apt install minimodem")

    def start(self):
        """Start RX and TX subprocesses."""
        self._running = True

        # RX subprocess: minimodem --rx <baud> --quiet
        rx_cmd = ["minimodem", "--rx", str(self.baud_rate), "--quiet"]
        if self.alsa_dev:
            rx_cmd.extend(["--alsa-dev", self.alsa_dev])
        self.rx_process = subprocess.Popen(
            rx_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        # TX subprocess: minimodem --tx <baud>
        tx_cmd = ["minimodem", "--tx", str(self.baud_rate)]
        if self.alsa_dev:
            tx_cmd.extend(["--alsa-dev", self.alsa_dev])
        self.tx_process = subprocess.Popen(
            tx_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        # background thread to read RX output
        self.rx_thread = threading.Thread(target=self._rx_reader, daemon=True)
        self.rx_thread.start()

        logger.info("MinimodemTransport started (baud=%d)", self.baud_rate)

    def stop(self):
        """Stop subprocesses and reader thread."""
        self._running = False

        if self.tx_process:
            self.tx_process.stdin.close()
            self.tx_process.wait(timeout=5)
            self.tx_process = None

        if self.rx_process:
            self.rx_process.terminate()
            self.rx_process.wait(timeout=5)
            self.rx_process = None

        logger.info("MinimodemTransport stopped")

    def send(self, data: str):
        """Send a string (typically a JSON chunk) over minimodem TX.
        Appends newline delimiter automatically."""
        if not self.tx_process or self.tx_process.poll() is not None:
            raise RuntimeError("TX subprocess not running")
        payload = (data + "\n").encode("utf-8")
        self.tx_process.stdin.write(payload)
        self.tx_process.stdin.flush()

    def receive(self, timeout=0.1):
        """Receive a decoded message (newline-delimited string).
        Returns None if nothing available within timeout."""
        try:
            return self.rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _rx_reader(self):
        """Background thread: read minimodem RX stdout, split on newlines."""
        while self._running and self.rx_process:
            try:
                chunk = self.rx_process.stdout.read(1)
                if not chunk:
                    break
                char = chunk.decode("utf-8", errors="replace")
                if char == "\n":
                    line = self._line_buffer.strip()
                    if line:
                        self.rx_queue.put(line)
                    self._line_buffer = ""
                else:
                    self._line_buffer += char
            except Exception as e:
                logger.error("RX reader error: %s", e)
                break
