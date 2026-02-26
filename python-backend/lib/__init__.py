"""
lib — shared modules for the ggwave radiology backend.
"""

from .config import logger, truncate_for_log, log_session_start, log_session_end
from .compression import lznt1_compress, lznt1_decompress
from .chunking import (
    chunk_message,
    handle_received_chunk,
    check_chunk_timeouts,
    send_chunks,
    handle_retransmission_request,
)
from .audio import list_devices
from .pipeline import ReportPipeline, TestPipeline, LLMPipeline

__all__ = [
    # config
    "logger",
    "truncate_for_log",
    "log_session_start",
    "log_session_end",
    # compression
    "lznt1_compress",
    "lznt1_decompress",
    # chunking
    "chunk_message",
    "handle_received_chunk",
    "check_chunk_timeouts",
    "send_chunks",
    "handle_retransmission_request",
    # audio
    "list_devices",
    # pipeline
    "ReportPipeline",
    "TestPipeline",
    "LLMPipeline",
]
