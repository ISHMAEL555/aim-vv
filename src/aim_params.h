#ifndef AIM_PARAMS_H
#define AIM_PARAMS_H

/* Tunable thresholds. See docs/icd/ICD.md Section 5 and docs/safety/FHA.md
 * for the rationale behind each value. This header is the single source of
 * truth: do not duplicate these numbers elsewhere. */

#define AIM_MIN_ALT_FT              (-1000)
#define AIM_MAX_ALT_FT               50000

#define AIM_APPROACH_BAND_FT          1000
#define AIM_CAPTURE_BAND_FT            300
#define AIM_DEVIATION_BAND_FT          300
#define AIM_HYSTERESIS_FT               50
#define AIM_DEVIATION_PERSIST_MS       1000u

#define AIM_MISCOMPARE_THRESHOLD_FT     200
#define AIM_MISCOMPARE_PERSIST_MS      2000u

#define AIM_CHANNEL_STALE_MS            500u

#endif /* AIM_PARAMS_H */
