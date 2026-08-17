
`timescale 1ns / 1ps

module tb_cordic #(
  parameter int WIDTH = 16,
  parameter int ITERATIONS = 12
);

  localparam real PERIOD = 10.0;

  localparam string RESULT_FILE   = "./results.yml";
  localparam string PROGRESS_FILE = "./log/progress.log";

  // Number of test vectors, spread evenly over a full turn
  localparam int NB_VECTORS = 512;
  // 2^32 / NB_VECTORS, the angle step between two consecutive vectors
  localparam int ANGLE_STEP = 8388608;

  // Extra margin, in LSB, added on top of the theoretical error bound of the
  // configuration under test (see error_tolerance below)
  localparam real ERROR_MARGIN_LSB = 2.0;

  localparam int RESET_CYCLES = 4;
  localparam int MAX_CYCLES   = RESET_CYCLES + NB_VECTORS + ITERATIONS + 32;

  localparam real MATH_PI = 3.14159265358979323846;

  // Signals
  logic                    clock   = 1'b0;
  logic                    reset   = 1'b1;
  logic                    i_valid = 1'b0;
  logic signed [WIDTH-1:0] i_x     = '0;
  logic signed [WIDTH-1:0] i_y     = '0;
  logic signed [31:0]      i_angle = '0;
  logic                    o_valid;
  logic signed [WIDTH-1:0] o_x;
  logic signed [WIDTH-1:0] o_y;

  bit running = 1'b1;

  // Stimulus and reference model
  real ref_x  [NB_VECTORS];
  real ref_y  [NB_VECTORS];
  real out_x  [NB_VECTORS];
  real out_y  [NB_VECTORS];
  real angles [NB_VECTORS];
  int  angles_fixed [NB_VECTORS];

  // ------------------------------------------------------------------
  // Design under test
  // ------------------------------------------------------------------
  // Instantiated by name only: the very same instantiation binds either the
  // VHDL entity or the SystemVerilog module, whichever was compiled into the
  // work library by scripts/sim.do.
  cordic #(
    .WIDTH      (WIDTH),
    .ITERATIONS (ITERATIONS)
  ) uut (
    .clock   (clock),
    .reset   (reset),
    .i_valid (i_valid),
    .i_x     (i_x),
    .i_y     (i_y),
    .i_angle (i_angle),
    .o_valid (o_valid),
    .o_x     (o_x),
    .o_y     (o_y)
  );

  // Clock generation, stopped once the stimulus process is done so that the
  // simulation ends by itself
  always begin
    #(PERIOD / 2.0);
    clock = running ? ~clock : 1'b0;
  end

  // ------------------------------------------------------------------
  // Reference model helpers
  // ------------------------------------------------------------------

  // CORDIC processing gain: product of sqrt(1 + 2^-2i) over all iterations
  function automatic real cordic_gain(input int nb_stages);
    real gain = 1.0;
    for (int i = 0; i < nb_stages; i++) begin
      gain = gain * $sqrt(1.0 + $pow(2.0, -2.0 * real'(i)));
    end
    return gain;
  endfunction

  // Theoretical error bound of a given configuration, in LSB. Two terms
  // contribute: the angle left over after the last rotation, and the
  // truncation of the arithmetic shift of each stage.
  function automatic real error_tolerance(input int nb_stages, input real radius);
    real residual_angle = $atan($pow(2.0, -real'(nb_stages - 1)));
    real angle_error    = radius * residual_angle;
    // Worst case truncation: up to one LSB per pipeline register
    real truncation_error = real'(nb_stages + 2);
    return angle_error + truncation_error + ERROR_MARGIN_LSB;
  endfunction

  function automatic void report_progress(input int percent);
    int fd = $fopen(PROGRESS_FILE, "w");
    if (fd != 0) begin
      $fdisplay(fd, "progress: %0d%%", percent);
      $fclose(fd);
    end
  endfunction

  // ------------------------------------------------------------------
  // Stimulus
  // ------------------------------------------------------------------
  initial begin : stimulus
    real gain       = cordic_gain(ITERATIONS);
    real full_scale = $pow(2.0, real'(WIDTH - 1)) - 1.0;
    // Input magnitude, chosen so that the gain does not saturate the output
    real magnitude;
    real tolerance;

    int sent     = 0;
    int received = 0;
    int cycle    = 0;
    int first_input_cycle  = 0;
    int first_output_cycle = 0;
    bit got_output = 1'b0;

    bit reset_ok      = 1'b1;
    bit continuity_ok = 1'b1;

    // Accuracy analysis
    real error_x, error_y, err;
    real max_error     = 0.0;
    real sum_error     = 0.0;
    real sum_sq_error  = 0.0;
    real sum_sq_signal = 0.0;
    real ref_angle, out_angle, angle_error, angle_error_deg;
    real max_angle_error_deg = 0.0;
    real sum_sq_angle_error  = 0.0;
    real worst_angle_deg = 0.0;
    int  checks_passed = 0;

    real mean_error, rms_error, rms_angle_error_deg, rms_signal;
    real snr_db, enob, throughput;
    real pass_rate;
    int  latency = 0;

    bit completeness_ok, latency_ok, accuracy_ok, all_ok;

    int last_percent = 0;
    int percent;

    int fd;

    magnitude = $floor(0.55 * full_scale / gain);
    tolerance = error_tolerance(ITERATIONS, magnitude * gain);

    $display("CORDIC testbench: WIDTH=%0d, ITERATIONS=%0d", WIDTH, ITERATIONS);
    $display("  processing gain : %0.6f", gain);
    $display("  input magnitude : %0.0f / %0.0f", magnitude, full_scale);
    $display("  test vectors    : %0d", NB_VECTORS);
    $display("  error tolerance : %0.3f LSB", tolerance);

    // Build the stimulus: a full turn, one vector per test point
    for (int i = 0; i < NB_VECTORS; i++) begin
      // Angle encoding: a full turn maps to 2^32
      angles_fixed[i] = (i - NB_VECTORS / 2) * ANGLE_STEP;
      angles[i] = real'(angles_fixed[i]) * 2.0 * MATH_PI / $pow(2.0, 32.0);
      ref_x[i] = gain * magnitude * $cos(angles[i]);
      ref_y[i] = gain * magnitude * $sin(angles[i]);
    end

    report_progress(1);

    // Reset
    reset   = 1'b1;
    i_valid = 1'b0;
    repeat (RESET_CYCLES) @(posedge clock);
    #(PERIOD / 4.0);
    // Check that the reset zeroes the outputs
    if (o_valid !== 1'b0 || o_x !== '0 || o_y !== '0) begin
      reset_ok = 1'b0;
      $display("Reset KO: outputs are not cleared");
    end
    reset = 1'b0;
    i_x   = WIDTH'(int'(magnitude));
    i_y   = '0;

    // Feed the design and collect its outputs, one vector per cycle
    for (int c = 0; c < MAX_CYCLES; c++) begin
      @(posedge clock);
      // Let the outputs of the design settle before sampling them
      #(PERIOD / 4.0);
      cycle = c;

      if (o_valid === 1'b1) begin
        if (!got_output) begin
          first_output_cycle = c;
          got_output = 1'b1;
        end
        if (received < NB_VECTORS) begin
          out_x[received] = real'(o_x);
          out_y[received] = real'(o_y);
          received++;
        end
      end else if (received > 0 && received < NB_VECTORS) begin
        // o_valid must stay asserted while the pipeline is being drained
        continuity_ok = 1'b0;
      end

      if (sent < NB_VECTORS) begin
        if (sent == 0) begin
          first_input_cycle = c + 1;
        end
        i_valid = 1'b1;
        i_angle = angles_fixed[sent];
        sent++;

        percent = 5 + (90 * sent) / NB_VECTORS;
        if (percent != last_percent) begin
          report_progress(percent);
          last_percent = percent;
        end
      end else begin
        i_valid = 1'b0;
      end

      if (received >= NB_VECTORS) begin
        break;
      end
    end

    // ------------------------------------------------------------------
    // Accuracy analysis
    // ------------------------------------------------------------------
    for (int i = 0; i < received; i++) begin
      error_x = out_x[i] - ref_x[i];
      error_y = out_y[i] - ref_y[i];
      err = $sqrt(error_x * error_x + error_y * error_y);

      sum_error     = sum_error + err;
      sum_sq_error  = sum_sq_error + err * err;
      sum_sq_signal = sum_sq_signal + ref_x[i] * ref_x[i] + ref_y[i] * ref_y[i];

      if (err > max_error) begin
        max_error = err;
        worst_angle_deg = angles[i] * 180.0 / MATH_PI;
      end
      if (err <= tolerance) begin
        checks_passed++;
      end

      // Angular error between the reference and the actual output vector
      ref_angle = $atan2(ref_y[i], ref_x[i]);
      out_angle = $atan2(out_y[i], out_x[i]);
      angle_error = out_angle - ref_angle;
      while (angle_error > MATH_PI) begin
        angle_error = angle_error - 2.0 * MATH_PI;
      end
      while (angle_error < -MATH_PI) begin
        angle_error = angle_error + 2.0 * MATH_PI;
      end
      angle_error_deg = ((angle_error < 0.0) ? -angle_error : angle_error) * 180.0 / MATH_PI;

      sum_sq_angle_error = sum_sq_angle_error + angle_error_deg * angle_error_deg;
      if (angle_error_deg > max_angle_error_deg) begin
        max_angle_error_deg = angle_error_deg;
      end
    end

    if (received > 0) begin
      mean_error          = sum_error / real'(received);
      rms_error           = $sqrt(sum_sq_error / real'(received));
      rms_angle_error_deg = $sqrt(sum_sq_angle_error / real'(received));
      rms_signal          = $sqrt(sum_sq_signal / real'(received));
    end else begin
      mean_error          = 0.0;
      rms_error           = 0.0;
      rms_angle_error_deg = 0.0;
      rms_signal          = 0.0;
    end

    if (rms_error > 0.0 && rms_signal > 0.0) begin
      snr_db = 20.0 * ($ln(rms_signal / rms_error) / $ln(10.0));
    end else begin
      snr_db = 0.0;
    end
    // Effective number of bits, referred to the full scale of the datapath
    if (rms_error > 0.0) begin
      enob = real'(WIDTH) - ($ln(rms_error * $sqrt(12.0)) / $ln(2.0));
    end else begin
      enob = real'(WIDTH);
    end

    if (got_output && first_output_cycle >= first_input_cycle) begin
      latency = first_output_cycle - first_input_cycle;
    end
    if (cycle > 0) begin
      throughput = real'(received) / real'(cycle);
    end else begin
      throughput = 0.0;
    end

    pass_rate = (received > 0) ? 100.0 * real'(checks_passed) / real'(received) : 0.0;

    completeness_ok = (received == NB_VECTORS) && continuity_ok;
    latency_ok      = (latency == ITERATIONS + 1);
    accuracy_ok     = (checks_passed == received) && completeness_ok;
    all_ok          = reset_ok && completeness_ok && latency_ok && accuracy_ok;

    $display("  latency         : %0d cycles", latency);
    $display("  max error       : %0.6f LSB (at %0.2f deg)", max_error, worst_angle_deg);
    $display("  rms error       : %0.6f LSB", rms_error);
    $display("  rms angle error : %0.6f deg", rms_angle_error_deg);
    $display("  snr             : %0.6f dB", snr_db);
    $display("  status          : %s", all_ok ? "OK" : "KO");

    // ------------------------------------------------------------------
    // Export the results
    // ------------------------------------------------------------------
    fd = $fopen(RESULT_FILE, "w");
    if (fd == 0) begin
      $display("Could not open result file '%s'", RESULT_FILE);
    end else begin
      $fdisplay(fd, "width: %0d", WIDTH);
      $fdisplay(fd, "iterations: %0d", ITERATIONS);
      $fdisplay(fd, "cycles: %0d", cycle);
      $fdisplay(fd, "latency_cycles: %0d", latency);
      $fdisplay(fd, "throughput: %0.6f", throughput);
      $fdisplay(fd, "vectors: %0d", received);
      $fdisplay(fd, "error_tolerance_lsb: %0.6f", tolerance);
      $fdisplay(fd, "max_error_lsb: %0.6f", max_error);
      $fdisplay(fd, "rms_error_lsb: %0.6f", rms_error);
      $fdisplay(fd, "mean_error_lsb: %0.6f", mean_error);
      $fdisplay(fd, "max_angle_error_deg: %0.6f", max_angle_error_deg);
      $fdisplay(fd, "rms_angle_error_deg: %0.6f", rms_angle_error_deg);
      $fdisplay(fd, "snr_db: %0.6f", snr_db);
      $fdisplay(fd, "enob: %0.6f", enob);
      $fdisplay(fd, "worst_case_angle_deg: %0.6f", worst_angle_deg);
      $fdisplay(fd, "checks_total: %0d", received);
      $fdisplay(fd, "checks_passed: %0d", checks_passed);
      $fdisplay(fd, "checks_failed: %0d", received - checks_passed);
      $fdisplay(fd, "pass_rate: %0.6f", pass_rate);
      $fdisplay(fd, "reset: %s", reset_ok ? "OK" : "KO");
      $fdisplay(fd, "latency_check: %s", latency_ok ? "OK" : "KO");
      $fdisplay(fd, "completeness: %s", completeness_ok ? "OK" : "KO");
      $fdisplay(fd, "accuracy: %s", accuracy_ok ? "OK" : "KO");
      $fdisplay(fd, "status: %s", all_ok ? "OK" : "KO");
      $fclose(fd);
    end

    report_progress(100);

    // Stop the clock, which ends the simulation
    running = 1'b0;
    #(PERIOD);
    $finish;
  end

endmodule
