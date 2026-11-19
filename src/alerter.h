#ifndef AIM_ALERTER_H
#define AIM_ALERTER_H

#include "aim_types.h"

/* Approach/capture/deviation alert state machine. See docs/icd/ICD.md
 * Section 4 and the HLR-ALT-* requirements in reqs/hlr.sdoc for the exact
 * transition rules implemented here. */

void aim_alerter_init(aim_alerter_state_t *st);

void aim_alerter_update(aim_alerter_state_t *st, uint32_t now_ms,
                         int32_t current_altitude_ft, uint8_t altitude_valid,
                         int32_t selected_altitude_ft, uint8_t selected_altitude_valid,
                         uint8_t approach_mode,
                         aim_alerter_status_t *out);

#endif /* AIM_ALERTER_H */
