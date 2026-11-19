# Change Control Log

**Baseline:** commit `bbf3f86` (Phases 0–3: foundation, C core, unit tests, integration tests).
Every change after baseline needs: reason, affected requirements/artefacts, impact analysis,
and regression evidence (full `scripts/check.sh` + `trace.py --check` + `mutate.py`).

| ID | Change | Reason |
|---|---|---|
| CR-001 | `src/monitor.c`: removed `!ch*_stale` terms from usable/reconcile conditions | Coverage (Phase 4) |
| CR-002 | `src/decoder.c`: `1u` → `UINT32_C(1)` in sign-bit and field-mask macros | **Defect** found by Phase 7 AVR build |
| CR-003 | ICD §3: added `STEP`, `APPROACH_MODE` frames, execution model, status line; added SYS-10, HLR-FRM-01..04 | Phase 7 needs host-supplied time and approach-mode input |
| CR-004 | New tests: coverage gaps, survivors of seeded-defect campaign | Phases 4 and 6 |
| CR-005 | Non-functional: CMake options (`AIM_COVERAGE`, `AIM_STRICT`), `AIM_LIB`/`AIM_FRAMER_LIB` loader overrides, scripts, CI | Tooling |

## CR-001 — Unreachable branches in monitor.c
- **Change:** `both_usable = ch1_good && ch2_good` (was `… && !ch1_stale && !ch2_stale`); reconciliation tests `ch1_good` / `ch2_good` only.
- **Rationale:** if a channel is good in this call, `last_good_ms == now_ms`, so `now_ms - last_good_ms == 0` and it cannot be stale. The extra terms had no reachable false branch (gcov showed 3 untaken branches).
- **Impact:** none on behaviour — logically equivalent. Affects HLR-MON-02, -03, -05, -06. Stale flags are still computed and reported.
- **Evidence:** 100 % branch coverage after change; all monitor tests, back-to-back model and mutants M09–M18 pass/killed.

## CR-002 — 16-bit `int` shift defect in decoder (AVR)
- **Defect:** `AIM_ALT_SIGN_BIT` = `1u << 17` and `AIM_ALT_FIELD_MASK` = `(1u << 18) - 1u`. On AVR `unsigned int` is 16 bits, so these shifts overflow; the altitude field would decode incorrectly on the target. The host (32-bit `int`) never exhibits it.
- **Detection:** `arduino-cli compile --warnings all` → `-Wshift-count-overflow`, the first time the core was compiled for the real target. Not detectable by any host test.
- **Fix:** `UINT32_C(1)`. Host behaviour unchanged (all decoder tests/vectors identical).
- **Impact:** HLR-DEC-03; common-cause for FC-03 (identical corruption of both channels would mask a real miscompare — see FTA B3).
- **Preventive action:** `scripts/build_target.sh` fails on any project warning for the AVR build; verified with a negative control (re-introducing the bug makes it exit 1). Wired into CI.
- **Open item:** a runtime PIL check on hardware with a negative-altitude word is still needed to confirm the fixed decode on the actual device.

## CR-003 — Target-link protocol additions
- **Change:** TYPE `0x04 STEP` (payload `now_ms`, triggers one `aim_step`), `0x05 APPROACH_MODE`; per-step status line; ≥15 ms ADC2→STEP spacing requirement. New SYS-10 and HLR-FRM-01..04, with `framer.c`/`framer.h` and unit/integration tests.
- **Rationale:** the original three frame types provided no way to give `aim_step` its `now_ms` or `approach_mode`. Host-supplied time keeps PIL deterministic and consistent with HLR-TIM-01.
- **Impact:** ICD only; `src/` core untouched. Backward compatible (types 0x01–0x03 unchanged).

## CR-004 — Test additions
Added: ch2/ch1 staleness and fail-over, never-good ch2, re-convergence timer restart,
selected-altitude range boundaries, corrupted state byte, **re-divergence after clear
(mutant M13)**, deviation-band exact boundary (M26), alert-flag exclusivity (M32),
no-channels-means-invalid (M33), SDI test (HLR-DEC-02 previously covered only by a range tag).
M13 was a genuine verification gap: a stale `diverging` flag could cause an instant
re-latch after a clear, and no test would have noticed.

## CR-005 — Tooling
No effect on delivered code. `AIM_LIB`/`AIM_FRAMER_LIB` let the same tests run against the
coverage and mutant builds.
