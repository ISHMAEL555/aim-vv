#include "aim.h"
#include "decoder.h"
#include "monitor.h"
#include "alerter.h"

void aim_init(aim_t *aim)
{
    aim_monitor_init(&aim->monitor);
    aim_alerter_init(&aim->alerter);
}

void aim_step(aim_t *aim, uint32_t now_ms,
              uint32_t word_ch1, uint32_t word_ch2,
              int32_t selected_altitude_ft, uint8_t selected_altitude_valid,
              uint8_t approach_mode,
              aim_status_t *out)
{
    aim_decoded_word_t ch1, ch2;

    aim_decoder_decode(word_ch1, &ch1);
    aim_decoder_decode(word_ch2, &ch2);

    aim_monitor_update(&aim->monitor, now_ms, &ch1, &ch2, &out->monitor);

    out->altitude_valid = out->monitor.altitude_available;
    out->altitude_ft = out->monitor.reconciled_altitude_ft;

    aim_alerter_update(&aim->alerter, now_ms,
                        out->altitude_ft, out->altitude_valid,
                        selected_altitude_ft, selected_altitude_valid,
                        approach_mode,
                        &out->alerter);
}
