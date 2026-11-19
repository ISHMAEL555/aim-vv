"""Back-to-back test: C implementation vs. the independent reference model
(tests/model/aim_model.py) on randomised stimulus. SYS tags below."""
import ctypes
import pathlib
import random
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "model"))
import aim_model  # noqa: E402

import aim_ctypes as ac  # noqa: E402


def gen_word(rng, alt):
    r = rng.random()
    if r < 0.80:
        return ac.encode_word(ac.LABEL_203, 1, 3, alt), dict(valid=1, ssm=3, alt=alt)
    if r < 0.90:
        ssm = rng.choice([0, 1, 2])
        return ac.encode_word(ac.LABEL_203, 1, ssm, alt), dict(valid=1, ssm=ssm, alt=alt)
    word = ac.encode_word(0x55, 1, 3, alt)                      # wrong label
    return word, dict(valid=0, ssm=3, alt=alt)


@pytest.mark.parametrize("seed", range(150))
def test_c_matches_reference_model(lib, seed):
    """SYS-3, SYS-4, SYS-5, SYS-6, SYS-7, SYS-8, SYS-9: 400 random cycles
    (irregular time steps, dropouts, SSM changes, bad labels, out-of-range and
    missing selected altitude, approach-mode toggling) must give identical
    outputs from the C code and the model on every cycle."""
    rng = random.Random(seed)
    model, aim, now = aim_model.Model(), ac.Aim(), rng.choice([0, 1000, 2**32 - 3000])
    lib.aim_init(ctypes.byref(aim))
    sel, true_alt = 10000, 9000
    for _ in range(400):
        now = (now + rng.choice([1, 20, 50, 50, 100, 400, 700])) & 0xFFFFFFFF
        true_alt += rng.choice([-400, -60, 0, 0, 60, 400]) if rng.random() < 0.7 else 0
        if rng.random() < 0.03:
            sel = rng.choice([10000, 10500, -1001, 50001, 20000, 8000])
        sel_ok = rng.random() > 0.05
        approach = int(rng.random() < 0.15)
        a1 = true_alt
        a2 = true_alt + (rng.choice([0, 0, 0, 250, -250, 1000]) if rng.random() < 0.5 else 0)
        w1, m1 = gen_word(rng, a1)
        w2, m2 = gen_word(rng, a2)

        # model uses an unwrapped time base is not needed: arithmetic is mod 2**32 in C,
        # so give the model the same wrapped value but unwrap differences identically.
        want = _wrap_model_step(model, now, m1, m2, sel, sel_ok, approach)
        out = ac.Status()
        lib.aim_step(ctypes.byref(aim), now, w1, w2, sel, int(sel_ok), approach, ctypes.byref(out))
        got = {
            "state": out.alerter.state, "approaching": out.alerter.alert_approaching,
            "deviation": out.alerter.alert_deviation, "miscompare": out.monitor.miscompare,
            "alt_valid": out.altitude_valid, "alt": out.altitude_ft,
            "ch1_valid": out.monitor.ch1_valid, "ch2_valid": out.monitor.ch2_valid,
            "ch1_stale": out.monitor.ch1_stale, "ch2_stale": out.monitor.ch2_stale,
            "sel_valid": out.alerter.selected_altitude_valid,
        }
        assert got == want, f"seed={seed} now={now}"


def _wrap_model_step(model, now, m1, m2, sel, sel_ok, approach):
    """Feed the model a monotonically increasing time (unwrapping the 32-bit
    counter), which is what 'wraparound-safe subtraction' (HLR-TIM-01) means."""
    base = getattr(model, "_base", 0)
    last = getattr(model, "_last", None)
    if last is not None and now < last:
        base += 1 << 32
    model._base, model._last = base, now
    return model.step(base + now, m1, m2, sel, sel_ok, approach)
