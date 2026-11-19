"""Unit tests for the cross-cutting timing requirements. HLR tags: HLR-TIM-01/02."""
import ctypes

import aim_ctypes as ac

STALE_MS = 500


def test_elapsed_time_is_wraparound_safe(lib):
    """HLR-TIM-01: a channel whose last good sample was just before the
    uint32_t millisecond counter wraps must compute a small, correct elapsed
    time after the wrap, not a huge one from a naive signed/overflowed
    subtraction."""
    st = ac.MonitorState()
    lib.aim_monitor_init(ctypes.byref(st))

    near_wrap = 0xFFFFFFF0  # 16 ms before the uint32_t rolls over
    good = ac.DecodedWord(valid=1, parity_ok=1, label=ac.LABEL_203, sdi=1,
                           ssm=ac.AIM_SSM_NORMAL_OPERATION, altitude_ft=10000)
    bad = ac.DecodedWord(valid=0, parity_ok=0, label=0, sdi=0, ssm=0, altitude_ft=0)
    out = ac.MonitorStatus()

    lib.aim_monitor_update(ctypes.byref(st), ctypes.c_uint32(near_wrap),
                            ctypes.byref(good), ctypes.byref(good), ctypes.byref(out))

    # 36 ms of true elapsed time after wrapping past 0xFFFFFFFF
    now_ms = (near_wrap + 36) % (2 ** 32)
    lib.aim_monitor_update(ctypes.byref(st), ctypes.c_uint32(now_ms),
                            ctypes.byref(bad), ctypes.byref(bad), ctypes.byref(out))

    assert out.ch1_stale == 0  # 36 ms elapsed, well under AIM_CHANNEL_STALE_MS (500)


def test_result_depends_only_on_state_and_inputs_not_call_history(lib):
    """HLR-TIM-02: replaying the same (state, now_ms, inputs) must give the
    same result regardless of what happened on previous calls -- i.e. there
    is no hidden counter or wall-clock dependency inside the library."""
    st_a = ac.AlerterState()
    st_b = ac.AlerterState()
    lib.aim_alerter_init(ctypes.byref(st_a))
    lib.aim_alerter_init(ctypes.byref(st_b))

    def run(st, n_warmup_calls):
        out = ac.AlerterStatus()
        for _ in range(n_warmup_calls):
            lib.aim_alerter_update(ctypes.byref(st), ctypes.c_uint32(0),
                                    ctypes.c_int32(20000), ctypes.c_uint8(1),
                                    ctypes.c_int32(10000), ctypes.c_uint8(1),
                                    ctypes.c_uint8(0), ctypes.byref(out))
        return out

    out_a = run(st_a, 1)
    out_b = run(st_b, 7)  # same state reached via a different number of prior ticks

    assert (st_a.state, st_a.selected_altitude_ft) == (st_b.state, st_b.selected_altitude_ft)
    assert (out_a.state, out_a.alert_approaching, out_a.alert_deviation) == \
           (out_b.state, out_b.alert_approaching, out_b.alert_deviation)
