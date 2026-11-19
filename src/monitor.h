#ifndef AIM_MONITOR_H
#define AIM_MONITOR_H

#include "aim_types.h"

/* Cross-side miscompare and staleness monitor. See docs/icd/ICD.md Section 4
 * and docs/safety/FHA.md (SR-1, SR-2, SR-4) for the behaviour this implements. */

void aim_monitor_init(aim_monitor_state_t *st);

void aim_monitor_update(aim_monitor_state_t *st, uint32_t now_ms,
                         const aim_decoded_word_t *ch1,
                         const aim_decoded_word_t *ch2,
                         aim_monitor_status_t *out);

#endif /* AIM_MONITOR_H */
