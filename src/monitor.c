#include "monitor.h"
#include "aim_params.h"

/* int32_t, not plain int: on an 8-bit AVR target, int is 16 bits and would
 * silently truncate an altitude difference. */
static int32_t abs_diff_i32(int32_t a, int32_t b)
{
    int32_t d = a - b;
    return (d < 0) ? -d : d;
}

static uint8_t is_good(const aim_decoded_word_t *w)
{
    return (uint8_t)(w->valid && (w->ssm == (uint8_t)AIM_SSM_NORMAL_OPERATION));
}

void aim_monitor_init(aim_monitor_state_t *st)
{
    st->last_good_ms_ch1  = 0u;
    st->last_good_ms_ch2  = 0u;
    st->have_ch1_ever     = 0u;
    st->have_ch2_ever     = 0u;
    st->diverge_since_ms  = 0u;
    st->diverging         = 0u;
    st->converge_since_ms = 0u;
    st->converging        = 0u;
    st->miscompare_latched = 0u;
}

void aim_monitor_update(aim_monitor_state_t *st, uint32_t now_ms,
                         const aim_decoded_word_t *ch1,
                         const aim_decoded_word_t *ch2,
                         aim_monitor_status_t *out)
{
    uint8_t ch1_good = is_good(ch1);
    uint8_t ch2_good = is_good(ch2);
    uint8_t ch1_stale, ch2_stale, both_usable;

    /* A channel that is good this cycle has last_good_ms == now_ms, so it can
     * never also be stale; "usable" therefore reduces to "good". (An explicit
     * !stale term would be an unreachable branch.) */

    if (ch1_good) {
        st->last_good_ms_ch1 = now_ms;
        st->have_ch1_ever = 1u;
    }
    if (ch2_good) {
        st->last_good_ms_ch2 = now_ms;
        st->have_ch2_ever = 1u;
    }

    ch1_stale = (uint8_t)(st->have_ch1_ever &&
                           ((uint32_t)(now_ms - st->last_good_ms_ch1) > AIM_CHANNEL_STALE_MS));
    ch2_stale = (uint8_t)(st->have_ch2_ever &&
                           ((uint32_t)(now_ms - st->last_good_ms_ch2) > AIM_CHANNEL_STALE_MS));

    out->ch1_valid = ch1_good;
    out->ch2_valid = ch2_good;
    out->ch1_stale = ch1_stale;
    out->ch2_stale = ch2_stale;

    both_usable = (uint8_t)(ch1_good && ch2_good);

    if (both_usable) {
        int32_t diff = abs_diff_i32(ch1->altitude_ft, ch2->altitude_ft);

        if (!st->miscompare_latched) {
            if (diff > AIM_MISCOMPARE_THRESHOLD_FT) {
                if (!st->diverging) {
                    st->diverging = 1u;
                    st->diverge_since_ms = now_ms;
                } else if ((uint32_t)(now_ms - st->diverge_since_ms) >= AIM_MISCOMPARE_PERSIST_MS) {
                    st->miscompare_latched = 1u;
                    st->diverging = 0u;
                }
            } else {
                st->diverging = 0u;
            }
        } else {
            if (diff <= AIM_MISCOMPARE_THRESHOLD_FT) {
                if (!st->converging) {
                    st->converging = 1u;
                    st->converge_since_ms = now_ms;
                } else if ((uint32_t)(now_ms - st->converge_since_ms) >= AIM_MISCOMPARE_PERSIST_MS) {
                    st->miscompare_latched = 0u;
                    st->converging = 0u;
                }
            } else {
                st->converging = 0u;
            }
        }
    }
    /* else: either channel unusable -- freeze both timers (HLR-MON-05) */

    out->miscompare = st->miscompare_latched;

    if (ch1_good) {
        out->altitude_available = 1u;
        out->reconciled_altitude_ft = ch1->altitude_ft;
    } else if (ch2_good) {
        out->altitude_available = 1u;
        out->reconciled_altitude_ft = ch2->altitude_ft;
    } else {
        out->altitude_available = 0u;
        out->reconciled_altitude_ft = 0;
    }
}
