# Interface Control Document — AIM (Altitude Indication Monitor)

## 1. Scope

This document defines the data formats and public API used by AIM:

1. The ARINC 429 label-203 altitude word format used by ADC-1 and ADC-2.
2. The UART framing used to carry those words (and the pilot-selected altitude)
   from the test laptop to the Arduino target in Phase 7.
3. The core C API (`src/aim.h` and friends) used by both the host unit/integration
   tests and the Phase 7 target firmware.
4. The parameter table of tunable thresholds.

The core library (`src/`) operates only on already-extracted 32-bit ARINC words
and plain integers — it never touches a UART or a clock. Time is always passed
in explicitly as `now_ms`, a caller-supplied monotonic millisecond counter, so
that the same code is deterministic on the host and on the target regardless of
call rate (see HLR-TIM-01/02).

## 2. ARINC 429 label-203 altitude word

This project uses a **simplified in-memory word format**: a plain `uint32_t`
with the fields below. It does **not** replicate the physical bit-reversed wire
order of a real ARINC 429 transceiver, because words never go over an actual
ARINC 429 bus here — they are carried as plain 4-byte payloads inside the UART
frames in §3. Bit 0 is the least significant bit of the `uint32_t`.

| Bits | Width | Field | Meaning |
|---|---|---|---|
| 0–7 | 8 | Label | Must equal `0203` octal (`0x83`, 131 decimal) for the word to be considered correctly labelled |
| 8–9 | 2 | SDI | Source identifier: `01` = ADC-1, `10` = ADC-2 (informational; the channel is actually determined by which link/frame type carried the word, not by SDI) |
| 10–27 | 18 | Altitude (BNR) | Two's-complement signed altitude, LSB = 1 ft, sign-extended to `int32_t` on decode. Operating range: `AIM_MIN_ALT_FT` (-1000 ft) to `AIM_MAX_ALT_FT` (+50000 ft) |
| 28–29 | 2 | SSM | Sign/Status Matrix, standard ARINC 429 BNR encoding: `00` = Failure Warning, `01` = No Computed Data, `10` = Functional Test, `11` = Normal Operation |
| 30 | 1 | Spare | Reserved, transmitted as 0, not checked by the decoder |
| 31 | 1 | Parity | Odd parity over bits 0–30 (total number of 1 bits in bits 0–31 is odd) |

### Worked example

Label = `0203` octal, SDI = `01` (ADC-1), SSM = `11` (Normal Operation),
altitude = **+10000 ft**:

```
word = 0x309C4183
```

Decoded:

| Field | Value |
|---|---|
| label | `0x83` (`0203` octal) |
| sdi | 1 |
| altitude_ft | +10000 |
| ssm | 3 (AIM_SSM_NORMAL_OPERATION) |
| parity_ok | true |
| valid | true |

This exact word/value pair is the canonical decoder test vector used in
`tests/vectors/decoder_vectors.json` and must decode correctly for Phase 2 to
be considered done.

## 3. UART framing (Phase 7 target link — informative for Phases 1–3)

Two independent serial links carry frames of the same shape:

```
Byte 0   SYNC       0xAA
Byte 1   TYPE        0x01 = ADC1_WORD, 0x02 = SELECTED_ALT, 0x03 = ADC2_WORD,
                     0x04 = STEP, 0x05 = APPROACH_MODE
Bytes 2-5 PAYLOAD    4 bytes, little-endian
Byte 6   CHECKSUM     8-bit two's-complement sum: (TYPE + PAYLOAD bytes + CHECKSUM) mod 256 == 0
```

- **Main link** (USB, 115200 baud): interleaves `ADC1_WORD` (payload = the
  `uint32_t` ARINC word from §2) and `SELECTED_ALT` (payload = `int32_t`
  selected altitude in ft; the reserved value `0x7FFFFFFF` means "no target /
  invalid").
  The main link also carries `APPROACH_MODE` (payload 0 or 1; `aim_step`'s
  `approach_mode` input, held until changed) and `STEP` (payload = `now_ms`;
  see below).
- **Secondary link** (CP2102 → UNO `SoftwareSerial` pin 10, 38400 baud): only
  `ADC2_WORD` frames, same payload shape as `ADC1_WORD`.

**Execution model (added in CR-003).** The firmware latches the most recent
`ADC1_WORD`, `ADC2_WORD`, `SELECTED_ALT` and `APPROACH_MODE` values and calls
`aim_step` exactly once per `STEP` frame, using the frame's payload as `now_ms`.
Time is therefore supplied by the test laptop, not read from `millis()`, which
keeps processor-in-the-loop runs deterministic and comparable cycle-by-cycle
with the host build (HLR-TIM-01). After each step the firmware prints one line:

```
S,now_ms,state,approaching,deviation,miscompare,alt_valid,altitude_ft,ch1_valid,ch2_valid,ch1_stale,ch2_stale,sel_valid,rejected
```

Frames failing sync/checksum or with an unknown TYPE are dropped and counted in
`rejected` (HLR-FRM-01..04). The harness must allow ~15 ms between an `ADC2_WORD`
frame and the following `STEP`, because the two links are independent and
`SoftwareSerial` reception at 38400 baud is asynchronous to the USB link.

Frame parsing is implemented in the Phase 7 target firmware (`target/`), not in
`src/`. The core API in §4 takes already-decoded values, independent of how
they arrived.

## 4. Core C API

Public types live in `src/aim_types.h`. All boolean-ish fields that cross the
C ABI are `uint8_t` (0/1), not `bool` or `enum`-sized types, so the layout is
unambiguous to both the C compiler and Python `ctypes`.

```c
/* decoder.h */
void aim_decoder_decode(uint32_t word, aim_decoded_word_t *out);

/* monitor.h */
void aim_monitor_init(aim_monitor_state_t *st);
void aim_monitor_update(aim_monitor_state_t *st, uint32_t now_ms,
                         const aim_decoded_word_t *ch1,
                         const aim_decoded_word_t *ch2,
                         aim_monitor_status_t *out);

/* alerter.h */
void aim_alerter_init(aim_alerter_state_t *st);
void aim_alerter_update(aim_alerter_state_t *st, uint32_t now_ms,
                         int32_t current_altitude_ft, uint8_t altitude_valid,
                         int32_t selected_altitude_ft, uint8_t selected_altitude_valid,
                         uint8_t approach_mode,
                         aim_alerter_status_t *out);

/* aim.h — top-level, used by host tests and the Phase 7 target */
void aim_init(aim_t *aim);
void aim_step(aim_t *aim, uint32_t now_ms,
              uint32_t word_ch1, uint32_t word_ch2,
              int32_t selected_altitude_ft, uint8_t selected_altitude_valid,
              uint8_t approach_mode,
              aim_status_t *out);
```

`aim_step` is the only function Phase 7 firmware needs to call once per cycle;
it decodes both channel words, runs the monitor, reconciles an altitude, and
runs the alerter against that reconciled altitude — all in one call.

## 5. Parameter table (`src/aim_params.h`)

| Parameter | Value | Meaning |
|---|---|---|
| `AIM_MIN_ALT_FT` | -1000 | Lower bound of a valid altitude/selected-altitude value |
| `AIM_MAX_ALT_FT` | 50000 | Upper bound of a valid altitude/selected-altitude value |
| `AIM_APPROACH_BAND_FT` | 1000 | CRUISE → APPROACHING threshold |
| `AIM_CAPTURE_BAND_FT` | 300 | APPROACHING → CAPTURED threshold |
| `AIM_DEVIATION_BAND_FT` | 300 | CAPTURED → (timing toward) DEVIATION threshold |
| `AIM_HYSTERESIS_FT` | 50 | Hysteresis subtracted/added at band edges to prevent chatter |
| `AIM_DEVIATION_PERSIST_MS` | 1000 | Deviation must persist this long (continuously) before alerting |
| `AIM_MISCOMPARE_THRESHOLD_FT` | 200 | ADC-1 vs ADC-2 difference threshold |
| `AIM_MISCOMPARE_PERSIST_MS` | 2000 | Miscompare must persist this long to latch, and tolerance must persist this long to clear |
| `AIM_CHANNEL_STALE_MS` | 500 | A channel with no good sample for this long is reported stale |

See [`docs/safety/FHA.md`](../safety/FHA.md) for the safety requirements these
parameters exist to satisfy.
