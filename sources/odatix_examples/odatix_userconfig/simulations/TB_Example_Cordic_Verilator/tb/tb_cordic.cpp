// **********************************************************************
//                                Odatix
// **********************************************************************
//
// Testbench for the pipelined CORDIC rotation core.
//
// The design is fed with one vector per clock cycle, covering the whole
// [-180 deg, +180 deg[ angle range. Each output is compared against a double
// precision reference, and the testbench derives accuracy figures (error in
// LSB, angular error, SNR, effective number of bits) as well as timing figures
// (latency, throughput, host runtime).
//
// Those figures are written to "results.yml" so that Odatix can collect them
// as metrics (see _metrics.yml of this simulation).
//
// CFG_WIDTH and CFG_ITERATIONS are passed by the Makefile, which reads them
// back from the parameters of the RTL file configured by Odatix.

#include <verilated.h>
#include <verilated_vcd_c.h>
#include <getopt.h>
#include <algorithm>
#include <cmath>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

#include "Vcordic.h"

#ifndef CFG_WIDTH
#define CFG_WIDTH 16
#endif
#ifndef CFG_ITERATIONS
#define CFG_ITERATIONS 12
#endif

#define PERIOD 10

// Number of test vectors, spread evenly over a full turn
#define NB_VECTORS 512

// Extra margin, in LSB, added on top of the theoretical error bound of the
// configuration under test (see error_tolerance() below)
#define ERROR_MARGIN_LSB 2.0

// Number of cycles dumped in the VCD file (a full run would be far too big)
#define TRACE_CYCLES 300

static const double PI = 3.14159265358979323846;

vluint64_t main_time = 0;  // Current simulation time
vluint64_t cycle = 0;      // Current clock cycle

double sc_time_stamp() {
  return main_time;
}

// CORDIC processing gain: product of sqrt(1 + 2^-2i) over all iterations
static double cordic_gain(int iterations) {
  double gain = 1.0;
  for (int i = 0; i < iterations; i++) {
    gain *= std::sqrt(1.0 + std::pow(2.0, -2.0 * i));
  }
  return gain;
}

// Theoretical error bound of a given configuration, in LSB. Two terms
// contribute: the angle left over after the last rotation, and the truncation
// of the arithmetic shift of each stage.
static double error_tolerance(int iterations, double radius) {
  // Worst case residual angle after the last rotation step
  const double residual_angle = std::atan(std::pow(2.0, -double(iterations - 1)));
  const double angle_error = radius * residual_angle;
  // Worst case truncation: up to one LSB per pipeline register
  const double truncation_error = double(iterations + 2);
  return angle_error + truncation_error + ERROR_MARGIN_LSB;
}

// Sign extend a WIDTH-bit value read from the design
static double signed_value(vluint32_t raw, int width) {
  vluint32_t mask = (width >= 32) ? 0xFFFFFFFFu : ((1u << width) - 1u);
  vluint32_t value = raw & mask;
  if (width < 32 && (value & (1u << (width - 1)))) {
    return double(int32_t(value | ~mask));
  }
  return double(int32_t(value));
}

// Write the testbench results as a flat yaml file, so that Odatix can extract
// them as metrics (see _metrics.yml of this simulation)
static void write_yaml_results(const std::string& path,
                               const std::vector<std::pair<std::string, double> >& values,
                               const std::vector<std::pair<std::string, std::string> >& strings) {
  std::ofstream yaml(path.c_str());
  if (!yaml.is_open()) {
    std::cerr << "Error: Could not open result file '" << path << "'" << std::endl;
    return;
  }

  yaml << std::fixed;
  for (size_t i = 0; i < values.size(); i++) {
    yaml << values[i].first << ": " << std::setprecision(6) << values[i].second << std::endl;
  }
  for (size_t i = 0; i < strings.size(); i++) {
    yaml << strings[i].first << ": " << strings[i].second << std::endl;
  }

  yaml.close();
}

static void report_progress(const std::string& path, int percent) {
  std::ofstream progress(path.c_str());
  if (progress.is_open()) {
    progress << "progress: " << percent << "%" << std::endl;
    progress.close();
  }
}

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);

  std::string vcd_file_path = "./waveform.vcd";
  std::string result_file_path = "./results.yml";
  std::string progress_file_path = "./log/progress.log";

  // Options
  int opt;
  static struct option long_options[] = {
    {"vcd_file", required_argument, 0, 'v'},
    {"result_file", required_argument, 0, 'r'},
    {"progress_file", required_argument, 0, 'p'},
    {0, 0, 0, 0}
  };

  int option_index = 0;
  while ((opt = getopt_long(argc, argv, "v:r:p:", long_options, &option_index)) != -1) {
    switch (opt) {
      case 'v':
        vcd_file_path = optarg;
        break;
      case 'r':
        result_file_path = optarg;
        break;
      case 'p':
        progress_file_path = optarg;
        break;
      default:
        std::cerr << "Error: Invalid option '" << (char)opt << "'" << std::endl;
        return 1;
    }
  }

  const int width = CFG_WIDTH;
  const int iterations = CFG_ITERATIONS;
  const double gain = cordic_gain(iterations);
  const double full_scale = std::pow(2.0, width - 1) - 1.0;

  // Input magnitude, chosen so that the gain does not saturate the output
  const double magnitude = std::floor(0.55 * full_scale / gain);

  // Error budget expected from this configuration
  const double tolerance = error_tolerance(iterations, magnitude * gain);

  std::cout << "CORDIC testbench: WIDTH=" << width << ", ITERATIONS=" << iterations << std::endl;
  std::cout << "  processing gain : " << gain << std::endl;
  std::cout << "  input magnitude : " << magnitude << " / " << full_scale << std::endl;
  std::cout << "  test vectors    : " << NB_VECTORS << std::endl;
  std::cout << "  error tolerance : " << tolerance << " LSB" << std::endl;

  // Build the stimulus: a full turn, one vector per test point
  std::vector<double> angles(NB_VECTORS);
  std::vector<int32_t> angles_fixed(NB_VECTORS);
  std::vector<double> ref_x(NB_VECTORS);
  std::vector<double> ref_y(NB_VECTORS);

  const double input_x = magnitude;
  const double input_y = 0.0;

  for (int i = 0; i < NB_VECTORS; i++) {
    // Angle encoding: a full turn maps to 2^32
    int64_t fixed = int64_t(i) * (int64_t(1) << 32) / NB_VECTORS - (int64_t(1) << 31);
    angles_fixed[i] = int32_t(fixed);
    angles[i] = double(fixed) * 2.0 * PI / std::pow(2.0, 32);
    ref_x[i] = gain * (input_x * std::cos(angles[i]) - input_y * std::sin(angles[i]));
    ref_y[i] = gain * (input_x * std::sin(angles[i]) + input_y * std::cos(angles[i]));
  }

  // Instantiate the design
  Vcordic* top = new Vcordic;

  // Initialize VCD trace dump
  Verilated::traceEverOn(true);
  VerilatedVcdC* tfp = new VerilatedVcdC;
  top->trace(tfp, 99);
  tfp->open(vcd_file_path.c_str());

  // Initial signals
  top->clock = 0;
  top->reset = 1;
  top->i_valid = 0;
  top->i_x = 0;
  top->i_y = 0;
  top->i_angle = 0;

  const vluint64_t reset_cycles = 4;
  // Enough cycles to push every vector in and flush the whole pipeline
  const vluint64_t max_cycles = reset_cycles + NB_VECTORS + iterations + 32;

  int sent = 0;
  std::vector<double> out_x;
  std::vector<double> out_y;
  out_x.reserve(NB_VECTORS);
  out_y.reserve(NB_VECTORS);

  vluint64_t first_input_cycle = 0;
  vluint64_t first_output_cycle = 0;
  bool reset_ok = true;
  bool continuity_ok = true;
  bool got_output = false;
  int last_percent = 0;

  const std::clock_t start_clock = std::clock();

  // Simulation loop, one clock edge per iteration
  while (!Verilated::gotFinish() && cycle < max_cycles) {
    top->clock = !top->clock;

    if (main_time == 2 * reset_cycles - 1) {
      top->reset = 0;
    }

    top->eval();

    if (cycle < TRACE_CYCLES) {
      tfp->dump(main_time);
    }

    if (top->clock) {
      // Sample the outputs on the rising edge
      if (top->o_valid) {
        if (!got_output) {
          first_output_cycle = cycle;
          got_output = true;
        }
        if (int(out_x.size()) < NB_VECTORS) {
          out_x.push_back(signed_value(top->o_x, width));
          out_y.push_back(signed_value(top->o_y, width));
        }
      } else if (int(out_x.size()) > 0 && int(out_x.size()) < NB_VECTORS) {
        // o_valid must stay asserted while the pipeline is being drained
        continuity_ok = false;
      }

      // Check that the reset zeroes the outputs
      if (cycle == reset_cycles - 1) {
        if (top->o_valid != 0 || signed_value(top->o_x, width) != 0.0 ||
            signed_value(top->o_y, width) != 0.0) {
          reset_ok = false;
          std::cout << "Reset KO: outputs are not cleared" << std::endl;
        }
      }

      // Drive the next stimulus
      if (cycle >= reset_cycles && sent < NB_VECTORS) {
        if (sent == 0) {
          first_input_cycle = cycle + 1;
        }
        vluint32_t mask = (width >= 32) ? 0xFFFFFFFFu : ((1u << width) - 1u);
        top->i_valid = 1;
        top->i_x = vluint32_t(int32_t(input_x)) & mask;
        top->i_y = vluint32_t(int32_t(input_y)) & mask;
        top->i_angle = vluint32_t(angles_fixed[sent]);
        sent++;

        int percent = 5 + (90 * sent) / NB_VECTORS;
        if (percent != last_percent) {
          report_progress(progress_file_path, percent);
          last_percent = percent;
        }
      } else if (sent >= NB_VECTORS) {
        top->i_valid = 0;
      }

      if (int(out_x.size()) >= NB_VECTORS) {
        break;
      }
    }

    main_time++;
    cycle = main_time / 2;
  }

  const double runtime_ms = 1000.0 * double(std::clock() - start_clock) / CLOCKS_PER_SEC;

  // ------------------------------------------------------------------
  // Accuracy analysis
  // ------------------------------------------------------------------
  const int compared = int(out_x.size());

  double max_error = 0.0;
  double sum_sq_error = 0.0;
  double sum_error = 0.0;
  double max_angle_error_deg = 0.0;
  double sum_sq_angle_error = 0.0;
  double sum_sq_signal = 0.0;
  int checks_passed = 0;
  double worst_angle_deg = 0.0;

  for (int i = 0; i < compared; i++) {
    const double error_x = out_x[i] - ref_x[i];
    const double error_y = out_y[i] - ref_y[i];
    const double error = std::sqrt(error_x * error_x + error_y * error_y);

    sum_error += error;
    sum_sq_error += error * error;
    sum_sq_signal += ref_x[i] * ref_x[i] + ref_y[i] * ref_y[i];

    if (error > max_error) {
      max_error = error;
      worst_angle_deg = angles[i] * 180.0 / PI;
    }
    if (error <= tolerance) {
      checks_passed++;
    }

    // Angular error between the reference and the actual output vector
    const double ref_angle = std::atan2(ref_y[i], ref_x[i]);
    const double out_angle = std::atan2(out_y[i], out_x[i]);
    double angle_error = out_angle - ref_angle;
    while (angle_error > PI) angle_error -= 2.0 * PI;
    while (angle_error < -PI) angle_error += 2.0 * PI;
    const double angle_error_deg = std::fabs(angle_error) * 180.0 / PI;

    sum_sq_angle_error += angle_error_deg * angle_error_deg;
    max_angle_error_deg = std::max(max_angle_error_deg, angle_error_deg);
  }

  const double mean_error = compared > 0 ? sum_error / compared : 0.0;
  const double rms_error = compared > 0 ? std::sqrt(sum_sq_error / compared) : 0.0;
  const double rms_angle_error_deg = compared > 0 ? std::sqrt(sum_sq_angle_error / compared) : 0.0;
  const double rms_signal = compared > 0 ? std::sqrt(sum_sq_signal / compared) : 0.0;

  const double snr_db = (rms_error > 0.0 && rms_signal > 0.0)
                          ? 20.0 * std::log10(rms_signal / rms_error)
                          : 0.0;
  // Effective number of bits, referred to the full scale of the datapath
  const double enob = (rms_error > 0.0) ? (double(width) - std::log2(rms_error * std::sqrt(12.0)))
                                        : double(width);

  const vluint64_t latency = got_output && first_output_cycle >= first_input_cycle
                               ? (first_output_cycle - first_input_cycle)
                               : 0;
  const double throughput = cycle > 0 ? double(compared) / double(cycle) : 0.0;

  const bool completeness_ok = (compared == NB_VECTORS) && continuity_ok;
  const bool latency_ok = (latency == vluint64_t(iterations) + 1);
  const bool accuracy_ok = (checks_passed == compared) && completeness_ok;
  const bool all_ok = reset_ok && completeness_ok && latency_ok && accuracy_ok;

  std::cout << "  latency         : " << latency << " cycles" << std::endl;
  std::cout << "  max error       : " << max_error << " LSB (at " << worst_angle_deg << " deg)"
            << std::endl;
  std::cout << "  rms error       : " << rms_error << " LSB" << std::endl;
  std::cout << "  rms angle error : " << rms_angle_error_deg << " deg" << std::endl;
  std::cout << "  snr             : " << snr_db << " dB" << std::endl;
  std::cout << "  status          : " << (all_ok ? "OK" : "KO") << std::endl;

  // ------------------------------------------------------------------
  // Export the results
  // ------------------------------------------------------------------
  std::vector<std::pair<std::string, double> > values;
  values.push_back(std::make_pair("width", double(width)));
  values.push_back(std::make_pair("iterations", double(iterations)));
  values.push_back(std::make_pair("cycles", double(cycle)));
  values.push_back(std::make_pair("latency_cycles", double(latency)));
  values.push_back(std::make_pair("throughput", throughput));
  values.push_back(std::make_pair("vectors", double(compared)));
  values.push_back(std::make_pair("error_tolerance_lsb", tolerance));
  values.push_back(std::make_pair("max_error_lsb", max_error));
  values.push_back(std::make_pair("rms_error_lsb", rms_error));
  values.push_back(std::make_pair("mean_error_lsb", mean_error));
  values.push_back(std::make_pair("max_angle_error_deg", max_angle_error_deg));
  values.push_back(std::make_pair("rms_angle_error_deg", rms_angle_error_deg));
  values.push_back(std::make_pair("snr_db", snr_db));
  values.push_back(std::make_pair("enob", enob));
  values.push_back(std::make_pair("worst_case_angle_deg", worst_angle_deg));
  values.push_back(std::make_pair("sim_runtime_ms", runtime_ms));
  values.push_back(std::make_pair("checks_total", double(compared)));
  values.push_back(std::make_pair("checks_passed", double(checks_passed)));
  values.push_back(std::make_pair("checks_failed", double(compared - checks_passed)));
  values.push_back(std::make_pair(
    "pass_rate", compared > 0 ? 100.0 * double(checks_passed) / double(compared) : 0.0));

  std::vector<std::pair<std::string, std::string> > strings;
  strings.push_back(std::make_pair("reset", reset_ok ? "OK" : "KO"));
  strings.push_back(std::make_pair("latency_check", latency_ok ? "OK" : "KO"));
  strings.push_back(std::make_pair("completeness", completeness_ok ? "OK" : "KO"));
  strings.push_back(std::make_pair("accuracy", accuracy_ok ? "OK" : "KO"));
  strings.push_back(std::make_pair("status", all_ok ? "OK" : "KO"));

  write_yaml_results(result_file_path, values, strings);
  report_progress(progress_file_path, 100);

  // Finalize simulation
  top->final();
  tfp->close();
  delete top;
  delete tfp;
  return 0;
}
