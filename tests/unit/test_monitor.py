"""Unit tests for src/monitor.c. HLR tags: HLR-MON-01..06."""
import ctypes

import pytest

import aim_ctypes as ac

STALE_MS = 500
THRESHOLD = 200
PERSIST_MS = 2000


def word(valid=True, ssm=ac.AIM_SSM_NORMAL_OPERATION, altitude_ft=10000):
    return ac.DecodedWord(valid=int(valid), parity_ok=1, label=ac.LABEL_203, sdi=1,
                           ssm=ssm, altitude_ft=altitude_ft)


def update(lib, st, now_ms, ch1, ch2):
    out = ac.MonitorStatus()
    lib.aim_monitor_update(ctypes.byref(st), ctypes.c_uint32(now_ms),
                            ctypes.byref(ch1), ctypes.byref(ch2), ctypes.byref(out))
    return out


@pytest.fixture
def st(lib):
    s = ac.MonitorState()
    lib.aim_monitor_init(ctypes.byref(s))
    return s


def test_invalid_or_wrong_ssm_is_not_good(lib, st):
    """HLR-MON-01"""
    out = update(lib, st, 0, word(valid=False), word())
    assert out.ch1_valid == 0
    assert out.ch2_valid == 1

    out = update(lib, st, 100, word(ssm=ac.AIM_SSM_NO_COMPUTED_DATA), word())
    assert out.ch1_valid == 0


def test_never_good_channel_is_invalid_not_stale(lib, st):
    """HLR-MON-02: a channel that has never produced a good sample is
    reported invalid, not stale, even after a long time."""
    out = update(lib, st, 10_000, word(valid=False), word())
    assert out.ch1_valid == 0
    assert out.ch1_stale == 0


def test_staleness_exact_boundary(lib, st):
    """HLR-MON-02: exactly STALE_MS is not yet stale, STALE_MS+1 is."""
    update(lib, st, 0, word(), word())  # both good at t=0

    out = update(lib, st, STALE_MS, word(valid=False), word())
    assert out.ch1_stale == 0

    out = update(lib, st, STALE_MS + 1, word(valid=False), word())
    assert out.ch1_stale == 1


def test_miscompare_requires_full_persistence(lib, st):
    """HLR-MON-03: just under persistence does not latch; at persistence it does."""
    update(lib, st, 0, word(altitude_ft=10000), word(altitude_ft=10000))  # agree

    diverging1 = word(altitude_ft=10000)
    diverging2 = word(altitude_ft=10000 + THRESHOLD + 1)

    out = update(lib, st, 100, diverging1, diverging2)
    assert out.miscompare == 0

    out = update(lib, st, 100 + PERSIST_MS - 1, diverging1, diverging2)
    assert out.miscompare == 0

    out = update(lib, st, 100 + PERSIST_MS, diverging1, diverging2)
    assert out.miscompare == 1


def test_miscompare_at_exact_threshold_does_not_latch(lib, st):
    """HLR-MON-03: a difference exactly at the threshold must not start the
    divergence timer."""
    a = word(altitude_ft=10000)
    b = word(altitude_ft=10000 + THRESHOLD)  # exactly at threshold, not exceeding it
    for t in (0, PERSIST_MS, 2 * PERSIST_MS):
        out = update(lib, st, t, a, b)
    assert out.miscompare == 0


def test_miscompare_clear_requires_full_persistence(lib, st):
    """HLR-MON-04"""
    a = word(altitude_ft=10000)
    b_bad = word(altitude_ft=10000 + THRESHOLD + 1)
    b_good = word(altitude_ft=10000)

    update(lib, st, 0, a, b_bad)
    out = update(lib, st, PERSIST_MS, a, b_bad)
    assert out.miscompare == 1  # latched

    out = update(lib, st, PERSIST_MS + 100, a, b_good)
    assert out.miscompare == 1  # not yet cleared

    out = update(lib, st, PERSIST_MS + 100 + PERSIST_MS - 1, a, b_good)
    assert out.miscompare == 1

    out = update(lib, st, PERSIST_MS + 100 + PERSIST_MS, a, b_good)
    assert out.miscompare == 0


def test_timers_frozen_when_a_channel_is_unusable(lib, st):
    """HLR-MON-05: a transient dropout of one channel mid-divergence must not
    reset the divergence timer's anchor -- "frozen" means the unusable sample
    is simply not acted on, so the latch still occurs at the original
    divergence start time plus the persistence window, undisturbed by the
    dropout in between."""
    a = word(altitude_ft=10000)
    b_bad = word(altitude_ft=10000 + THRESHOLD + 1)

    update(lib, st, 0, a, b_bad)  # start diverging, anchor = t=0
    # ch2 goes invalid partway through the persistence window; must not reset the anchor
    update(lib, st, PERSIST_MS // 2, a, word(valid=False))

    out = update(lib, st, PERSIST_MS - 1, a, b_bad)
    assert out.miscompare == 0  # not latched yet

    out = update(lib, st, PERSIST_MS, a, b_bad)
    assert out.miscompare == 1  # latches exactly at the original anchor + persistence


def test_reconciliation_prefers_ch1_then_ch2_then_unavailable(lib, st):
    """HLR-MON-06"""
    out = update(lib, st, 0, word(altitude_ft=11111), word(altitude_ft=22222))
    assert out.altitude_available == 1
    assert out.reconciled_altitude_ft == 11111

    out = update(lib, st, 100, word(valid=False), word(altitude_ft=22222))
    assert out.altitude_available == 1
    assert out.reconciled_altitude_ft == 22222

    out = update(lib, st, 200, word(valid=False), word(valid=False))
    assert out.altitude_available == 0


def test_ch2_staleness_and_ch1_stale_failover(lib, st):
    """HLR-MON-02 / HLR-MON-06: each channel goes stale independently, and a
    stale ch1 fails over to a good ch2."""
    update(lib, st, 0, word(), word(altitude_ft=11000))

    out = update(lib, st, STALE_MS + 1, word(), word(valid=False))
    assert out.ch2_stale == 1
    assert out.ch1_stale == 0
    assert out.reconciled_altitude_ft == 10000

    # Now ch1 stops while ch2 is good again: ch1 stale, ch2 used.
    st2 = ac.MonitorState()
    lib.aim_monitor_init(ctypes.byref(st2))
    update(lib, st2, 0, word(), word(altitude_ft=11000))
    out = update(lib, st2, STALE_MS + 1, word(valid=False), word(altitude_ft=11000))
    assert out.ch1_stale == 1
    assert out.altitude_available == 1
    assert out.reconciled_altitude_ft == 11000


def test_both_stale_means_unavailable(lib, st):
    """HLR-MON-06"""
    update(lib, st, 0, word(), word())
    out = update(lib, st, STALE_MS + 1, word(valid=False), word(valid=False))
    assert out.altitude_available == 0


def test_never_good_ch2_is_invalid_not_stale(lib, st):
    """HLR-MON-02: a channel that was never good is invalid, not stale."""
    out = update(lib, st, 10_000, word(), word(valid=False))
    assert out.ch2_valid == 0
    assert out.ch2_stale == 0
    assert out.reconciled_altitude_ft == 10000


def test_latched_miscompare_reconverge_timer_restarts(lib, st):
    """HLR-MON-04: re-diverging mid-clear abandons the clear attempt, so the
    full persistence time must elapse again from the next convergence."""
    a = word(altitude_ft=10000)
    bad = word(altitude_ft=10000 + THRESHOLD + 1)
    good = word(altitude_ft=10000)

    update(lib, st, 0, a, bad)
    update(lib, st, PERSIST_MS, a, bad)           # latched
    update(lib, st, PERSIST_MS + 100, a, good)    # converging starts
    update(lib, st, PERSIST_MS + 200, a, bad)     # diverges again: reset
    update(lib, st, PERSIST_MS + 300, a, good)    # converging restarts
    out = update(lib, st, PERSIST_MS + 300 + PERSIST_MS - 1, a, good)
    assert out.miscompare == 1
    out = update(lib, st, PERSIST_MS + 300 + PERSIST_MS, a, good)
    assert out.miscompare == 0


def test_rediverge_after_clear_needs_full_persistence_again(lib, st):
    """HLR-MON-03/04: after the latch has cleared, a fresh divergence must
    again persist for the full time; stale divergence state from the earlier
    episode must not cause an instant re-latch."""
    a = word(altitude_ft=10000)
    bad = word(altitude_ft=10000 + THRESHOLD + 1)
    good = word(altitude_ft=10000)

    update(lib, st, 0, a, bad)
    update(lib, st, PERSIST_MS, a, bad)               # latched
    update(lib, st, PERSIST_MS + 10, a, good)
    out = update(lib, st, 2 * PERSIST_MS + 10, a, good)
    assert out.miscompare == 0                        # cleared

    t = 2 * PERSIST_MS + 20
    out = update(lib, st, t, a, bad)                  # new divergence begins
    assert out.miscompare == 0
    out = update(lib, st, t + PERSIST_MS - 1, a, bad)
    assert out.miscompare == 0
    out = update(lib, st, t + PERSIST_MS, a, bad)
    assert out.miscompare == 1
