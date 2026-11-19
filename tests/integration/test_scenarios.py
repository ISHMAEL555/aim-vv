"""Integration tests through the public aim_step API. SYS tags: SYS-1..9.

Each test drives aim_step() across a sequence of simulated 50 ms-ish ticks
(timing is deliberately irregular/coarse in places to show the logic does
not depend on a fixed call rate -- see HLR-TIM-01/02).
"""
import ctypes

import aim_ctypes as ac

SELECTED = 10000
APPROACH = 1000
CAPTURE = 300
DEVIATION_BAND = 300
HYST = 50
DEV_PERSIST_MS = 1000
MISCOMPARE_THRESHOLD = 200
MISCOMPARE_PERSIST_MS = 2000
STALE_MS = 500

GOOD_SSM = ac.AIM_SSM_NORMAL_OPERATION


def good_word(alt_ft, sdi=1):
    return ac.encode_word(ac.LABEL_203, sdi, GOOD_SSM, alt_ft)


def ncd_word(alt_ft, sdi=1):
    return ac.encode_word(ac.LABEL_203, sdi, ac.AIM_SSM_NO_COMPUTED_DATA, alt_ft)


def bad_label_word(alt_ft, sdi=1):
    return ac.encode_word(0x55, sdi, GOOD_SSM, alt_ft) & 0xFFFFFFFE  # also corrupt parity, don't care


def new_aim(lib):
    a = ac.Aim()
    lib.aim_init(ctypes.byref(a))
    return a


def tick(lib, aim, now_ms, w1, w2, selected, selected_valid=True, approach_mode=False):
    out = ac.Status()
    lib.aim_step(
        ctypes.byref(aim), ctypes.c_uint32(now_ms),
        ctypes.c_uint32(w1), ctypes.c_uint32(w2),
        ctypes.c_int32(selected), ctypes.c_uint8(int(selected_valid)),
        ctypes.c_uint8(int(approach_mode)),
        ctypes.byref(out),
    )
    return out


def test_climb_capture_deviation_and_return(lib):
    """SYS-1, SYS-6, SYS-7: a full climb-capture-deviate-return cycle with
    both ADCs agreeing throughout (no miscompare noise)."""
    aim = new_aim(lib)

    out = tick(lib, aim, 0, good_word(SELECTED - 5000), good_word(SELECTED - 5000), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_CRUISE

    out = tick(lib, aim, 100, good_word(SELECTED - APPROACH), good_word(SELECTED - APPROACH), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_APPROACHING
    assert out.alerter.alert_approaching == 1

    out = tick(lib, aim, 200, good_word(SELECTED - CAPTURE), good_word(SELECTED - CAPTURE), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED

    out = tick(lib, aim, 300, good_word(SELECTED + DEVIATION_BAND + 1), good_word(SELECTED + DEVIATION_BAND + 1), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED  # deviation just started

    out = tick(lib, aim, 300 + DEV_PERSIST_MS, good_word(SELECTED + DEVIATION_BAND + 1),
               good_word(SELECTED + DEVIATION_BAND + 1), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_DEVIATION
    assert out.alerter.alert_deviation == 1

    out = tick(lib, aim, 300 + DEV_PERSIST_MS + 100, good_word(SELECTED), good_word(SELECTED), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED
    assert out.alerter.alert_deviation == 0
    assert out.monitor.miscompare == 0


def test_adc2_drift_causes_latched_miscompare_without_disturbing_alerting(lib):
    """SYS-4: ADC-2 drifts away from ADC-1 while ADC-1 (primary) stays
    correct; the monitor must latch a miscompare, but alerting must keep
    using ADC-1 and must not itself be disrupted."""
    aim = new_aim(lib)

    tick(lib, aim, 0, good_word(SELECTED), good_word(SELECTED), SELECTED)
    out = tick(lib, aim, 1, good_word(SELECTED), good_word(SELECTED), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED
    assert out.monitor.miscompare == 0

    drifted = SELECTED + MISCOMPARE_THRESHOLD + 50  # ADC-2 only; ADC-1 unaffected
    out = tick(lib, aim, 100, good_word(SELECTED), good_word(drifted), SELECTED)
    assert out.monitor.miscompare == 0  # not yet persisted

    out = tick(lib, aim, 100 + MISCOMPARE_PERSIST_MS, good_word(SELECTED), good_word(drifted), SELECTED)
    assert out.monitor.miscompare == 1
    assert out.altitude_ft == SELECTED  # reconciliation still prefers ADC-1
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED  # alerting undisturbed by the drift


def test_channel_goes_stale_mid_alert_and_system_fails_over(lib):
    """SYS-5: ADC-1 (primary) stops producing good samples while the system
    is already alerting (CAPTURED); the system must detect the staleness and
    fail over to ADC-2 without losing the alerting function (FC-01/FC-06)."""
    aim = new_aim(lib)

    tick(lib, aim, 0, good_word(SELECTED), good_word(SELECTED), SELECTED)
    out = tick(lib, aim, 1, good_word(SELECTED), good_word(SELECTED), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED

    # ADC-1 starts sending NCD (e.g. a computer fault); ADC-2 keeps reporting good data
    out = tick(lib, aim, 10, ncd_word(SELECTED), good_word(SELECTED), SELECTED)
    assert out.monitor.ch1_valid == 0
    assert out.monitor.altitude_available == 1  # already failed over to ch2 this tick
    assert out.altitude_ft == SELECTED

    out = tick(lib, aim, 10 + STALE_MS + 1, ncd_word(SELECTED), good_word(SELECTED), SELECTED)
    assert out.monitor.ch1_stale == 1
    assert out.monitor.altitude_available == 1
    assert out.altitude_ft == SELECTED
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED  # alerting kept working throughout


def test_selected_altitude_change_during_approach_mode(lib):
    """SYS-7: a pilot-commanded target change while approach_mode is active
    (e.g. a go-around altitude change) must be adopted immediately, and
    deviation alerting must remain inhibited throughout approach mode."""
    aim = new_aim(lib)

    tick(lib, aim, 0, good_word(SELECTED), good_word(SELECTED), SELECTED, approach_mode=True)
    out = tick(lib, aim, 1, good_word(SELECTED), good_word(SELECTED), SELECTED, approach_mode=True)
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED

    new_target = SELECTED + 3000
    out = tick(lib, aim, 100, good_word(SELECTED), good_word(SELECTED), new_target, approach_mode=True)
    assert aim.alerter.selected_altitude_ft == new_target
    # HLR-ALT-06/08 only define CAPTURED <-> DEVIATION transitions; capture is
    # "sticky" and does not revert to APPROACHING/CRUISE on a target change,
    # so the large resulting error is handled purely via the (here-inhibited)
    # deviation path, not a re-approach.
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED
    assert out.alerter.alert_deviation == 0

    # even after a long time well outside the deviation band, approach_mode
    # must keep suppressing the deviation alert
    out = tick(lib, aim, 100 + DEV_PERSIST_MS * 5, good_word(SELECTED), good_word(SELECTED), new_target,
               approach_mode=True)
    assert out.alerter.alert_deviation == 0


def test_invalid_selected_altitude_holds_last_good_target(lib):
    """SYS-8: an out-of-range selected altitude must be rejected and the
    last valid target held, without the system crashing or mis-alerting."""
    aim = new_aim(lib)

    tick(lib, aim, 0, good_word(SELECTED), good_word(SELECTED), SELECTED)
    out = tick(lib, aim, 1, good_word(SELECTED), good_word(SELECTED), SELECTED)
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED

    out = tick(lib, aim, 100, good_word(SELECTED), good_word(SELECTED), 999999)
    assert aim.alerter.selected_altitude_ft == SELECTED  # held
    assert out.alerter.selected_altitude_valid == 1
    assert out.alerter.state == ac.AIM_ALERT_CAPTURED  # unaffected by the rejected input


def test_power_up_is_deterministic_and_miscompare_can_start_at_t_zero(lib):
    """SYS-9 / power-up: the very first tick after aim_init (now_ms == 0)
    must behave the same as any other tick -- in particular a miscompare
    that begins at t=0 must still latch at exactly the persistence window,
    not be lost or delayed by the zero-is-ambiguous sentinel pitfall."""
    aim = new_aim(lib)

    out = tick(lib, aim, 0, good_word(SELECTED), good_word(SELECTED), 0, selected_valid=False)
    assert out.alerter.state == ac.AIM_ALERT_CRUISE
    assert out.alerter.selected_altitude_valid == 0
    assert out.monitor.miscompare == 0

    aim2 = new_aim(lib)
    drifted = SELECTED + MISCOMPARE_THRESHOLD + 1
    tick(lib, aim2, 0, good_word(SELECTED), good_word(drifted), SELECTED)  # divergence starts at t=0
    out = tick(lib, aim2, MISCOMPARE_PERSIST_MS - 1, good_word(SELECTED), good_word(drifted), SELECTED)
    assert out.monitor.miscompare == 0
    out = tick(lib, aim2, MISCOMPARE_PERSIST_MS, good_word(SELECTED), good_word(drifted), SELECTED)
    assert out.monitor.miscompare == 1


def test_malformed_word_on_one_channel_is_rejected_system_wide(lib):
    """SYS-2, SYS-3: a structurally invalid word must not be treated as
    usable data anywhere in the pipeline."""
    aim = new_aim(lib)
    out = tick(lib, aim, 0, bad_label_word(SELECTED), good_word(SELECTED), SELECTED)
    assert out.monitor.ch1_valid == 0
    assert out.monitor.altitude_available == 1
    assert out.altitude_ft == SELECTED  # only the good channel (ch2) is used


def test_no_channels_means_altitude_invalid_and_no_alerts(lib):
    """SYS-3, SYS-5: with neither channel carrying good data the reconciled
    altitude is reported invalid and alerting stays in CRUISE."""
    aim = new_aim(lib)
    out = tick(lib, aim, 0, ncd_word(SELECTED), bad_label_word(SELECTED), SELECTED)
    assert out.altitude_valid == 0
    assert out.monitor.altitude_available == 0
    assert out.alerter.state == ac.AIM_ALERT_CRUISE
    assert out.alerter.alert_approaching == 0
    assert out.alerter.alert_deviation == 0


def test_corrupted_link_does_not_disturb_valid_data_path(framer_lib):
    """SYS-10: a byte stream with garbage, a corrupted frame and a truncated
    frame interleaved with good frames yields exactly the good frames, in order."""
    fr = ac.Framer()
    framer_lib.aim_framer_init(ctypes.byref(fr))
    good = [ac.make_frame(ac.FRAME_ADC1_WORD, good_word(10000)),
            ac.make_frame(ac.FRAME_SELECTED_ALT, 10000),
            ac.make_frame(ac.FRAME_STEP, 100)]
    bad = bytearray(ac.make_frame(ac.FRAME_ADC2_WORD, good_word(10000)))
    bad[4] ^= 0xFF
    stream = b"\x01\x02" + good[0] + bytes(bad) + good[1] + good[2][:3] + good[2]
    got = []
    for b in stream:
        out = ac.Frame()
        if framer_lib.aim_framer_push(ctypes.byref(fr), b, ctypes.byref(out)):
            got.append((out.type, out.payload))
    assert got == [(1, good_word(10000)), (2, 10000), (4, 100)]
