#!/usr/bin/env python3
"""Phase 7 processor-in-the-loop (PIL) harness.

Runs scripted scenarios against the Arduino target and compares every cycle's
status line with the host build of the same core (libaim), run in lockstep.

  pil.py --sim                                   emulate the target on the host
  pil.py --port /dev/ttyACM0 --adc2 /dev/ttyUSB0 real hardware (needs pyserial)

Rig: UNO USB serial (115200) carries ADC1/SELECTED/APPROACH/STEP frames; the
CP2102 bridge (38400) carries ADC2 frames to SoftwareSerial pin 10.
Time is host-supplied in STEP frames, so runs are deterministic.
"""
import argparse
import ctypes
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import aim_ctypes as ac  # noqa: E402

FIELDS = ["now", "state", "approaching", "deviation", "miscompare", "alt_valid", "alt",
          "ch1v", "ch2v", "ch1s", "ch2s", "sel_valid", "rejected"]
NORMAL, NCD = ac.AIM_SSM_NORMAL_OPERATION, ac.AIM_SSM_NO_COMPUTED_DATA


def w(alt, ssm=NORMAL, sdi=1):
    return ac.encode_word(ac.LABEL_203, sdi, ssm, alt)


class Tick:
    def __init__(self, t, w1, w2, sel, approach=0, inject_main=b"", inject_adc2=b""):
        self.t, self.w1, self.w2, self.sel, self.approach = t, w1, w2, sel, approach
        self.inject_main, self.inject_adc2 = inject_main, inject_adc2


def scenarios():
    S = {}
    ticks, t = [], 0
    for alt in list(range(8000, 10001, 100)) + [10000] * 5:       # climb and capture
        ticks.append(Tick(t, w(alt), w(alt), 10000)); t += 50
    for _ in range(30):                                            # deviate > 1 s
        ticks.append(Tick(t, w(10400), w(10400), 10000)); t += 50
    S["climb_capture_deviation"] = ticks

    ticks, t = [], 0
    for i in range(70):                                            # ADC2 +300 ft for 3.5 s
        ticks.append(Tick(t, w(10000), w(10000 if i < 5 else 10300), 10000)); t += 50
    for _ in range(80):                                            # reconverge, clear after 2 s
        ticks.append(Tick(t, w(10000), w(10000), 10000)); t += 50
    S["miscompare_latch_and_clear"] = ticks

    ticks, t = [], 0
    for i in range(40):                                            # ADC1 -> NCD, stale after 500 ms
        ticks.append(Tick(t, w(10000) if i < 10 else w(10000, NCD), w(10050), 10000)); t += 50
    S["adc1_dropout_failover"] = ticks

    ticks, t = [], 0
    bad = bytearray(ac.make_frame(ac.FRAME_ADC1_WORD, w(1)))
    bad[6] ^= 0x55
    for i in range(30):                                            # noisy link
        ticks.append(Tick(t, w(10000), w(10000), 10000, approach=1 if 10 <= i < 20 else 0,
                          inject_main=(b"\x00\xaa\x13" + bytes(bad)) if i % 5 == 0 else b"")); t += 50
    S["corrupted_link_and_approach_mode"] = ticks
    return S


# ---- transports ------------------------------------------------------------
class SimTarget:
    """Host emulation of aim_target.ino built from the same C code (libaim +
    libaimframer). Validates the harness and protocol, NOT the AVR build."""

    def __init__(self):
        self.lib, self.fl = ac.load(), ac.load_framer()
        self.aim = ac.Aim(); self.lib.aim_init(ctypes.byref(self.aim))
        self.fr = {k: ac.Framer() for k in ("main", "adc2")}
        for f in self.fr.values():
            self.fl.aim_framer_init(ctypes.byref(f))
        self.w1 = self.w2 = 0; self.sel = 0; self.sel_valid = 0; self.appr = 0
        self.lines = []

    def write_main(self, data): self._feed("main", data)
    def write_adc2(self, data): self._feed("adc2", data)

    def _feed(self, link, data):
        for b in data:
            fr = ac.Frame()
            if self.fl.aim_framer_push(ctypes.byref(self.fr[link]), b, ctypes.byref(fr)):
                self._handle(fr)

    def _handle(self, f):
        if f.type == ac.FRAME_ADC1_WORD: self.w1 = f.payload
        elif f.type == ac.FRAME_ADC2_WORD: self.w2 = f.payload
        elif f.type == ac.FRAME_SELECTED_ALT:
            self.sel = ctypes.c_int32(f.payload).value
            self.sel_valid = int(f.payload != ac.NO_TARGET)
        elif f.type == ac.FRAME_APPROACH_MODE: self.appr = int(f.payload != 0)
        elif f.type == ac.FRAME_STEP:
            o = ac.Status()
            self.lib.aim_step(ctypes.byref(self.aim), f.payload, self.w1, self.w2,
                              self.sel, self.sel_valid, self.appr, ctypes.byref(o))
            rej = self.fr["main"].rejected + self.fr["adc2"].rejected
            self.lines.append(",".join(map(str, [
                "S", f.payload, o.alerter.state, o.alerter.alert_approaching, o.alerter.alert_deviation,
                o.monitor.miscompare, o.altitude_valid, o.altitude_ft, o.monitor.ch1_valid,
                o.monitor.ch2_valid, o.monitor.ch1_stale, o.monitor.ch2_stale,
                o.alerter.selected_altitude_valid, rej])))

    def readline(self): return self.lines.pop(0)


class HwTarget:
    def __init__(self, port, adc2_port):
        import serial  # pyserial, only needed for real hardware
        self.main = serial.Serial(port, 115200, timeout=2)
        self.adc2 = serial.Serial(adc2_port, 38400, timeout=2)
        time.sleep(2.0)  # UNO auto-resets when the USB port opens
        self.main.reset_input_buffer()

    def write_main(self, data): self.main.write(data); self.main.flush()
    def write_adc2(self, data):
        self.adc2.write(data); self.adc2.flush()
        time.sleep(0.015)  # let SoftwareSerial finish receiving before STEP arrives

    def readline(self):
        line = self.main.readline().decode(errors="replace").strip()
        if not line.startswith("S,"):
            raise TimeoutError(f"no status line from target (got {line!r})")
        return line


# ---- comparison ------------------------------------------------------------
def run(target, name, ticks):
    lib = ac.load()
    ref = ac.Aim(); lib.aim_init(ctypes.byref(ref))
    mismatches, injected_bad = [], 0
    for tk in ticks:
        o = ac.Status()
        lib.aim_step(ctypes.byref(ref), tk.t, tk.w1, tk.w2, tk.sel, int(tk.sel != ac.NO_TARGET),
                     tk.approach, ctypes.byref(o))
        want = [tk.t, o.alerter.state, o.alerter.alert_approaching, o.alerter.alert_deviation,
                o.monitor.miscompare, o.altitude_valid, o.altitude_ft, o.monitor.ch1_valid,
                o.monitor.ch2_valid, o.monitor.ch1_stale, o.monitor.ch2_stale,
                o.alerter.selected_altitude_valid]
        if tk.inject_adc2: target.write_adc2(tk.inject_adc2)
        target.write_adc2(ac.make_frame(ac.FRAME_ADC2_WORD, tk.w2))
        if tk.inject_main: target.write_main(tk.inject_main)
        target.write_main(ac.make_frame(ac.FRAME_ADC1_WORD, tk.w1)
                          + ac.make_frame(ac.FRAME_SELECTED_ALT, tk.sel)
                          + ac.make_frame(ac.FRAME_APPROACH_MODE, tk.approach)
                          + ac.make_frame(ac.FRAME_STEP, tk.t))
        got = dict(zip(FIELDS, target.readline().split(",")[1:]))
        for i, k in enumerate(FIELDS[:-1]):
            if int(got[k]) != want[i]:
                mismatches.append(f"t={tk.t} {k}: target={got[k]} host={want[i]}")
        last_rejected = int(got["rejected"])
        if tk.inject_main or tk.inject_adc2:
            injected_bad += 1
    if injected_bad and last_rejected < 1:
        mismatches.append(f"link corruption injected but target reported rejected={last_rejected}")
    return mismatches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--port"); ap.add_argument("--adc2")
    ap.add_argument("--report", action="store_true", help="write docs/verification/PIL_RESULTS.md")
    a = ap.parse_args()
    if not a.sim and not (a.port and a.adc2):
        ap.error("give --sim, or both --port and --adc2")
    rows, failed = [], False
    for name, ticks in scenarios().items():
        tgt = SimTarget() if a.sim else HwTarget(a.port, a.adc2)
        mm = run(tgt, name, ticks)
        failed |= bool(mm)
        print(f"{'PASS' if not mm else 'FAIL'}  {name}  ({len(ticks)} cycles)")
        for m in mm[:10]:
            print("   ", m)
        rows.append((name, len(ticks), "PASS" if not mm else f"FAIL ({len(mm)} mismatches)"))
    if a.report:
        mode = "host simulation of the target (NOT hardware)" if a.sim else f"hardware: UNO on {a.port}"
        out = ROOT / "docs" / "verification" / "PIL_RESULTS.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("# PIL Results\n\n_Generated by `scripts/pil.py --report`._\n\n"
                       f"Run mode: **{mode}**\n\n| Scenario | Cycles | Result |\n|---|---|---|\n"
                       + "".join(f"| {n} | {c} | {r} |\n" for n, c, r in rows))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
