#include "decoder.h"

#define AIM_LABEL_203     0x83u
#define AIM_ALT_FIELD_BITS 18u
#define AIM_ALT_SIGN_BIT   (1u << (AIM_ALT_FIELD_BITS - 1u))   /* bit 17 of the field */
#define AIM_ALT_FIELD_MASK ((1u << AIM_ALT_FIELD_BITS) - 1u)   /* 18 ones */

static uint32_t count_ones(uint32_t v)
{
    uint32_t count = 0;
    while (v != 0u) {
        count += (v & 1u);
        v >>= 1u;
    }
    return count;
}

void aim_decoder_decode(uint32_t word, aim_decoded_word_t *out)
{
    uint8_t  label      = (uint8_t)(word & 0xFFu);
    uint8_t  sdi        = (uint8_t)((word >> 8) & 0x3u);
    uint32_t alt_field  = (word >> 10) & AIM_ALT_FIELD_MASK;
    uint8_t  ssm        = (uint8_t)((word >> 28) & 0x3u);
    uint8_t  parity_bit = (uint8_t)((word >> 31) & 0x1u);
    uint32_t ones_0_30  = count_ones(word & 0x7FFFFFFFu);
    uint8_t  parity_ok  = (uint8_t)(((ones_0_30 + parity_bit) % 2u) == 1u);
    int32_t  altitude_ft;

    if ((alt_field & AIM_ALT_SIGN_BIT) != 0u) {
        altitude_ft = (int32_t)alt_field - (int32_t)(AIM_ALT_FIELD_MASK + 1u);
    } else {
        altitude_ft = (int32_t)alt_field;
    }

    out->label       = label;
    out->sdi         = sdi;
    out->altitude_ft = altitude_ft;
    out->ssm         = ssm;
    out->parity_ok   = parity_ok;
    out->valid       = (uint8_t)((label == AIM_LABEL_203) && (parity_ok != 0u));
}
