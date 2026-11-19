"""Unit tests for src/alerter.c. HLR tags: HLR-ALT-01..10.

Note: the state machine advances at most one state per aim_alerter_update
call (e.g. CRUISE -> APPROACHING -> CAPTURED takes two calls even if the
altitude is already within the capture band on the first call), matching
a real control loop ticking at a fixed rate. reach_captured() below drives
exactly that two-call sequence so CAPTURED/DEVIATION tests start from a
state the implementation actually reaches, not an assumed one.
"""
import ctypes

import pytest

import aim_ctypes as ac

APPROACH = 1000
CAPTURE = 300
DEVIATION_BAND = 300
HYST = 50
PERSIST_MS = 1000


def new_state():
    return ac.AlerterState()


def step(lib, st, now_ms, alt, alt_valid, selected, selected_valid, approach_mode=0):
    out = ac.AlerterStatus()
    lib.aim_alerter_update(
        ctypes.byref(st), ctypes.c_uint32(now_ms),
        ctypes.c_int32(alt), ctypes.c_uint8(int(alt_valid)),
        ctypes.c_int32(selected), ctypes.c_uint8(int(selected_valid)),
        ctypes.c_uint8(int(approach_mode)),
        ctypes.byref(out),
    )
    return out


def reach_captured(lib, st, selected, t0=0):
    """CRUISE -> APPROACHING -> CAPTURED, at zero error, over two calls."""
    step(lib, st, t0, selected, True, selected, True)
    out = step(lib, st, t0 + 1, selected, True, selected, True)
    assert out.state == ac.AIM_ALERT_CAPTURED
    return out


@pytest.fixture
def st(lib):
    s = new_state()
    lib.aim_alerter_init(ctypes.byref(s))
    return s


def test_no_alert_before_any_valid_target(lib, st):
    """HLR-ALT-02"""
    out = step(lib, st, 0, 20000, True, 0, False)
    assert out.selected_altitude_valid == 0
    assert out.alert_approaching == 0
    assert out.alert_deviation == 0
    assert out.state == ac.AIM_ALERT_CRUISE


def test_selected_altitude_out_of_range_is_rejected_and_held(lib, st):
    """HLR-ALT-01: first a good selected altitude, then an out-of-range one
    must be rejected, holding the earlier value."""
    step(lib, st, 0, 20000, True, 20000, True)
    assert st.selected_altitude_ft == 20000

    out = step(lib, st, 100, 20000, True, 999999, True)
    assert out.selected_altitude_valid == 1
    assert st.selected_altitude_ft == 20000  # held, not overwritten


def test_invalid_current_altitude_forces_cruise(lib, st):
    """HLR-ALT-03"""
    reach_captured(lib, st, 10000)

    out = step(lib, st, 200, 0, False, 10000, True)
    assert out.state == ac.AIM_ALERT_CRUISE
    assert out.alert_approaching == 0
    assert out.alert_deviation == 0


def test_cruise_to_approaching_at_exact_band(lib, st):
    """HLR-ALT-04: exact threshold and threshold+1."""
    step(lib, st, 0, 0, True, 10000, True)  # establish target, alt far away (err huge)
    out = step(lib, st, 100, 10000 - APPROACH, True, 10000, True)  # err == APPROACH exactly
    assert out.state == ac.AIM_ALERT_APPROACHING

    st2 = new_state()
    lib.aim_alerter_init(ctypes.byref(st2))
    step(lib, st2, 0, 0, True, 10000, True)
    out2 = step(lib, st2, 100, 10000 - APPROACH - 1, True, 10000, True)  # err == APPROACH+1
    assert out2.state == ac.AIM_ALERT_CRUISE


def test_approaching_to_captured_at_exact_band(lib, st):
    """HLR-ALT-05 capture edge."""
    step(lib, st, 0, 10000 - APPROACH, True, 10000, True)  # -> APPROACHING
    out = step(lib, st, 100, 10000 - CAPTURE, True, 10000, True)  # err == CAPTURE exactly
    assert out.state == ac.AIM_ALERT_CAPTURED


def test_approaching_back_to_cruise_with_hysteresis(lib, st):
    """HLR-ALT-05 hysteresis edge: APPROACH_BAND+HYST stays APPROACHING,
    APPROACH_BAND+HYST+1 drops to CRUISE."""
    step(lib, st, 0, 10000 - APPROACH, True, 10000, True)  # -> APPROACHING
    out = step(lib, st, 100, 10000 - (APPROACH + HYST), True, 10000, True)
    assert out.state == ac.AIM_ALERT_APPROACHING

    out = step(lib, st, 200, 10000 - (APPROACH + HYST + 1), True, 10000, True)
    assert out.state == ac.AIM_ALERT_CRUISE


def test_captured_to_deviation_requires_full_persistence(lib, st):
    """HLR-ALT-06/07: just under persistence stays CAPTURED, at persistence
    transitions to DEVIATION, and a dip back inside the band resets the timer."""
    reach_captured(lib, st, 10000)  # CAPTURED as of t=1

    out = step(lib, st, 100, 10000 + DEVIATION_BAND + 1, True, 10000, True)  # start deviating
    assert out.state == ac.AIM_ALERT_CAPTURED

    out = step(lib, st, 100 + PERSIST_MS - 1, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert out.state == ac.AIM_ALERT_CAPTURED  # not yet persisted long enough

    out = step(lib, st, 100 + PERSIST_MS, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert out.state == ac.AIM_ALERT_DEVIATION
    assert out.alert_deviation == 1


def test_deviation_timer_resets_on_return_to_band(lib, st):
    """HLR-ALT-07: a dip back inside the deviation band before persistence
    completes must reset the timer, not merely delay the alert."""
    reach_captured(lib, st, 10000)

    step(lib, st, 100, 10000 + DEVIATION_BAND + 1, True, 10000, True)  # start deviating
    step(lib, st, 500, 10000, True, 10000, True)  # back within band -> timer reset
    assert st.deviating == 0

    # resume deviating; persistence must be measured from this new start, not t=100
    step(lib, st, 600, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    out = step(lib, st, 600 + PERSIST_MS - 1, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert out.state == ac.AIM_ALERT_CAPTURED  # old timer (from t=100) would have expired by now

    out = step(lib, st, 600 + PERSIST_MS, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert out.state == ac.AIM_ALERT_DEVIATION


def test_deviation_back_to_captured_with_hysteresis(lib, st):
    """HLR-ALT-08"""
    reach_captured(lib, st, 10000)
    step(lib, st, 100, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    out = step(lib, st, 100 + PERSIST_MS, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert out.state == ac.AIM_ALERT_DEVIATION

    out = step(lib, st, 100 + PERSIST_MS + 1, 10000 + (DEVIATION_BAND - HYST + 1), True, 10000, True)
    assert out.state == ac.AIM_ALERT_DEVIATION  # one past the hysteresis edge: still outside

    out = step(lib, st, 100 + PERSIST_MS + 2, 10000 + (DEVIATION_BAND - HYST), True, 10000, True)
    assert out.state == ac.AIM_ALERT_CAPTURED  # exactly at the hysteresis edge: back to CAPTURED


def test_approach_mode_inhibits_deviation(lib, st):
    """HLR-ALT-09: deviation alert never asserts while approach_mode is true."""
    reach_captured(lib, st, 10000)
    step(lib, st, 100, 10000 + DEVIATION_BAND + 1, True, 10000, True, approach_mode=True)
    out = step(lib, st, 100 + PERSIST_MS, 10000 + DEVIATION_BAND + 1, True, 10000, True, approach_mode=True)
    assert out.state == ac.AIM_ALERT_CAPTURED
    assert out.alert_deviation == 0


def test_approach_mode_downgrades_existing_deviation_and_restarts_timer(lib, st):
    """HLR-ALT-09: entering approach_mode while already in DEVIATION forces an
    immediate downgrade and restarts the persistence timer."""
    reach_captured(lib, st, 10000)
    step(lib, st, 100, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    out = step(lib, st, 100 + PERSIST_MS, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert out.state == ac.AIM_ALERT_DEVIATION

    now = 100 + PERSIST_MS + 1
    out = step(lib, st, now, 10000 + DEVIATION_BAND + 1, True, 10000, True, approach_mode=True)
    assert out.state == ac.AIM_ALERT_CAPTURED
    assert st.deviation_since_ms == now

    # still deviating, but the timer just restarted -> must not re-alert immediately
    out = step(lib, st, now + 1, 10000 + DEVIATION_BAND + 1, True, 10000, True, approach_mode=True)
    assert out.state == ac.AIM_ALERT_CAPTURED


def test_alert_flags_match_state_exactly(lib, st):
    """HLR-ALT-10"""
    out = step(lib, st, 0, 0, True, 10000, True)
    assert out.state == ac.AIM_ALERT_CRUISE
    assert out.alert_approaching == 0 and out.alert_deviation == 0

    out = step(lib, st, 100, 10000 - APPROACH, True, 10000, True)
    assert out.state == ac.AIM_ALERT_APPROACHING
    assert out.alert_approaching == 1 and out.alert_deviation == 0


@pytest.mark.parametrize("selected,accepted", [
    (-1000, True), (-1001, False), (50000, True), (50001, False),
])
def test_selected_altitude_range_boundaries(lib, st, selected, accepted):
    """HLR-ALT-01: inclusive range [-1000, 50000]."""
    out = step(lib, st, 0, 0, True, selected, True)
    assert out.selected_altitude_valid == int(accepted)


def test_corrupted_state_recovers_to_cruise(lib, st):
    """Defensive default branch: an out-of-range state byte (e.g. RAM upset)
    must fall back to CRUISE rather than stay undefined."""
    reach_captured(lib, st, 10000)
    st.state = 99
    out = step(lib, st, 10, 10000, True, 10000, True)
    assert out.state == ac.AIM_ALERT_CRUISE


def test_deviation_band_exact_boundary(lib, st):
    """HLR-ALT-06: an error of exactly DEVIATION_BAND is not a deviation;
    DEVIATION_BAND+1 is."""
    reach_captured(lib, st, 10000)
    step(lib, st, 100, 10000 + DEVIATION_BAND, True, 10000, True)
    assert st.deviating == 0
    out = step(lib, st, 100 + PERSIST_MS, 10000 + DEVIATION_BAND, True, 10000, True)
    assert out.state == ac.AIM_ALERT_CAPTURED

    step(lib, st, 5000, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert st.deviating == 1


def test_alert_flags_exclusive_to_their_state(lib, st):
    """HLR-ALT-10: alert_approaching only in APPROACHING, alert_deviation only
    in DEVIATION; neither is set in CRUISE or CAPTURED, and approaching is
    clear in DEVIATION."""
    out = step(lib, st, 0, 0, True, 10000, True)            # CRUISE
    assert (out.alert_approaching, out.alert_deviation) == (0, 0)

    out = step(lib, st, 1, 9500, True, 10000, True)         # APPROACHING
    assert (out.state, out.alert_approaching, out.alert_deviation) == (ac.AIM_ALERT_APPROACHING, 1, 0)

    out = step(lib, st, 2, 10000, True, 10000, True)        # CAPTURED
    assert (out.state, out.alert_approaching, out.alert_deviation) == (ac.AIM_ALERT_CAPTURED, 0, 0)

    step(lib, st, 100, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    out = step(lib, st, 100 + PERSIST_MS, 10000 + DEVIATION_BAND + 1, True, 10000, True)
    assert (out.state, out.alert_approaching, out.alert_deviation) == (ac.AIM_ALERT_DEVIATION, 0, 1)
