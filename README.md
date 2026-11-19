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

- **Device under test:** Arduino UNO, USB-connected (`/dev/ttyACM0`), 115200 baud:
  carries ADC-1, the selected altitude, approach mode and step commands.
- **Test station:** a laptop **or a Raspberry Pi 4**. It runs `scripts/pil.py`.
- **Secondary link (ADC-2):** 38400 baud into UNO pin 10 (`SoftwareSerial`), independent of
  the USB link. Any one of these works as the source:

| Source | Connection | `--adc2` argument |
|---|---|---|
| Pi 4 hardware UART | Pi pin 8 (GPIO14 TXD) to UNO pin 10; Pi pin 6 (GND) to UNO GND | `/dev/serial0` |
| USB-serial adapter (CP2102, FT232, CH340) | adapter TXD to UNO pin 10; GND to GND | `/dev/ttyUSB0` |
| Arduino Nano as adapter (empty sketch uploaded) | Nano RX0 to UNO pin 10; GND to GND | `/dev/ttyUSB0` |

Do not connect the UNO's TX or any 5 V pin to a 3.3 V device (Pi, CP2102). Nothing here needs
an analog-to-digital converter: ADC-1/ADC-2 are *air data computers*, simulated in software
by the test station.

**Raspberry Pi 4 one-time setup:** `sudo raspi-config` > Interface Options > Serial Port:
login shell **No**, serial hardware **Yes**; add `dtoverlay=disable-bt` to
`/boot/firmware/config.txt`; reboot. `/dev/serial0` should then exist.
**WSL2 laptops** need `usbipd-win` to attach USB devices.

The core logic in `src/` has no hardware dependency and builds/tests entirely on
the laptop; the Arduino only matters for Phase 7 (processor-in-the-loop) (processor-in-the-loop).

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
  model/                    Independent Python reference model (Phase 10 substitute)
target/aim_target/          Arduino UNO firmware (.ino) + UART frame parser (framer.c)
scripts/                    check.sh (coverage/static analysis), trace.py, mutate.py,
                            build_target.sh (AVR build), pil.py (processor-in-the-loop)
CMakeLists.txt               Builds libaim as a shared library for ctypes
```

## Status

| Phase | Status |
|---|---|
| 0 — Foundation | done |
| 1 — C core | done |
| 2 — Unit tests | done |
| 3 — Integration tests | done |
| 4 — Coverage, static analysis, CI | done (100 % line/branch, `scripts/check.sh`, CI) |
| 5 — Traceability | done (`scripts/trace.py`, [matrix](docs/trace/TRACEABILITY.md)) |
| 6 — Seeded defects | done (39/39 killed, [report](docs/verification/SEEDED_DEFECTS.md)) |
| 7 — Processor-in-the-loop | firmware + harness done and compiling for UNO; **hardware run pending** (none attached) |
| 8 — Process documents | done ([plan](docs/process/PLAN.md), [FTA](docs/safety/FTA.md), [summary](docs/process/VERIFICATION_SUMMARY.md)) |
| 9 — Change control | done ([log](docs/process/CHANGE_LOG.md)) |
| 10 — Stateflow model | Python reference model back-to-back instead (no MATLAB available) |

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

## Full verification

```bash
scripts/check.sh                 # strict build, analyzer, tests, 100% coverage gate
.venv/bin/python scripts/trace.py --check
.venv/bin/python scripts/mutate.py
scripts/build_target.sh          # needs arduino-cli + arduino:avr core
.venv/bin/python scripts/pil.py --sim                                  # no hardware
.venv/bin/pip install pyserial
.venv/bin/python scripts/pil.py --port /dev/ttyACM0 --adc2 /dev/serial0 --report   # real rig (see Rig table for --adc2)
```
