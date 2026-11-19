"""ctypes bindings to libaim, shared by unit and integration tests.

Struct field order/types mirror src/aim_types.h exactly. Do not reorder or
retype a field here without making the matching change in aim_types.h --
these are two independent encodings of the same C ABI.
"""
import ctypes
import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_LIB_CANDIDATES = [
    REPO_ROOT / "build" / "libaim.so",
    REPO_ROOT / "build" / "libaim.dylib",
]

AIM_SSM_FAILURE_WARNING = 0
AIM_SSM_NO_COMPUTED_DATA = 1
AIM_SSM_FUNCTIONAL_TEST = 2
AIM_SSM_NORMAL_OPERATION = 3

AIM_ALERT_CRUISE = 0
AIM_ALERT_APPROACHING = 1
AIM_ALERT_CAPTURED = 2
AIM_ALERT_DEVIATION = 3

LABEL_203 = 0o203


class DecodedWord(ctypes.Structure):
    _fields_ = [
        ("valid", ctypes.c_uint8),
        ("parity_ok", ctypes.c_uint8),
        ("label", ctypes.c_uint8),
        ("sdi", ctypes.c_uint8),
        ("ssm", ctypes.c_uint8),
        ("altitude_ft", ctypes.c_int32),
    ]


class MonitorState(ctypes.Structure):
    _fields_ = [
        ("last_good_ms_ch1", ctypes.c_uint32),
        ("last_good_ms_ch2", ctypes.c_uint32),
        ("have_ch1_ever", ctypes.c_uint8),
        ("have_ch2_ever", ctypes.c_uint8),
        ("diverge_since_ms", ctypes.c_uint32),
        ("diverging", ctypes.c_uint8),
        ("converge_since_ms", ctypes.c_uint32),
        ("converging", ctypes.c_uint8),
        ("miscompare_latched", ctypes.c_uint8),
    ]


class MonitorStatus(ctypes.Structure):
    _fields_ = [
        ("ch1_valid", ctypes.c_uint8),
        ("ch2_valid", ctypes.c_uint8),
        ("ch1_stale", ctypes.c_uint8),
        ("ch2_stale", ctypes.c_uint8),
        ("miscompare", ctypes.c_uint8),
        ("altitude_available", ctypes.c_uint8),
        ("reconciled_altitude_ft", ctypes.c_int32),
    ]


class AlerterState(ctypes.Structure):
    _fields_ = [
        ("state", ctypes.c_uint8),
        ("deviation_since_ms", ctypes.c_uint32),
        ("deviating", ctypes.c_uint8),
        ("selected_altitude_ft", ctypes.c_int32),
        ("have_selected_ever", ctypes.c_uint8),
    ]


class AlerterStatus(ctypes.Structure):
    _fields_ = [
        ("state", ctypes.c_uint8),
        ("alert_approaching", ctypes.c_uint8),
        ("alert_deviation", ctypes.c_uint8),
        ("selected_altitude_valid", ctypes.c_uint8),
    ]


class Aim(ctypes.Structure):
    _fields_ = [
        ("monitor", MonitorState),
        ("alerter", AlerterState),
    ]


class Status(ctypes.Structure):
    _fields_ = [
        ("monitor", MonitorStatus),
        ("alerter", AlerterStatus),
        ("altitude_ft", ctypes.c_int32),
        ("altitude_valid", ctypes.c_uint8),
    ]


def find_lib() -> pathlib.Path:
    override = os.environ.get("AIM_LIB")
    if override:
        return pathlib.Path(override)
    for candidate in _LIB_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "libaim shared library not found; build it first with:\n"
        "  cmake -S . -B build && cmake --build build"
    )


def load() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(find_lib()))

    lib.aim_decoder_decode.argtypes = [ctypes.c_uint32, ctypes.POINTER(DecodedWord)]
    lib.aim_decoder_decode.restype = None

    lib.aim_monitor_init.argtypes = [ctypes.POINTER(MonitorState)]
    lib.aim_monitor_init.restype = None
    lib.aim_monitor_update.argtypes = [
        ctypes.POINTER(MonitorState), ctypes.c_uint32,
        ctypes.POINTER(DecodedWord), ctypes.POINTER(DecodedWord),
        ctypes.POINTER(MonitorStatus),
    ]
    lib.aim_monitor_update.restype = None

    lib.aim_alerter_init.argtypes = [ctypes.POINTER(AlerterState)]
    lib.aim_alerter_init.restype = None
    lib.aim_alerter_update.argtypes = [
        ctypes.POINTER(AlerterState), ctypes.c_uint32,
        ctypes.c_int32, ctypes.c_uint8,
        ctypes.c_int32, ctypes.c_uint8,
        ctypes.c_uint8,
        ctypes.POINTER(AlerterStatus),
    ]
    lib.aim_alerter_update.restype = None

    lib.aim_init.argtypes = [ctypes.POINTER(Aim)]
    lib.aim_init.restype = None
    lib.aim_step.argtypes = [
        ctypes.POINTER(Aim), ctypes.c_uint32,
        ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_int32, ctypes.c_uint8,
        ctypes.c_uint8,
        ctypes.POINTER(Status),
    ]
    lib.aim_step.restype = None

    return lib


def decode(lib: ctypes.CDLL, word: int) -> DecodedWord:
    out = DecodedWord()
    lib.aim_decoder_decode(ctypes.c_uint32(word), ctypes.byref(out))
    return out


def encode_word(label: int, sdi: int, ssm: int, alt_ft: int) -> int:
    """Python reference encoder, used to build test words. Mirrors the C
    decoder's field layout (docs/icd/ICD.md Section 2) in reverse."""
    alt_field = alt_ft & 0x3FFFF
    word = 0
    word |= label & 0xFF
    word |= (sdi & 0x3) << 8
    word |= (alt_field & 0x3FFFF) << 10
    word |= (ssm & 0x3) << 28
    ones = bin(word & 0x7FFFFFFF).count("1")
    parity = 0 if ones % 2 == 1 else 1
    word |= (parity & 1) << 31
    return word


# ---- Phase 7 frame parser (target/aim_target/framer.c) --------------------
FRAME_ADC1_WORD, FRAME_SELECTED_ALT, FRAME_ADC2_WORD, FRAME_STEP, FRAME_APPROACH_MODE = 1, 2, 3, 4, 5
NO_TARGET = 0x7FFFFFFF


class Framer(ctypes.Structure):
    _fields_ = [("buf", ctypes.c_uint8 * 7), ("n", ctypes.c_uint8), ("rejected", ctypes.c_uint16)]


class Frame(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint8), ("payload", ctypes.c_uint32)]


def make_frame(ftype: int, payload: int) -> bytes:
    """Python reference frame encoder (ICD Section 3)."""
    p = (payload & 0xFFFFFFFF).to_bytes(4, "little")
    chk = (-(ftype + sum(p))) & 0xFF
    return bytes([0xAA, ftype]) + p + bytes([chk])


def load_framer() -> ctypes.CDLL:
    override = os.environ.get("AIM_FRAMER_LIB")
    path = pathlib.Path(override) if override else REPO_ROOT / "build" / "libaimframer.so"
    lib = ctypes.CDLL(str(path))
    lib.aim_framer_init.argtypes = [ctypes.POINTER(Framer)]
    lib.aim_framer_init.restype = None
    lib.aim_framer_push.argtypes = [ctypes.POINTER(Framer), ctypes.c_uint8, ctypes.POINTER(Frame)]
    lib.aim_framer_push.restype = ctypes.c_uint8
    return lib
