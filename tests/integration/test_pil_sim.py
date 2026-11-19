"""PIL harness self-tests using the host-simulated target (no hardware).

These validate the harness, the UART protocol and the status-line format.
They do NOT validate the AVR build -- that needs the board (scripts/pil.py --port).
"""
import importlib.util
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "pil", pathlib.Path(__file__).resolve().parents[2] / "scripts" / "pil.py")
pil = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pil)

SCENARIOS = pil.scenarios()


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_sim_target_matches_host_lockstep(lib, framer_lib, name):
    """SYS-9, SYS-10: every cycle of every scripted scenario, driven over the
    UART framing (including injected garbage and corrupt frames), produces the
    same status as calling aim_step directly on the host."""
    assert pil.run(pil.SimTarget(), name, SCENARIOS[name]) == []


def test_harness_detects_a_broken_target(lib, framer_lib):
    """SYS-9: the comparison must fail when the target misbehaves (negative
    control, so a passing PIL run is meaningful)."""
    class Broken(pil.SimTarget):
        def _handle(self, f):
            if f.type == pil.ac.FRAME_SELECTED_ALT:
                return  # target ignores the selected altitude
            super()._handle(f)

    assert pil.run(Broken(), "x", SCENARIOS["climb_capture_deviation"]) != []
