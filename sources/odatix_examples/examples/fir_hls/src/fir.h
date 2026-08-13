
#ifndef FIR_H
#define FIR_H

#include <ap_int.h>

// Number of taps of the filter.
//
// This is a *generation parameter*: it is not swept by editing this file, but
// by passing "-DTAPS=<n>" to the C++ front end from "run_hls.tcl", which gets
// the value from the "taps" variable of the architecture. The default below is
// only what a hand-run synthesis outside Odatix would use.
#ifndef TAPS
#define TAPS 16
#endif

typedef ap_int<16> data_t; // input samples and filter output
typedef ap_int<16> coef_t; // filter coefficients, Q1.15
typedef ap_int<40> acc_t;  // accumulator, wide enough for TAPS products

void fir(data_t sample, const coef_t coeffs[TAPS], data_t *out);

#endif // FIR_H
