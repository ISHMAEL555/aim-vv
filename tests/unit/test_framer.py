"""Unit tests for target/aim_target/framer.c. HLR tags: HLR-FRM-01..04."""
import ctypes
import random

import pytest

import aim_ctypes as ac


def feed(lib, fr, data):
    """Push bytes; return the list of (type, payload) frames delivered."""
    got = []
    for b in data:
        out = ac.Frame()
        if lib.aim_framer_push(ctypes.byref(fr), b, ctypes.byref(out)):
            got.append((out.type, out.payload))
    return got


@pytest.fixture
def fr(framer_lib):
    f = ac.Framer()
    framer_lib.aim_framer_init(ctypes.byref(f))
    return f


@pytest.mark.parametrize("ftype", [1, 2, 3, 4, 5])
def test_valid_frame_delivered_with_le_payload(framer_lib, fr, ftype):
    """HLR-FRM-01"""
    assert feed(framer_lib, fr, ac.make_frame(ftype, 0x309C4183)) == [(ftype, 0x309C4183)]


def test_icd_checksum_rule_and_reserved_no_target_value(framer_lib, fr):
    """HLR-FRM-01: reserved 0x7FFFFFFF payload and the literal checksum rule."""
    frame = ac.make_frame(ac.FRAME_SELECTED_ALT, ac.NO_TARGET)
    assert (frame[1] + sum(frame[2:6]) + frame[6]) % 256 == 0
    assert feed(framer_lib, fr, frame) == [(2, 0x7FFFFFFF)]


def test_bad_checksum_rejected_and_counted(framer_lib, fr):
    """HLR-FRM-02"""
    frame = bytearray(ac.make_frame(1, 1234))
    frame[6] ^= 0x01
    assert feed(framer_lib, fr, frame) == []
    assert fr.rejected == 1


@pytest.mark.parametrize("ftype", [0, 6, 0xFF])
def test_unknown_type_rejected(framer_lib, fr, ftype):
    """HLR-FRM-02: checksum-valid frame with an unknown TYPE is still dropped."""
    assert feed(framer_lib, fr, ac.make_frame(ftype, 7)) == []
    assert fr.rejected == 1


def test_rejected_counter_saturates(framer_lib, fr):
    """HLR-FRM-02"""
    fr.rejected = 0xFFFE
    bad = bytearray(ac.make_frame(1, 1))
    bad[6] ^= 0x01
    feed(framer_lib, fr, bad)
    feed(framer_lib, fr, bad)
    feed(framer_lib, fr, bad)
    assert fr.rejected == 0xFFFF


def test_leading_garbage_is_skipped(framer_lib, fr):
    """HLR-FRM-03"""
    assert feed(framer_lib, fr, b"\x00\x13\x7f" + ac.make_frame(3, 99)) == [(3, 99)]


def test_resync_when_false_sync_swallows_a_real_frame(framer_lib, fr):
    """HLR-FRM-03: a stray 0xAA makes the parser start a 7-byte candidate that
    overlaps the next real frame; the real frame must still be delivered."""
    real = ac.make_frame(1, 0xDEADBEEF)
    assert feed(framer_lib, fr, b"\xaa" + real) == [(1, 0xDEADBEEF)]
    assert fr.rejected == 1


def test_truncated_frame_then_valid_frame(framer_lib, fr):
    """HLR-FRM-03"""
    cut = ac.make_frame(2, 5000)[:4]
    assert feed(framer_lib, fr, cut + ac.make_frame(2, 6000)) == [(2, 6000)]


def test_back_to_back_frames(framer_lib, fr):
    """HLR-FRM-04"""
    stream = b"".join(ac.make_frame(t, 100 + t) for t in (1, 3, 2, 5, 4))
    assert feed(framer_lib, fr, stream) == [(1, 101), (3, 103), (2, 102), (5, 105), (4, 104)]


def test_random_noise_never_crashes_and_valid_frames_always_found(framer_lib, fr):
    """HLR-FRM-03 / SYS-10: fuzz. A valid frame preceded by up to 20 random
    bytes that contain no 0xAA is always delivered; arbitrary noise never
    wedges the parser."""
    rng = random.Random(1234)
    for _ in range(300):
        noise = bytes(b for b in (rng.randrange(256) for _ in range(rng.randrange(20))) if b != 0xAA)
        payload = rng.getrandbits(32)
        assert feed(framer_lib, fr, noise + ac.make_frame(1, payload))[-1] == (1, payload)
    for _ in range(2000):  # arbitrary noise, including 0xAA, must not wedge it
        feed(framer_lib, fr, bytes([rng.randrange(256)]))
    assert feed(framer_lib, fr, b"\x00" * 7 + ac.make_frame(2, 42))[-1] == (2, 42)
