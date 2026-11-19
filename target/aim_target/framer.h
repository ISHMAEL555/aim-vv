#ifndef AIM_FRAMER_H
#define AIM_FRAMER_H

#include <stdint.h>

/* UART frame parser for the Phase 7 target link (docs/icd/ICD.md Section 3).
 * Pure C, no I/O: feed it one received byte at a time. */

#define AIM_FRAME_SYNC           0xAAu
#define AIM_FRAME_ADC1_WORD      0x01u
#define AIM_FRAME_SELECTED_ALT   0x02u
#define AIM_FRAME_ADC2_WORD      0x03u
#define AIM_FRAME_STEP           0x04u  /* payload = now_ms; runs one aim_step */
#define AIM_FRAME_APPROACH_MODE  0x05u  /* payload = 0 or 1 */
#define AIM_FRAME_LEN            7u     /* SYNC TYPE P0 P1 P2 P3 CHK */

typedef struct {
    uint8_t  buf[AIM_FRAME_LEN]; /* buf[0] is always SYNC while n > 0 */
    uint8_t  n;                  /* bytes held; 0 = hunting for SYNC */
    uint16_t rejected;           /* frames dropped for a bad checksum or unknown type (saturating) */
} aim_framer_t;

typedef struct {
    uint8_t  type;
    uint32_t payload;
} aim_frame_t;

void aim_framer_init(aim_framer_t *f);

/* Returns 1 and fills *out when this byte completed a valid frame, else 0. */
uint8_t aim_framer_push(aim_framer_t *f, uint8_t byte, aim_frame_t *out);

#endif /* AIM_FRAMER_H */
