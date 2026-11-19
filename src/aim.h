#ifndef AIM_H
#define AIM_H

#include "aim_types.h"

/* Top-level public API: decode both channels, run the monitor to reconcile
 * an altitude, then run the alerter against that altitude. This is the only
 * entry point the Phase 7 target firmware needs to call once per cycle. */

void aim_init(aim_t *aim);

void aim_step(aim_t *aim, uint32_t now_ms,
              uint32_t word_ch1, uint32_t word_ch2,
              int32_t selected_altitude_ft, uint8_t selected_altitude_valid,
              uint8_t approach_mode,
              aim_status_t *out);

#endif /* AIM_H */
