# Verification Summary

Evidence below was produced on the working tree following baseline `bbf3f86`
(changes in [CHANGE_LOG.md](CHANGE_LOG.md); not yet committed when written, so it is
bound to that baseline plus those changes, not to a single commit).

| Objective | Result | How to reproduce |
|---|---|---|
| Tests | **237 pass** (unit, integration, framer, PIL-sim, back-to-back) | `.venv/bin/python -m pytest tests` |
| Structural coverage | **100 %** line and branch (203 lines, 83+ branches) on `src/*.c` and `framer.c` | `scripts/check.sh` |
| Strict warnings / static analysis | clean: `-Wall -Wextra -Werror -Wconversion -Wshadow -pedantic`, `gcc -fanalyzer` | `scripts/check.sh` |
| Requirements traceability | 10 SYS, 28 HLR, **0 gaps** ([matrix](../trace/TRACEABILITY.md)) | `scripts/trace.py --check` |
| Test adequacy | **39/39 seeded defects killed** ([report](../verification/SEEDED_DEFECTS.md)) | `scripts/mutate.py` |
| Independent model | 150 random seeds × 400 cycles identical to the C code, incl. 32-bit time wrap | `tests/integration/test_back_to_back.py` |
| AVR build | compiles clean for UNO: 5.7 KB flash (17 %), 371 B RAM (18 %) | `scripts/build_target.sh` |
| PIL, simulated target | 4/4 scenarios match host lockstep ([report](../verification/PIL_RESULTS.md)) | `scripts/pil.py --sim` |
| **PIL, real hardware** | **NOT RUN** — no Arduino was attached | `scripts/pil.py --port … --adc2 …` |

## Findings during verification
1. **CR-002 — real defect.** 16-bit `int` shift overflow in the decoder, invisible on the host,
   found by the first AVR compile.
2. **Mutant M13 — real test gap.** Stale divergence state could re-latch instantly after a clear.
3. **CR-001 — dead code.** Redundant `!stale` conditions removed.
4. **FTA residual risks** A3 (intermittent dropouts postpone latch) and C2 (no state integrity
   in monitor) are documented, not fixed.

## Limitations — read before relying on this
- **Hardware PIL has not been executed.** The firmware only *compiles*. The `--sim` mode
  validates the harness and protocol using the host C code; it says nothing about AVR runtime
  behaviour. Run the rig before calling Phase 7 complete.
- **Known rig risk:** `SoftwareSerial` RX at 38400 baud disables interrupts for ~260 µs per byte,
  while the hardware UART receives a byte every ~87 µs at 115200 baud. Bytes on the USB link may be
  dropped during ADC-2 reception. The framer rejects corrupt frames (visible in the `rejected`
  field), and the harness spaces frames, but loss is possible; if the rig shows `rejected > 0`,
  lower the USB baud rate or pace writes.
- **Coverage is statement/decision (100 %), not MC/DC.** DAL B nominally calls for MC/DC.
  The one compound condition (`valid && ssm == NORMAL`, label+parity) is exercised by tests
  for each term independently, but MC/DC was not measured.
- **Phase 10:** MATLAB/Stateflow was not available. The Python model is a behavioural stand-in
  written from the HLR text; it is not a Stateflow model and offers no model-coverage or
  code-generation evidence. It shares the HLR author's reading of the requirements, so it cannot
  detect a requirement that is itself wrong.
- Mutation operators are hand-picked (39), not exhaustive.
- Single engineer: no independent review. Tooling stands in for independence.
- cppcheck/clang-tidy unavailable; static analysis is gcc-only.
