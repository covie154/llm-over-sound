"""
Shared configuration constants and logging setup for the ggwave backend.
"""

import logging
import os

# ==================== Logging Configuration ====================
LOG_ENABLED = True
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend_log.txt")
LOG_MAX_CONTENT_LENGTH = 500  # Truncate long messages in log

# ==================== Compression Configuration ====================
COMPRESSION_THRESHOLD = 100  # Only compress messages longer than this (in characters)

# ==================== Chunking Configuration ====================
GGWAVE_PAYLOAD_LIMIT = 140    # Max bytes per ggwave transmission (kMaxLengthVariable)
CHUNK_DATA_SIZE = 70           # Max base64 content chars per chunk
INTER_CHUNK_DELAY = 0.5        # Seconds between chunk transmissions
CHUNK_REASSEMBLY_TIMEOUT = 30  # Seconds before requesting retransmission


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console output."""
    logger = logging.getLogger("ggwave_backend")

    if not LOG_ENABLED:
        logging.disable(logging.CRITICAL)
        return logger

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Module-level logger instance shared across the package
logger = setup_logging()


def truncate_for_log(text: str) -> str:
    """Truncate long text for logging."""
    text = text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
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
