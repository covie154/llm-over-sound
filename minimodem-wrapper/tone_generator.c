/*
 * tone_generator.c
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

#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>

#include "tone_generator.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static float tone_mag = 1.0;

static unsigned int sin_table_len_g;
static float *sin_table_float;

void
tone_generator_init( unsigned int new_sin_table_len, float mag )
{
    sin_table_len_g = new_sin_table_len;
    tone_mag = mag;

    if ( tone_mag > 1.0f )
	tone_mag = 1.0f;
    if ( tone_mag < 0.0f )
	tone_mag = 0.0f;

    if ( sin_table_len_g != 0 ) {
	sin_table_float = realloc(sin_table_float,
				  sin_table_len_g * sizeof(float));
	if ( !sin_table_float ) {
	    perror("malloc");
	    assert(0);
	}

	unsigned int i;
	for ( i=0; i<sin_table_len_g; i++ )
	    sin_table_float[i] = tone_mag
		* sinf((float)M_PI * 2.0f * i / sin_table_len_g);

    } else {
	if ( sin_table_float ) {
	    free(sin_table_float);
	    sin_table_float = NULL;
	}
    }
}


/*
 * in: turns (0.0 to 1.0)    out: -1.0 to +1.0
 */
static inline float
sin_lu_float( float turns )
{
    int t = (float)sin_table_len_g * turns + 0.5f;
    t %= sin_table_len_g;
    return sin_table_float[t];
}


/* "current" phase state of the tone generator */
static float sa_tone_cphase = 0.0;

void
tone_reset_phase( void )
{
    sa_tone_cphase = 0.0;
}

size_t
tone_generate( float *buf, float tone_freq, size_t nsamples, float sample_rate )
{
    if ( tone_freq != 0.0f ) {

	float wave_nsamples = sample_rate / tone_freq;
	size_t i;

#define TURNS_TO_RADIANS(t)	( (float)M_PI * 2.0f * (t) )

#define SINE_PHASE_TURNS	( (float)i / wave_nsamples + sa_tone_cphase )
#define SINE_PHASE_RADIANS	TURNS_TO_RADIANS(SINE_PHASE_TURNS)

	if ( sin_table_float ) {
	    for ( i=0; i<nsamples; i++ )
		buf[i] = sin_lu_float(SINE_PHASE_TURNS);
	} else {
	    for ( i=0; i<nsamples; i++ )
		buf[i] = tone_mag * sinf(SINE_PHASE_RADIANS);
	}

	sa_tone_cphase
	    = fmodf(sa_tone_cphase + (float)nsamples / wave_nsamples, 1.0f);

    } else {

	memset(buf, 0, nsamples * sizeof(float));
	sa_tone_cphase = 0.0;

    }

    return nsamples;
}
