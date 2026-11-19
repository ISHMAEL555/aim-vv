# Functional Hazard Assessment — AIM (Altitude Indication Monitor)

Scope: the PFD altitude alerting and cross-side miscompare monitor function
described in the [ICD](../icd/ICD.md). This FHA is scaled for a single-function,
single-engineer exercise; it is not a complete aircraft-level FHA.

DAL scale used: **A** (Catastrophic) > **B** (Hazardous) > **C** (Major) >
**D** (Minor) > **E** (No Safety Effect), per ARP4761A severity classes.

## Failure conditions

| ID | Failure condition | Effect | Severity | DAL |
|---|---|---|---|---|
| FC-01 | Loss of altitude alerting function (no approaching/deviation alert when one is due) | Crew loses an awareness cue during level-off or a sustained deviation; other cues (altitude tape, ATC) remain available | Major | C |
| FC-02 | Nuisance approaching/deviation alert (alert when none is due) | Increased crew workload, possible momentary distraction; no erroneous action likely | Minor | D |
| FC-03 | Undetected cross-side altitude miscompare (ADC-1 and ADC-2 disagree and the monitor fails to flag it) | Crew or downstream function may use erroneous altitude data believing it to be cross-checked, with no annunciation of the disagreement | Hazardous | B |
| FC-04 | Erroneous miscompare annunciation (flagged when channels actually agree) | Increased workload, possible unnecessary channel distrust/switching | Minor | D |
| FC-05 | Alert fails to clear, or clears incorrectly, during a critical flight phase (e.g. approach) | Spurious/stuck alert during a high-workload phase compounds crew workload at the worst time | Major | C |
| FC-06 | Loss of stale-channel detection (a frozen/stuck ADC channel continues to be used as if valid) | Altitude data used for alerting and comparison may be frozen without the crew or the monitor being aware | Hazardous | B |

## Derived safety requirements

These are allocated to the system requirements in [`reqs/system.sdoc`](../../reqs/system.sdoc)
and implemented by the monitor/alerter logic in [`src/`](../../src/).

- **SR-1** (addresses FC-03): the monitor shall detect and latch a cross-side
  altitude miscompare within `AIM_MISCOMPARE_PERSIST_MS` of the inter-channel
  difference exceeding `AIM_MISCOMPARE_THRESHOLD_FT`, and shall not clear the
  latch until the difference has stayed within tolerance for the same
  persistence time.
- **SR-2** (addresses FC-06): the monitor shall detect a channel as stale within
  `AIM_CHANNEL_STALE_MS` of its last valid (SSM = Normal Operation, parity-ok,
  correctly labelled) sample, and shall exclude a stale channel's data from the
  reconciled altitude used for alerting and comparison.
- **SR-3** (addresses FC-02, FC-04, FC-05): the alerter shall not assert a
  deviation alert unless the deviation has persisted continuously for at least
  `AIM_DEVIATION_PERSIST_MS`, and shall not assert a deviation alert at all
  while approach mode is active, bounding nuisance/stuck alerts during a
  critical flight phase.
- **SR-4** (addresses FC-01, FC-06): loss or staleness of a single ADC channel
  shall not cause loss of the altitude alerting function; the system shall
  automatically continue alerting from the remaining valid channel.

## Notes

- FC-03 is the subject of the fault tree analysis planned for Phase 8
  (`docs/safety/FTA.md`), as it is the highest-severity failure condition with
  the least obvious single root cause (it requires simultaneous loss of two
  independent pieces of evidence: the per-channel SSM/parity checks and the
  cross-side comparison itself).
- No failure condition above DAL B (Hazardous) was identified for this function,
  consistent with it being an advisory/awareness function with independent
  crew cross-check available (raw altitude tape, ATC) rather than a function
  whose sole failure can directly cause a catastrophic outcome.
