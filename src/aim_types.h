#ifndef AIM_TYPES_H
#define AIM_TYPES_H

#include <stdint.h>

/* Public ABI types. Boolean-ish fields are uint8_t (0/1), not bool or a
 * compiler-sized enum, so the struct layout is unambiguous to both the C
 * compiler and Python ctypes (see docs/icd/ICD.md Section 4). */

typedef enum {
    AIM_SSM_FAILURE_WARNING  = 0,
    AIM_SSM_NO_COMPUTED_DATA = 1,
    AIM_SSM_FUNCTIONAL_TEST  = 2,
    AIM_SSM_NORMAL_OPERATION = 3
} aim_ssm_t;

typedef struct {
    uint8_t  valid;        /* label correct AND parity ok (independent of SSM) */
    uint8_t  parity_ok;
    uint8_t  label;
    uint8_t  sdi;
    uint8_t  ssm;          /* aim_ssm_t */
    int32_t  altitude_ft;
} aim_decoded_word_t;

typedef enum {
    AIM_ALERT_CRUISE      = 0,
    AIM_ALERT_APPROACHING = 1,
    AIM_ALERT_CAPTURED    = 2,
    AIM_ALERT_DEVIATION   = 3
} aim_alert_state_t;

typedef struct {
    uint32_t last_good_ms_ch1;
    uint32_t last_good_ms_ch2;
    uint8_t  have_ch1_ever;
    uint8_t  have_ch2_ever;
    uint32_t diverge_since_ms;   /* meaningful only while diverging == 1; now_ms==0 is a valid start time */
    uint8_t  diverging;
    uint32_t converge_since_ms;  /* meaningful only while converging == 1 */
    uint8_t  converging;
    uint8_t  miscompare_latched;
} aim_monitor_state_t;

typedef struct {
    uint8_t ch1_valid;
    uint8_t ch2_valid;
    uint8_t ch1_stale;
    uint8_t ch2_stale;
    uint8_t miscompare;
    uint8_t altitude_available;
    int32_t reconciled_altitude_ft;
} aim_monitor_status_t;

typedef struct {
    uint8_t  state;                   /* aim_alert_state_t */
    uint32_t deviation_since_ms;      /* meaningful only while deviating == 1; now_ms==0 is a valid start time */
    uint8_t  deviating;
    int32_t  selected_altitude_ft;    /* last valid selected altitude, held across invalid inputs */
    uint8_t  have_selected_ever;
} aim_alerter_state_t;

typedef struct {
    uint8_t state;                    /* aim_alert_state_t */
    uint8_t alert_approaching;
    uint8_t alert_deviation;
    uint8_t selected_altitude_valid;
} aim_alerter_status_t;

typedef struct {
    aim_monitor_state_t monitor;
    aim_alerter_state_t alerter;
} aim_t;

typedef struct {
    aim_monitor_status_t monitor;
    aim_alerter_status_t alerter;
    int32_t altitude_ft;
    uint8_t altitude_valid;
} aim_status_t;

#endif /* AIM_TYPES_H */
