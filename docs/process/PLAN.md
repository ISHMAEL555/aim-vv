# Development & Verification Plan — AIM

Scaled-down analogue of a PSAC/SDP/SVP (ARP4754B / ARP4761A / DO-178C-style) for a
single-engineer, single-function exercise. It states what was planned; results are in
[VERIFICATION_SUMMARY.md](VERIFICATION_SUMMARY.md).

## 1. Function, assurance level
AIM (altitude alerting + cross-side miscompare monitor). Highest failure condition
FC-03/FC-06, **DAL B** (see [FHA](../safety/FHA.md), [FTA](../safety/FTA.md)). Verification
objectives are therefore set at a DAL-B-like level: requirements-based tests, structural
coverage to **decision (branch) level**, and independence evidence where practical.
(Full DAL B would also require MC/DC; see limitations in the summary.)

## 2. Lifecycle and outputs
| Phase | Output |
|---|---|
| 0 Foundation | FHA, ICD, system and high-level requirements (`reqs/*.sdoc`) |
| 1 C core | `src/` — C99, no dynamic memory, fixed-width types, explicit time |
| 2–3 Tests | Unit tests per HLR, integration tests per SYS requirement |
| 4 Coverage, static analysis, CI | `scripts/check.sh`, `.github/workflows/ci.yml` |
| 5 Traceability | `scripts/trace.py` → `docs/trace/TRACEABILITY.md` |
| 6 Seeded defects | `scripts/mutate.py` → `docs/verification/SEEDED_DEFECTS.md` |
| 7 PIL | `target/aim_target/` firmware, `scripts/pil.py`, `scripts/build_target.sh` |
| 8 Process | this plan, FTA, verification summary |
| 9 Change control | [CHANGE_LOG.md](CHANGE_LOG.md) |
| 10 Model | `tests/model/aim_model.py` (Python substitute for Stateflow) |

## 3. Standards and constraints
C99; `-Wall -Wextra -Werror`; extra strict build (`-Wconversion -Wshadow -pedantic …`);
`gcc -fanalyzer`; no dynamic allocation; all timing via caller-supplied `now_ms`;
integer types sized explicitly because the target (AVR) has 16-bit `int`.

## 4. Verification strategy
1. **Requirements-based tests.** Each test docstring cites the requirement it verifies;
   every HLR needs ≥1 unit test and every SYS requirement ≥1 integration test (enforced by
   `trace.py --check`).
2. **Structural coverage.** 100 % line and branch on `src/*.c` and the framer, enforced by
   `scripts/check.sh`. Unreachable branches are removed (not waived) and the removal justified
   in the change log.
3. **Robustness / fault injection.** Boundary ±1 tests, invalid SSM/label/parity, dropout,
   out-of-range selected altitude, corrupted state, corrupted UART frames, fuzzed framer.
4. **Test adequacy.** Seeded-defect campaign: every mutant must be killed.
5. **Independent oracle.** Python reference encoder (word layout) and Python behavioural
   model (whole function), both written from requirements, compared against C back-to-back
   on randomised stimulus incl. 32-bit time wraparound.
6. **Target.** Firmware must compile for the UNO with no warnings from project code; PIL
   compares the target cycle-by-cycle with the host build.

## 5. Entry/exit criteria
Exit requires: all tests pass; coverage gate passes; trace gap list empty; 0 surviving
mutants; target build clean; PIL passes on hardware. Any change after baseline follows
[CHANGE_LOG.md](CHANGE_LOG.md): record, impact analysis, full regression.

## 6. Roles
Single engineer; independence is approximated by tooling (oracles, mutation) rather than a
separate reviewer. This is a known deviation from DAL-B independence objectives.
