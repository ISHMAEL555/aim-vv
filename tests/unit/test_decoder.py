"""Unit tests for src/decoder.c. HLR tags: HLR-DEC-01..06."""
import json
import pathlib

import pytest

import aim_ctypes

VECTORS = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / "vectors" / "decoder_vectors.json").read_text()
)


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_decoder_vectors(lib, vector):
    """HLR-DEC-01..06: structural decode must match the Python reference
    encoder for every vector, including the ICD worked example."""
    out = aim_ctypes.decode(lib, vector["word"])

    assert bool(out.valid) == vector["expect_valid"], vector["note"]

    if vector["expect_parity_ok"] is not None:
        assert bool(out.parity_ok) == vector["expect_parity_ok"], vector["note"]

    if vector["label"] is not None:
        assert out.label == vector["label"]
    if vector["sdi"] is not None:
        assert out.sdi == vector["sdi"]
    if vector["ssm"] is not None:
        assert out.ssm == vector["ssm"]
    if vector["altitude_ft"] is not None:
        assert out.altitude_ft == vector["altitude_ft"]


def test_icd_worked_example_literal_hex(lib):
    """HLR-DEC-01/03/04/05: the literal hex word from docs/icd/ICD.md
    Section 2 must decode to the documented fields. This is the Phase 2
    done-criterion from the project plan -- keep this test even if the
    generic vector above is ever removed."""
    out = aim_ctypes.decode(lib, 0x309C4183)
    assert bool(out.valid) is True
    assert bool(out.parity_ok) is True
    assert out.label == aim_ctypes.LABEL_203
    assert out.sdi == 1
    assert out.ssm == aim_ctypes.AIM_SSM_NORMAL_OPERATION
    assert out.altitude_ft == 10000


@pytest.mark.parametrize("ssm", [0, 1, 2, 3])
def test_ssm_values_independent_of_validity(lib, ssm):
    """HLR-DEC-06: valid depends only on label+parity, never on SSM."""
    word = aim_ctypes.encode_word(aim_ctypes.LABEL_203, 1, ssm, 10000)
    out = aim_ctypes.decode(lib, word)
    assert bool(out.valid) is True
    assert out.ssm == ssm


def test_sign_extension_most_negative(lib):
    """HLR-DEC-03: 18-bit field's most negative representable value sign-extends correctly."""
    most_negative = -(1 << 17)  # -131072, outside the operating range but within the 18-bit field
    word = aim_ctypes.encode_word(aim_ctypes.LABEL_203, 1, 3, most_negative)
    out = aim_ctypes.decode(lib, word)
    assert out.altitude_ft == most_negative


def test_every_label_other_than_203_is_invalid(lib):
    """HLR-DEC-01: spot-check several wrong labels, not just one bit-flip."""
    for bad_label in (0x00, 0x7F, 0x82, 0x84, 0xFF):
        word = aim_ctypes.encode_word(bad_label, 1, 3, 10000)
        out = aim_ctypes.decode(lib, word)
        assert bool(out.valid) is False, hex(bad_label)
