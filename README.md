# AIM-VV — Altitude Indication Monitor: Verification & Validation

A requirements-based verification and validation exercise for a small avionics-style
function: a **PFD altitude alerting and cross-side miscompare monitor** ("AIM"),
developed and verified following an ARP4754B/4761A-style process (requirements,
hazard analysis, design, test, coverage, traceability — scaled down for a
single-engineer, single-board exercise).

## What AIM does

AIM ingests ARINC 429 label-203 altitude words from two independent air data
channels (ADC-1, ADC-2) plus a pilot-selected target altitude, and produces:

- **Altitude alerting** — an "approaching altitude" indication and, if a captured
  altitude is subsequently departed for too long, a "deviation" alert (suppressed
  in approach mode).
- **Cross-side monitoring** — a latched miscompare flag when the two ADC channels
  disagree by more than a threshold for longer than a persistence time, plus
  per-channel staleness detection and automatic fail-over to the remaining valid
  channel.

See [`docs/icd/ICD.md`](docs/icd/ICD.md) for the exact bit layout, parameter
values and public API, and [`docs/safety/FHA.md`](docs/safety/FHA.md) for the
hazard analysis that drives the safety requirements.

## Rig

- **Test station:** laptop.
- **Device under test:** Arduino UNO.
- **Secondary serial link:** CP2102 USB-UART bridge (feeds ADC-2 to the UNO over
  `SoftwareSerial` on pin 10 at 38400 baud, independent of the main USB link at
  115200 baud used for ADC-1 and the selected altitude).

The core logic in `src/` has no hardware dependency and builds/tests entirely on
the laptop; the Arduino only matters from Phase 7 onward (processor-in-the-loop).

## Repository layout

```
docs/
  safety/FHA.md        Functional Hazard Assessment: failure conditions, DAL, derived safety reqs
  icd/ICD.md            Interface Control Document: bit layout, SSM, UART framing, API, parameters
reqs/
  system.sdoc            System requirements (SYS-*)
  hlr.sdoc                High-level requirements (HLR-*), tagged by category
src/
  aim_params.h            Compile-time thresholds (the single source of truth for tunables)
  aim_types.h              Public types/structs (the C ABI)
  decoder.{h,c}            ARINC 429 label-203 word decode
  monitor.{h,c}             Cross-side miscompare + staleness monitor
  alerter.{h,c}              Approach/capture/deviation state machine
  aim.{h,c}                   Top-level public API tying the above together
tests/
  vectors/                  Shared JSON test vectors (decoder worked examples)
  unit/                     pytest + ctypes unit tests, one file per module, tagged by HLR ID
  integration/              Scenario tests through the public API, tagged by SYS ID
CMakeLists.txt               Builds libaim as a shared library for ctypes
```

## Status

| Phase | Status |
|---|---|
| 0 — Foundation | done |
| 1 — C core | done |
| 2 — Unit tests | done |
| 3 — Integration tests | done |
| 4 — Coverage, static analysis, CI | not started |
| 5 — Traceability | not started |
| 6 — Seeded defects | not started |
| 7 — Processor-in-the-loop | not started |
| 8 — Process documents | not started |
| 9 — Change control | not started |
| 10 — Stateflow model | not started |

## Build & test

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build

python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
```

The library builds with `-Wall -Wextra -Werror`, no dynamic memory, fixed-width
types only, and takes time as an explicit `now_ms` parameter rather than reading
a clock — see `docs/icd/ICD.md` for why.
