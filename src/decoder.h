#ifndef AIM_DECODER_H
#define AIM_DECODER_H

#include "aim_types.h"

/* Decodes a 32-bit ARINC 429 label-203 altitude word per docs/icd/ICD.md
 * Section 2. Always populates every field of *out; out->valid summarizes
 * label-correctness and parity only (HLR-DEC-06) -- SSM is reported
 * separately so callers can distinguish e.g. a correctly-labelled,
 * parity-ok word flagged No Computed Data from a structurally bad word. */
void aim_decoder_decode(uint32_t word, aim_decoded_word_t *out);

#endif /* AIM_DECODER_H */
