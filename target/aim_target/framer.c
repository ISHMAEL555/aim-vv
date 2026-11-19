#include "framer.h"

static uint8_t checksum_ok(const uint8_t *b)
{
    /* (TYPE + 4 payload bytes + CHECKSUM) mod 256 == 0 */
    uint8_t sum = 0u;
    uint8_t i;
    for (i = 1u; i < AIM_FRAME_LEN; i++) {
        sum = (uint8_t)(sum + b[i]);
    }
    return (uint8_t)(sum == 0u);
}

static uint8_t known_type(uint8_t t)
{
    return (uint8_t)(t >= AIM_FRAME_ADC1_WORD && t <= AIM_FRAME_APPROACH_MODE);
}

void aim_framer_init(aim_framer_t *f)
{
    f->n = 0u;
    f->rejected = 0u;
}

uint8_t aim_framer_push(aim_framer_t *f, uint8_t byte, aim_frame_t *out)
{
    uint8_t i;

    if (f->n == 0u) {
        if (byte == AIM_FRAME_SYNC) {
            f->buf[0] = byte;
            f->n = 1u;
        }
        return 0u;
    }

    f->buf[f->n] = byte;
    f->n++;
    if (f->n < AIM_FRAME_LEN) {
        return 0u;
    }

    /* A full 7-byte candidate is held. */
    if (checksum_ok(f->buf) && known_type(f->buf[1])) {
        out->type = f->buf[1];
        out->payload = (uint32_t)f->buf[2]
                     | ((uint32_t)f->buf[3] << 8)
                     | ((uint32_t)f->buf[4] << 16)
                     | ((uint32_t)f->buf[5] << 24);
        f->n = 0u;
        return 1u;
    }

    /* Reject: the SYNC byte was a false start. Drop it and re-scan the
     * remaining bytes, so a real frame that began inside the garbage is not
     * lost (the garbage may itself have contained a 0xAA). */
    if (f->rejected < 0xFFFFu) {
        f->rejected++;
    }
    {
        uint8_t tmp[AIM_FRAME_LEN - 1u];
        aim_frame_t unused;
        for (i = 0u; i < AIM_FRAME_LEN - 1u; i++) {
            tmp[i] = f->buf[i + 1u];
        }
        f->n = 0u;
        /* Only 6 bytes are re-fed, so no 7-byte frame can complete here and
         * no recursion beyond this level is possible; the result is ignored. */
        for (i = 0u; i < AIM_FRAME_LEN - 1u; i++) {
            (void)aim_framer_push(f, tmp[i], &unused);
        }
    }
    return 0u;
}
