/*
 * tone_generator.h
 *
 * Adapted from minimodem simple-tone-generator.c
 * Original Copyright (C) 2011-2020 Kamal Mostafa <kamal@whence.com>
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef TONE_GENERATOR_H
#define TONE_GENERATOR_H

#include <stddef.h>

/* Initialize sine lookup table. Call once at startup.
 * sin_table_len: LUT size (0 = use sinf() directly, 4096 = typical)
 * mag: amplitude 0.0-1.0 */
void tone_generator_init(unsigned int sin_table_len, float mag);

/* Generate tone samples into a float buffer.
 * buf: output buffer (float32, -1.0 to 1.0)
 * tone_freq: frequency in Hz (0.0 = silence)
 * nsamples: number of samples to generate
 * sample_rate: audio sample rate in Hz
 * Returns: number of samples written (== nsamples) */
size_t tone_generate(float *buf, float tone_freq, size_t nsamples, float sample_rate);

/* Reset phase accumulator (call between independent transmissions) */
void tone_reset_phase(void);

#endif /* TONE_GENERATOR_H */
