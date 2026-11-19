#!/usr/bin/env python3
"""Phase 6: seeded-defect (mutation) campaign.

Each mutant is one deliberate fault injected into a scratch copy of src/.
The test suite must FAIL on every mutant ("killed"). A mutant that passes
("survived") means a requirement is not adequately verified. The real src/
is never modified. Writes docs/verification/SEEDED_DEFECTS.md.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable

# (id, file, original text, mutated text, requirement affected, description)
MUTANTS = [
    ("M01", "decoder.c", "0x83u", "0x82u", "HLR-DEC-01", "wrong label constant"),
    ("M02", "decoder.c", "(word >> 8) & 0x3u", "(word >> 9) & 0x3u", "HLR-DEC-02", "SDI shifted one bit"),
    ("M03", "decoder.c", "(word >> 10) & AIM_ALT_FIELD_MASK", "(word >> 11) & AIM_ALT_FIELD_MASK", "HLR-DEC-03", "altitude field off by one bit"),
    ("M04", "decoder.c", "if ((alt_field & AIM_ALT_SIGN_BIT) != 0u)", "if (0)", "HLR-DEC-03", "sign extension removed"),
    ("M05", "decoder.c", "(word >> 28) & 0x3u", "(word >> 29) & 0x3u", "HLR-DEC-04", "SSM shifted one bit"),
    ("M06", "decoder.c", "== 1u);", "== 0u);", "HLR-DEC-05", "parity sense inverted (even instead of odd)"),
    ("M07", "decoder.c", "(label == AIM_LABEL_203) && (parity_ok != 0u)", "(label == AIM_LABEL_203)", "HLR-DEC-05", "parity ignored in valid"),
    ("M08", "decoder.c", "(label == AIM_LABEL_203) && (parity_ok != 0u)", "(label == AIM_LABEL_203) && (parity_ok != 0u) && (ssm == 3u)", "HLR-DEC-06", "valid wrongly depends on SSM"),
    ("M09", "monitor.c", "w->valid && (w->ssm == (uint8_t)AIM_SSM_NORMAL_OPERATION)", "w->valid", "HLR-MON-01", "SSM ignored in good-sample test"),
    ("M10", "monitor.c", "> AIM_CHANNEL_STALE_MS));\n    ch2", ">= AIM_CHANNEL_STALE_MS));\n    ch2", "HLR-MON-02", "stale boundary off by one (ch1)"),
    ("M11", "monitor.c", "diff > AIM_MISCOMPARE_THRESHOLD_FT", "diff >= AIM_MISCOMPARE_THRESHOLD_FT", "HLR-MON-03", "miscompare threshold boundary (>=)"),
    ("M12", "monitor.c", "(uint32_t)(now_ms - st->diverge_since_ms) >= AIM_MISCOMPARE_PERSIST_MS", "(uint32_t)(now_ms - st->diverge_since_ms) > AIM_MISCOMPARE_PERSIST_MS", "HLR-MON-03", "latch persistence off by one"),
    ("M13", "monitor.c", "st->miscompare_latched = 1u;\n                    st->diverging = 0u;", "st->miscompare_latched = 1u;", "HLR-MON-03", "diverging flag not cleared on latch"),
    ("M14", "monitor.c", "} else if ((uint32_t)(now_ms - st->converge_since_ms) >= AIM_MISCOMPARE_PERSIST_MS) {", "} else if (1) {", "HLR-MON-04", "latch clears with no persistence"),
    ("M15", "monitor.c", "} else {\n                st->converging = 0u;", "} else {\n                (void)0;", "HLR-MON-04", "converge timer not reset on re-divergence"),
    ("M16", "monitor.c", "both_usable = (uint8_t)(ch1_good && ch2_good);", "both_usable = 1u;", "HLR-MON-05", "timers run while a channel is unusable"),
    ("M17", "monitor.c", "if (ch1_good) {\n        out->altitude_available", "if (0) {\n        out->altitude_available", "HLR-MON-06", "ch1 never used for reconciliation"),
    ("M18", "monitor.c", "} else if (ch2_good) {", "} else if (0) {", "HLR-MON-06", "no fail-over to ch2"),
    ("M19", "alerter.c", "alt <= AIM_MAX_ALT_FT", "alt <= AIM_MAX_ALT_FT + 1", "HLR-ALT-01", "selected-altitude upper bound widened"),
    ("M20", "alerter.c", "alt >= AIM_MIN_ALT_FT", "alt >= AIM_MIN_ALT_FT - 1", "HLR-ALT-01", "selected-altitude lower bound widened"),
    ("M21", "alerter.c", "if (!altitude_valid || !st->have_selected_ever) {", "if ((!altitude_valid && 0) || !st->have_selected_ever) {", "HLR-ALT-03", "invalid altitude does not force CRUISE"),
    ("M22", "alerter.c", "if (err <= AIM_APPROACH_BAND_FT) {", "if (err < AIM_APPROACH_BAND_FT) {", "HLR-ALT-04", "approach boundary (<)"),
    ("M23", "alerter.c", "err > AIM_APPROACH_BAND_FT + AIM_HYSTERESIS_FT", "err > AIM_APPROACH_BAND_FT", "HLR-ALT-05", "approach hysteresis removed"),
    ("M24", "alerter.c", "if (err <= AIM_CAPTURE_BAND_FT) {", "if (err < AIM_CAPTURE_BAND_FT) {", "HLR-ALT-05", "capture boundary (<)"),
    ("M25", "alerter.c", "(uint32_t)(now_ms - st->deviation_since_ms) >= AIM_DEVIATION_PERSIST_MS", "(uint32_t)(now_ms - st->deviation_since_ms) > AIM_DEVIATION_PERSIST_MS", "HLR-ALT-06", "deviation persistence off by one"),
    ("M26", "alerter.c", "if (err > AIM_DEVIATION_BAND_FT) {", "if (err >= AIM_DEVIATION_BAND_FT) {", "HLR-ALT-06", "deviation band boundary (>=)"),
    ("M27", "alerter.c", "} else {\n            st->deviation_since_ms = 0u;\n            st->deviating = 0u;\n        }\n        break;\n\n    case AIM_ALERT_DEVIATION", "}\n        break;\n\n    case AIM_ALERT_DEVIATION", "HLR-ALT-07", "deviation timer not reset on return to band"),
    ("M28", "alerter.c", "err <= AIM_DEVIATION_BAND_FT - AIM_HYSTERESIS_FT", "err <= AIM_DEVIATION_BAND_FT", "HLR-ALT-08", "deviation-clear hysteresis removed"),
    ("M29", "alerter.c", "} else if (!approach_mode &&\n                       (uint32_t)", "} else if ((uint32_t)", "HLR-ALT-09", "approach mode no longer inhibits deviation"),
    ("M30", "alerter.c", "        if (approach_mode) {\n            /* HLR-ALT-09", "        if (0) {\n            /* HLR-ALT-09", "HLR-ALT-09", "approach mode does not downgrade active deviation"),
    ("M31", "alerter.c", "out->alert_deviation   = (uint8_t)(st->state == (uint8_t)AIM_ALERT_DEVIATION);", "out->alert_deviation   = (uint8_t)(st->state >= (uint8_t)AIM_ALERT_CAPTURED);", "HLR-ALT-10", "deviation flag asserted in CAPTURED"),
    ("M32", "alerter.c", "out->alert_approaching = (uint8_t)(st->state == (uint8_t)AIM_ALERT_APPROACHING);", "out->alert_approaching = (uint8_t)(st->state != (uint8_t)AIM_ALERT_CRUISE);", "HLR-ALT-10", "approaching flag asserted in CAPTURED/DEVIATION"),
    ("F01", "framer.c", "i < AIM_FRAME_LEN; i++) {\n        sum", "i < AIM_FRAME_LEN - 1u; i++) {\n        sum", "HLR-FRM-01", "checksum omits last byte"),
    ("F02", "framer.c", "(uint32_t)f->buf[3] << 8", "(uint32_t)f->buf[3] << 7", "HLR-FRM-01", "payload byte order/shift wrong"),
    ("F03", "framer.c", "t >= AIM_FRAME_ADC1_WORD && t <= AIM_FRAME_APPROACH_MODE", "t >= AIM_FRAME_ADC1_WORD", "HLR-FRM-02", "unknown high TYPE accepted"),
    ("F04", "framer.c", "if (f->rejected < 0xFFFFu) {", "if (1) {", "HLR-FRM-02", "reject counter wraps instead of saturating"),
    ("F05", "framer.c", "tmp[i] = f->buf[i + 1u];", "tmp[i] = f->buf[i];", "HLR-FRM-03", "resync re-feeds the false SYNC (no progress)"),
    ("F06", "framer.c", "        f->n = 0u;\n        return 1u;", "        return 1u;", "HLR-FRM-04", "parser not reset after delivering a frame"),
    ("M33", "aim.c", "out->altitude_valid = out->monitor.altitude_available;", "out->altitude_valid = 1u;", "SYS-5", "altitude validity forced true"),
]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    results = []
    for mid, fname, old, new, req, desc in MUTANTS:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            shutil.copytree(ROOT / "src", tmp / "src")
            shutil.copytree(ROOT / "target", tmp / "target", symlinks=True)
            shutil.copy(ROOT / "CMakeLists.txt", tmp)
            path = (tmp / "target" / "aim_target" / fname) if fname == "framer.c" else (tmp / "src" / fname)
            src = path.read_text()
            if src.count(old) != 1:
                results.append((mid, req, desc, "INVALID", f"pattern matched {src.count(old)}x"))
                print(f"{mid} INVALID   pattern matched {src.count(old)}x")
                continue
            path.write_text(src.replace(old, new))
            b = run(["cmake", "-S", ".", "-B", "b", "-DCMAKE_BUILD_TYPE=Debug"], tmp)
            b = run(["cmake", "--build", "b"], tmp) if b.returncode == 0 else b
            if b.returncode != 0:
                results.append((mid, req, desc, "INVALID", "mutant does not compile"))
                print(f"{mid} INVALID   {b.stderr.strip()[-200:]}")
                continue
            env_lib = str(tmp / "b" / "libaim.so")
            t = subprocess.run([PY, "-m", "pytest", "tests", "-q", "-x", "-p", "no:cacheprovider"],
                               cwd=ROOT, capture_output=True, text=True,
                               env={**__import__("os").environ, "AIM_LIB": env_lib,
                                    "AIM_FRAMER_LIB": str(tmp / "b" / "libaimframer.so")})
            killer = ""
            for line in t.stdout.splitlines():
                if line.startswith("FAILED"):
                    killer = line.split()[1].split("::", 1)[-1]
            results.append((mid, req, desc, "KILLED" if t.returncode != 0 else "SURVIVED", killer))
        print(f"{mid} {results[-1][3]:9} {req:11} {desc}")

    killed = sum(r[3] == "KILLED" for r in results)
    survived = [r for r in results if r[3] == "SURVIVED"]
    invalid = [r for r in results if r[3] == "INVALID"]
    L = ["# Seeded-Defect (Mutation) Campaign", "",
         "_Generated by `scripts/mutate.py`._", "",
         f"**{killed}/{len(results)} mutants killed**, {len(survived)} survived, {len(invalid)} invalid.", "",
         "| ID | Requirement | Seeded defect | Result | First failing test |", "|---|---|---|---|---|"]
    L += [f"| {m} | {r} | {d} | {s} | {('`'+k+'`') if k and s == 'KILLED' else k or '—'} |" for m, r, d, s, k in results]
    out = ROOT / "docs" / "verification" / "SEEDED_DEFECTS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    print(f"\n{killed}/{len(results)} killed, {len(survived)} survived, {len(invalid)} invalid")
    sys.exit(1 if survived or invalid else 0)


if __name__ == "__main__":
    main()
