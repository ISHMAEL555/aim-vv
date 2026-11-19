#include "alerter.h"
#include "aim_params.h"

static int32_t abs_diff_i32(int32_t a, int32_t b)
{
    int32_t d = a - b;
    return (d < 0) ? -d : d;
}

static uint8_t selected_in_range(int32_t alt)
{
    return (uint8_t)(alt >= AIM_MIN_ALT_FT && alt <= AIM_MAX_ALT_FT);
}

void aim_alerter_init(aim_alerter_state_t *st)
{
    st->state = (uint8_t)AIM_ALERT_CRUISE;
    st->deviation_since_ms = 0u;
    st->deviating = 0u;
    st->selected_altitude_ft = 0;
    st->have_selected_ever = 0u;
}

void aim_alerter_update(aim_alerter_state_t *st, uint32_t now_ms,
                         int32_t current_altitude_ft, uint8_t altitude_valid,
                         int32_t selected_altitude_ft, uint8_t selected_altitude_valid,
                         uint8_t approach_mode,
                         aim_alerter_status_t *out)
{
    int32_t err;

    /* HLR-ALT-01: hold last-valid selected altitude; reject out-of-range input. */
    if (selected_altitude_valid && selected_in_range(selected_altitude_ft)) {
        st->selected_altitude_ft = selected_altitude_ft;
        st->have_selected_ever = 1u;
    }

    out->selected_altitude_valid = st->have_selected_ever;

    /* HLR-ALT-02 / HLR-ALT-03: no target yet, or altitude unknown -> fail safe to CRUISE. */
    if (!altitude_valid || !st->have_selected_ever) {
        st->state = (uint8_t)AIM_ALERT_CRUISE;
        st->deviation_since_ms = 0u;
        st->deviating = 0u;
        out->state = st->state;
        out->alert_approaching = 0u;
        out->alert_deviation = 0u;
        return;
    }

    err = abs_diff_i32(current_altitude_ft, st->selected_altitude_ft);

    switch ((aim_alert_state_t)st->state) {
    case AIM_ALERT_CRUISE:
        if (err <= AIM_APPROACH_BAND_FT) {
            st->state = (uint8_t)AIM_ALERT_APPROACHING;
        }
        break;

    case AIM_ALERT_APPROACHING:
        if (err <= AIM_CAPTURE_BAND_FT) {
            st->state = (uint8_t)AIM_ALERT_CAPTURED;
            st->deviation_since_ms = 0u;
            st->deviating = 0u;
        } else if (err > AIM_APPROACH_BAND_FT + AIM_HYSTERESIS_FT) {
            st->state = (uint8_t)AIM_ALERT_CRUISE;
        }
        break;

    case AIM_ALERT_CAPTURED:
        if (err > AIM_DEVIATION_BAND_FT) {
            if (!st->deviating) {
                st->deviating = 1u;
                st->deviation_since_ms = now_ms;
            } else if (!approach_mode &&
                       (uint32_t)(now_ms - st->deviation_since_ms) >= AIM_DEVIATION_PERSIST_MS) {
                st->state = (uint8_t)AIM_ALERT_DEVIATION;
            }
        } else {
            st->deviation_since_ms = 0u;
            st->deviating = 0u;
        }
        break;

    case AIM_ALERT_DEVIATION:
        if (approach_mode) {
            /* HLR-ALT-09: approach mode forces an immediate downgrade and a
             * fresh persistence interval before it can alert again. */
            st->state = (uint8_t)AIM_ALERT_CAPTURED;
            st->deviating = 1u;
            st->deviation_since_ms = now_ms;
        } else if (err <= AIM_DEVIATION_BAND_FT - AIM_HYSTERESIS_FT) {
            st->state = (uint8_t)AIM_ALERT_CAPTURED;
            st->deviation_since_ms = 0u;
            st->deviating = 0u;
        }
        break;

    default:
        st->state = (uint8_t)AIM_ALERT_CRUISE;
        break;
    }

    out->state = st->state;
    out->alert_approaching = (uint8_t)(st->state == (uint8_t)AIM_ALERT_APPROACHING);
    out->alert_deviation   = (uint8_t)(st->state == (uint8_t)AIM_ALERT_DEVIATION);
}
