
#include "fir.h"

// Direct-form FIR filter.
//
// One call consumes one sample and produces one output: the tap delay line is
// shifted, every tap is multiplied by its coefficient, and the products are
// accumulated.
//
// There is no "#pragma HLS" anywhere in this file, on purpose. Every directive
// this design is explored with is applied from "run_hls.tcl" instead (see
// "set_directive_*" there), so the same unmodified C++ is synthesized for
// every point of the design space and the sweep stays in the Odatix
// configuration rather than in the source.
void fir(data_t sample, const coef_t coeffs[TAPS], data_t *out) {
  static data_t shift_reg[TAPS];
  acc_t acc = 0;

mac_loop:
  for (int i = TAPS - 1; i >= 0; i--) {
    if (i == 0) {
      shift_reg[0] = sample;
    } else {
      shift_reg[i] = shift_reg[i - 1];
    }
    acc += (acc_t)shift_reg[i] * (acc_t)coeffs[i];
  }

  // Coefficients are Q1.15: bring the accumulator back to the input format.
  *out = (data_t)(acc >> 15);
}
