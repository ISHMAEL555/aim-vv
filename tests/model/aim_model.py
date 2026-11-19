"""Executable reference model of AIM, written from the HLR text in reqs/hlr.sdoc
(not from src/). Phase 10 substitute for the Stateflow model: MATLAB/Stateflow is
not available in this environment, so this plays the same role -- an independent
behavioural model run back-to-back against the C code (see
tests/integration/test_back_to_back.py).
"""
MIN_ALT, MAX_ALT = -1000, 50000
APPROACH, CAPTURE, DEV_BAND, HYST = 1000, 300, 300, 50
DEV_PERSIST, MISC_THRESH, MISC_PERSIST, STALE = 1000, 200, 2000, 500
CRUISE, APPROACHING, CAPTURED, DEVIATION = 0, 1, 2, 3
NORMAL = 3


class Model:
    def __init__(self):
        self.last_good = [None, None]          # time of last good sample per channel
        self.diverge_t = self.converge_t = None
        self.latched = False
        self.state = CRUISE
        self.dev_t = None
        self.sel = None

    # words are dicts: valid, ssm, alt
    def step(self, now, w1, w2, sel, sel_ok, approach):
        # ---- monitor
        good = [bool(w["valid"]) and w["ssm"] == NORMAL for w in (w1, w2)]
        for i in (0, 1):
            if good[i]:
                self.last_good[i] = now
        stale = [self.last_good[i] is not None and (now - self.last_good[i]) > STALE for i in (0, 1)]
        if good[0] and good[1]:                # both usable => timers run (HLR-MON-05 otherwise frozen)
            diff = abs(w1["alt"] - w2["alt"])
            if not self.latched:
                if diff > MISC_THRESH:
                    if self.diverge_t is None:
                        self.diverge_t = now
                    elif now - self.diverge_t >= MISC_PERSIST:
                        self.latched, self.diverge_t = True, None
                else:
                    self.diverge_t = None
            else:
                if diff <= MISC_THRESH:
                    if self.converge_t is None:
                        self.converge_t = now
                    elif now - self.converge_t >= MISC_PERSIST:
                        self.latched, self.converge_t = False, None
                else:
                    self.converge_t = None
        if good[0]:
            alt_ok, alt = True, w1["alt"]
        elif good[1]:
            alt_ok, alt = True, w2["alt"]
        else:
            alt_ok, alt = False, 0

        # ---- alerter
        if sel_ok and MIN_ALT <= sel <= MAX_ALT:
            self.sel = sel
        if not alt_ok or self.sel is None:
            self.state, self.dev_t = CRUISE, None
        else:
            err = abs(alt - self.sel)
            if self.state == CRUISE:
                if err <= APPROACH:
                    self.state = APPROACHING
            elif self.state == APPROACHING:
                if err <= CAPTURE:
                    self.state, self.dev_t = CAPTURED, None
                elif err > APPROACH + HYST:
                    self.state = CRUISE
            elif self.state == CAPTURED:
                if err > DEV_BAND:
                    if self.dev_t is None:
                        self.dev_t = now
                    elif not approach and now - self.dev_t >= DEV_PERSIST:
                        self.state = DEVIATION
                else:
                    self.dev_t = None
            elif self.state == DEVIATION:
                if approach:
                    self.state, self.dev_t = CAPTURED, now
                elif err <= DEV_BAND - HYST:
                    self.state, self.dev_t = CAPTURED, None
        return {
            "state": self.state,
            "approaching": int(self.state == APPROACHING and alt_ok and self.sel is not None),
            "deviation": int(self.state == DEVIATION),
            "miscompare": int(self.latched),
            "alt_valid": int(alt_ok), "alt": alt,
            "ch1_valid": int(good[0]), "ch2_valid": int(good[1]),
            "ch1_stale": int(stale[0]), "ch2_stale": int(stale[1]),
            "sel_valid": int(self.sel is not None),
        }
