"""
ctypes binding to the minimodem FSK wrapper shared library
(``libminimodem_simple.so`` on the Pi/Linux backend).

This is the minimodem FSK transport binding (replaced the old ggwave Python binding). The wrapper
mirrors ``ggwave_simple.h`` / ``minimodem_simple.h`` exactly so this binding is
symmetric with the AHK frontend's ``DllCall`` model: same 12-function API, with
``protocolId`` replaced by ``baud`` (and ``set_protocol`` -> ``set_baud``).

Security (07-RESEARCH.md Threat Model — ctypes signature mismatch): EXPLICIT
``restype``/``argtypes`` are set on every bound function. A wrong/implicit
signature can corrupt memory, so none are left to ctypes' int-default. ``receive``
is always called with a sized ``ctypes.create_string_buffer`` and only the
returned length is decoded (bounds respected).

Framing: the wrapper's background RX thread accumulates the FSK byte stream and
queues complete newline-delimited messages. ``receive`` drains ONE such line at
a time (the trailing newline is consumed by the wrapper); this binding returns
the decoded JSON line string.
"""

import ctypes
import os

# ---------------------------------------------------------------------------
# Shared library resolution + load
# ---------------------------------------------------------------------------

# Linux artifact names (the Pi target). NOTE: the wrapper's CMakeLists sets
# PREFIX "" so the produced file is `minimodem_simple.so`; the design contract /
# AHK side refer to it as `libminimodem_simple.so`. Search BOTH so the binding
# loads whichever name the build/installer placed on the Pi. On Windows dev
# boxes neither file exists; load() is lazy so importing this module (and its
# siblings) succeeds without the .so present.
_LIB_NAMES = ("libminimodem_simple.so", "minimodem_simple.so")

# Default search: alongside the backend package dir, then this lib/ dir, then
# an absolute fallback via LD_LIBRARY_PATH / system loader (bare name).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))

_lib = None  # populated by load()


def _resolve_lib_path() -> str:
    """Resolve an absolute path to the wrapper .so, with sensible fallbacks."""
    search_dirs = [
        _BACKEND_DIR,
        _LIB_DIR,
        os.path.join(_BACKEND_DIR, "lib"),
        os.path.join(_BACKEND_DIR, "build"),
        os.path.join(_BACKEND_DIR, "..", "minimodem-wrapper", "build"),
    ]
    for d in search_dirs:
        for name in _LIB_NAMES:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                return path
    # Last resort: let the dynamic loader search (LD_LIBRARY_PATH / ldconfig).
    return _LIB_NAMES[0]


def _bind_signatures(lib: ctypes.CDLL) -> None:
    """Set EXPLICIT restype/argtypes on every exported function.

    Security: an implicit/incorrect signature can corrupt memory across the FFI
    boundary, so all 12 exports are pinned here.
    """
    # int minimodem_simple_init(int playback, int capture, int baud)
    lib.minimodem_simple_init.restype = ctypes.c_int
    lib.minimodem_simple_init.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]

    # int minimodem_simple_get_playback_device_count(void)
    lib.minimodem_simple_get_playback_device_count.restype = ctypes.c_int
    lib.minimodem_simple_get_playback_device_count.argtypes = []

    # int minimodem_simple_get_capture_device_count(void)
    lib.minimodem_simple_get_capture_device_count.restype = ctypes.c_int
    lib.minimodem_simple_get_capture_device_count.argtypes = []

    # const char* minimodem_simple_get_playback_device_name(int deviceId)
    lib.minimodem_simple_get_playback_device_name.restype = ctypes.c_char_p
    lib.minimodem_simple_get_playback_device_name.argtypes = [ctypes.c_int]

    # const char* minimodem_simple_get_capture_device_name(int deviceId)
    lib.minimodem_simple_get_capture_device_name.restype = ctypes.c_char_p
    lib.minimodem_simple_get_capture_device_name.argtypes = [ctypes.c_int]

    # int minimodem_simple_send(const char* message, int volume)
    lib.minimodem_simple_send.restype = ctypes.c_int
    lib.minimodem_simple_send.argtypes = [ctypes.c_char_p, ctypes.c_int]

    # int minimodem_simple_is_transmitting(void)
    lib.minimodem_simple_is_transmitting.restype = ctypes.c_int
    lib.minimodem_simple_is_transmitting.argtypes = []

    # int minimodem_simple_process(void)
    lib.minimodem_simple_process.restype = ctypes.c_int
    lib.minimodem_simple_process.argtypes = []

    # int minimodem_simple_receive(char* buffer, int bufferSize)
    lib.minimodem_simple_receive.restype = ctypes.c_int
    lib.minimodem_simple_receive.argtypes = [ctypes.c_char_p, ctypes.c_int]

    # int minimodem_simple_set_baud(int baud)
    lib.minimodem_simple_set_baud.restype = ctypes.c_int
    lib.minimodem_simple_set_baud.argtypes = [ctypes.c_int]

    # void minimodem_simple_cleanup(void)
    lib.minimodem_simple_cleanup.restype = None
    lib.minimodem_simple_cleanup.argtypes = []

    # const char* minimodem_simple_get_error(void)
    lib.minimodem_simple_get_error.restype = ctypes.c_char_p
    lib.minimodem_simple_get_error.argtypes = []


def load(lib_path: str | None = None) -> ctypes.CDLL:
    """Load (once) and return the wrapper CDLL with signatures bound.

    Idempotent: subsequent calls return the already-loaded handle.
    """
    global _lib
    if _lib is not None:
        return _lib
    path = lib_path or _resolve_lib_path()
    lib = ctypes.CDLL(path)
    _bind_signatures(lib)
    _lib = lib
    return _lib


def _require() -> ctypes.CDLL:
    """Return the loaded library, loading on first use."""
    if _lib is None:
        return load()
    return _lib


# ---------------------------------------------------------------------------
# Thin Python helpers over the bound functions
# ---------------------------------------------------------------------------

# Default receive buffer size; mirrors the AHK frontend's 512-byte drain buffer.
RECEIVE_BUFFER_SIZE = 512


def init(playback_device_id: int = -1, capture_device_id: int = -1, baud: int = 1200) -> int:
    """Initialize minimodem with the given device indices and baud.

    -1 selects the system default device. Returns 0 on success, negative on error.
    """
    return _require().minimodem_simple_init(
        int(playback_device_id), int(capture_device_id), int(baud)
    )


def get_playback_device_count() -> int:
    return _require().minimodem_simple_get_playback_device_count()


def get_capture_device_count() -> int:
    return _require().minimodem_simple_get_capture_device_count()


def get_playback_device_name(device_id: int) -> str:
    name = _require().minimodem_simple_get_playback_device_name(int(device_id))
    return name.decode("utf-8", "replace") if name else ""


def get_capture_device_name(device_id: int) -> str:
    name = _require().minimodem_simple_get_capture_device_name(int(device_id))
    return name.decode("utf-8", "replace") if name else ""


def send(message: str, volume: int = 50) -> int:
    """FSK-modulate ``message`` to the playback device. Returns 0 on success."""
    return _require().minimodem_simple_send(message.encode("utf-8"), int(volume))


def is_transmitting() -> bool:
    """True while a transmission is still in flight."""
    return bool(_require().minimodem_simple_is_transmitting())


def process() -> int:
    """Housekeeping poll (near no-op; the wrapper RX thread does the demod)."""
    return _require().minimodem_simple_process()


def receive(buffer_size: int = RECEIVE_BUFFER_SIZE) -> str | None:
    """Drain ONE received newline-delimited message.

    Passes a sized ``create_string_buffer`` and decodes only the returned length
    (bounds respected). Returns the decoded JSON line string, or None if no
    message is queued (length 0) / on error (negative length).
    """
    buf = ctypes.create_string_buffer(buffer_size)
    n = _require().minimodem_simple_receive(buf, buffer_size)
    if n <= 0:
        return None
    # Respect the returned length; never read past it.
    n = min(n, buffer_size)
    return buf.raw[:n].decode("utf-8", "replace")


def set_baud(baud: int) -> int:
    """Set the FSK baud rate (rebuilds the fsk plan). Replaces set_protocol."""
    return _require().minimodem_simple_set_baud(int(baud))


def cleanup() -> None:
    """Release all resources (joins the RX thread, closes streams)."""
    _require().minimodem_simple_cleanup()


def get_error() -> str:
    """Return the last error message from the wrapper."""
    err = _require().minimodem_simple_get_error()
    return err.decode("utf-8", "replace") if err else ""
