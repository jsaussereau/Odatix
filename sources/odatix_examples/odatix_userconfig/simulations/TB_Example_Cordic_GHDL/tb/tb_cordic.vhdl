
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use IEEE.MATH_REAL.ALL;
use std.textio.all;

entity tb_cordic is
  generic (
    WIDTH : integer := 16;
    ITERATIONS : integer := 12
  );
end entity tb_cordic;

architecture Behavioral of tb_cordic is

  constant PERIOD       : time    := 10 ns;
  constant RESULT_FILE  : string  := "./results.yml";
  constant PROGRESS_FILE : string := "./log/progress.log";

  -- Number of test vectors, spread evenly over a full turn
  constant NB_VECTORS  : integer := 512;
  -- 2^32 / NB_VECTORS, the angle step between two consecutive vectors
  constant ANGLE_STEP  : integer := 8388608;

  -- Extra margin, in LSB, added on top of the theoretical error bound of the
  -- configuration under test (see error_tolerance below)
  constant ERROR_MARGIN_LSB : real := 2.0;

  constant RESET_CYCLES : integer := 4;
  constant MAX_CYCLES   : integer := RESET_CYCLES + NB_VECTORS + ITERATIONS + 32;

  -- Signals
  signal clock   : std_logic := '0';
  signal reset   : std_logic := '1';
  signal i_valid : std_logic := '0';
  signal i_x     : std_logic_vector(WIDTH-1 downto 0) := (others => '0');
  signal i_y     : std_logic_vector(WIDTH-1 downto 0) := (others => '0');
  signal i_angle : std_logic_vector(31 downto 0) := (others => '0');
  signal o_valid : std_logic;
  signal o_x     : std_logic_vector(WIDTH-1 downto 0);
  signal o_y     : std_logic_vector(WIDTH-1 downto 0);

  signal running : boolean := true;

  type real_vector_t is array (0 to NB_VECTORS-1) of real;
  type angle_vector_t is array (0 to NB_VECTORS-1) of integer;

  -- CORDIC processing gain: product of sqrt(1 + 2^-2i) over all iterations
  function cordic_gain(nb_stages : integer) return real is
    variable gain : real := 1.0;
  begin
    for i in 0 to nb_stages-1 loop
      gain := gain * sqrt(1.0 + 2.0 ** (-2.0 * real(i)));
    end loop;
    return gain;
  end function;

  -- Theoretical error bound of a given configuration, in LSB. Two terms
  -- contribute: the angle left over after the last rotation, and the
  -- truncation of the arithmetic shift of each stage.
  function error_tolerance(nb_stages : integer; radius : real) return real is
    constant residual_angle   : real := arctan(2.0 ** (-real(nb_stages - 1)));
    constant angle_error      : real := radius * residual_angle;
    -- Worst case truncation: up to one LSB per pipeline register
    constant truncation_error : real := real(nb_stages + 2);
  begin
    return angle_error + truncation_error + ERROR_MARGIN_LSB;
  end function;

  -- Write the testbench results as a flat yaml file, so that Odatix can
  -- extract them as metrics (see _metrics.yml of this simulation)
  procedure write_yaml_real(l : inout line; file f : text; name : in string; value : in real) is
  begin
    write(l, name & ": ");
    write(l, value, right, 0, 6);
    writeline(f, l);
  end procedure;

  procedure report_progress(percent : in integer) is
    file progress_out : text;
    variable status   : file_open_status;
    variable l        : line;
  begin
    file_open(status, progress_out, PROGRESS_FILE, write_mode);
    if status = open_ok then
      write(l, string'("progress: ") & integer'image(percent) & "%");
      writeline(progress_out, l);
      file_close(progress_out);
    end if;
  end procedure;

begin

  -- Instantiate the design under test
  uut : entity work.cordic
    generic map (
      WIDTH      => WIDTH,
      ITERATIONS => ITERATIONS
    )
    port map (
      clock   => clock,
      reset   => reset,
      i_valid => i_valid,
      i_x     => i_x,
      i_y     => i_y,
      i_angle => i_angle,
      o_valid => o_valid,
      o_x     => o_x,
      o_y     => o_y
    );

  -- Clock generation, stopped once the stimulus process is done so that the
  -- simulation ends by itself
  clock <= (not clock) after PERIOD/2 when running else '0';

  stimulus : process
    -- Stimulus and reference model
    variable angles      : real_vector_t;
    variable angles_fixed : angle_vector_t;
    variable ref_x       : real_vector_t;
    variable ref_y       : real_vector_t;
    variable out_x       : real_vector_t;
    variable out_y       : real_vector_t;

    variable gain       : real := cordic_gain(ITERATIONS);
    variable full_scale : real := 2.0 ** real(WIDTH - 1) - 1.0;
    -- Input magnitude, chosen so that the gain does not saturate the output
    variable magnitude  : real;
    variable tolerance  : real;

    variable angle_word : signed(31 downto 0);

    variable sent     : integer := 0;
    variable received : integer := 0;
    variable cycle    : integer := 0;
    variable first_input_cycle  : integer := 0;
    variable first_output_cycle : integer := 0;
    variable got_output : boolean := false;

    variable reset_ok      : boolean := true;
    variable continuity_ok : boolean := true;

    -- Accuracy analysis
    variable error_x, error_y, err : real;
    variable max_error     : real := 0.0;
    variable sum_error     : real := 0.0;
    variable sum_sq_error  : real := 0.0;
    variable sum_sq_signal : real := 0.0;
    variable ref_angle, out_angle, angle_error, angle_error_deg : real;
    variable max_angle_error_deg : real := 0.0;
    variable sum_sq_angle_error : real := 0.0;
    variable worst_angle_deg : real := 0.0;
    variable checks_passed : integer := 0;

    variable mean_error, rms_error, rms_angle_error_deg, rms_signal : real;
    variable snr_db, enob, throughput : real;
    variable latency : integer := 0;

    variable completeness_ok, latency_ok, accuracy_ok, all_ok : boolean;

    variable last_percent : integer := 0;
    variable percent      : integer;

    variable l : line;
    file results_out : text;
    variable status : file_open_status;

    -- Read back a WIDTH-bit output of the design as a real
    function signed_value(value : std_logic_vector) return real is
    begin
      return real(to_integer(signed(value)));
    end function;
  begin
    magnitude := floor(0.55 * full_scale / gain);
    tolerance := error_tolerance(ITERATIONS, magnitude * gain);

    report "CORDIC testbench: WIDTH=" & integer'image(WIDTH) &
           ", ITERATIONS=" & integer'image(ITERATIONS);
    report "  test vectors    : " & integer'image(NB_VECTORS);

    -- Build the stimulus: a full turn, one vector per test point
    for i in 0 to NB_VECTORS-1 loop
      -- Angle encoding: a full turn maps to 2^32
      angles_fixed(i) := (i - NB_VECTORS/2) * ANGLE_STEP;
      angles(i) := real(angles_fixed(i)) * 2.0 * MATH_PI / (2.0 ** 32.0);
      ref_x(i) := gain * magnitude * cos(angles(i));
      ref_y(i) := gain * magnitude * sin(angles(i));
    end loop;

    report_progress(1);

    -- Reset
    reset <= '1';
    i_valid <= '0';
    for c in 0 to RESET_CYCLES-1 loop
      wait until rising_edge(clock);
    end loop;
    wait for PERIOD/4;
    -- Check that the reset zeroes the outputs
    if o_valid /= '0' or signed_value(o_x) /= 0.0 or signed_value(o_y) /= 0.0 then
      reset_ok := false;
      report "Reset KO: outputs are not cleared" severity warning;
    end if;
    reset <= '0';
    i_x <= std_logic_vector(to_signed(integer(magnitude), WIDTH));
    i_y <= (others => '0');

    -- Feed the design and collect its outputs, one vector per cycle
    for c in 0 to MAX_CYCLES-1 loop
      wait until rising_edge(clock);
      -- Let the outputs of the design settle before sampling them
      wait for PERIOD/4;
      cycle := c;

      if o_valid = '1' then
        if not got_output then
          first_output_cycle := c;
          got_output := true;
        end if;
        if received < NB_VECTORS then
          out_x(received) := signed_value(o_x);
          out_y(received) := signed_value(o_y);
          received := received + 1;
        end if;
      elsif received > 0 and received < NB_VECTORS then
        -- o_valid must stay asserted while the pipeline is being drained
        continuity_ok := false;
      end if;

      if sent < NB_VECTORS then
        if sent = 0 then
          first_input_cycle := c + 1;
        end if;
        angle_word := to_signed(angles_fixed(sent), 32);
        i_valid <= '1';
        i_angle <= std_logic_vector(angle_word);
        sent := sent + 1;

        percent := 5 + (90 * sent) / NB_VECTORS;
        if percent /= last_percent then
          report_progress(percent);
          last_percent := percent;
        end if;
      else
        i_valid <= '0';
      end if;

      exit when received >= NB_VECTORS;
    end loop;

    -- ------------------------------------------------------------------
    -- Accuracy analysis
    -- ------------------------------------------------------------------
    for i in 0 to received-1 loop
      error_x := out_x(i) - ref_x(i);
      error_y := out_y(i) - ref_y(i);
      err := sqrt(error_x * error_x + error_y * error_y);

      sum_error := sum_error + err;
      sum_sq_error := sum_sq_error + err * err;
      sum_sq_signal := sum_sq_signal + ref_x(i) * ref_x(i) + ref_y(i) * ref_y(i);

      if err > max_error then
        max_error := err;
        worst_angle_deg := angles(i) * 180.0 / MATH_PI;
      end if;
      if err <= tolerance then
        checks_passed := checks_passed + 1;
      end if;

      -- Angular error between the reference and the actual output vector
      ref_angle := arctan(ref_y(i), ref_x(i));
      out_angle := arctan(out_y(i), out_x(i));
      angle_error := out_angle - ref_angle;
      while angle_error > MATH_PI loop
        angle_error := angle_error - 2.0 * MATH_PI;
      end loop;
      while angle_error < -MATH_PI loop
        angle_error := angle_error + 2.0 * MATH_PI;
      end loop;
      angle_error_deg := abs(angle_error) * 180.0 / MATH_PI;

      sum_sq_angle_error := sum_sq_angle_error + angle_error_deg * angle_error_deg;
      if angle_error_deg > max_angle_error_deg then
        max_angle_error_deg := angle_error_deg;
      end if;
    end loop;

    if received > 0 then
      mean_error := sum_error / real(received);
      rms_error := sqrt(sum_sq_error / real(received));
      rms_angle_error_deg := sqrt(sum_sq_angle_error / real(received));
      rms_signal := sqrt(sum_sq_signal / real(received));
    else
      mean_error := 0.0;
      rms_error := 0.0;
      rms_angle_error_deg := 0.0;
      rms_signal := 0.0;
    end if;

    if rms_error > 0.0 and rms_signal > 0.0 then
      snr_db := 20.0 * log10(rms_signal / rms_error);
    else
      snr_db := 0.0;
    end if;
    -- Effective number of bits, referred to the full scale of the datapath
    if rms_error > 0.0 then
      enob := real(WIDTH) - log2(rms_error * sqrt(12.0));
    else
      enob := real(WIDTH);
    end if;

    if got_output and first_output_cycle >= first_input_cycle then
      latency := first_output_cycle - first_input_cycle;
    end if;
    if cycle > 0 then
      throughput := real(received) / real(cycle);
    else
      throughput := 0.0;
    end if;

    completeness_ok := (received = NB_VECTORS) and continuity_ok;
    latency_ok := (latency = ITERATIONS + 1);
    accuracy_ok := (checks_passed = received) and completeness_ok;
    all_ok := reset_ok and completeness_ok and latency_ok and accuracy_ok;

    report "  latency         : " & integer'image(latency) & " cycles";
    report "  max error       : " & real'image(max_error) & " LSB";
    report "  rms error       : " & real'image(rms_error) & " LSB";
    report "  snr             : " & real'image(snr_db) & " dB";
    if all_ok then
      report "  status          : OK";
    else
      report "  status          : KO" severity warning;
    end if;

    -- ------------------------------------------------------------------
    -- Export the results
    -- ------------------------------------------------------------------
    file_open(status, results_out, RESULT_FILE, write_mode);
    if status /= open_ok then
      report "Could not open result file '" & RESULT_FILE & "'" severity error;
    else
      write(l, string'("width: ") & integer'image(WIDTH));
      writeline(results_out, l);
      write(l, string'("iterations: ") & integer'image(ITERATIONS));
      writeline(results_out, l);
      write(l, string'("cycles: ") & integer'image(cycle));
      writeline(results_out, l);
      write(l, string'("latency_cycles: ") & integer'image(latency));
      writeline(results_out, l);
      write_yaml_real(l, results_out, "throughput", throughput);
      write(l, string'("vectors: ") & integer'image(received));
      writeline(results_out, l);
      write_yaml_real(l, results_out, "error_tolerance_lsb", tolerance);
      write_yaml_real(l, results_out, "max_error_lsb", max_error);
      write_yaml_real(l, results_out, "rms_error_lsb", rms_error);
      write_yaml_real(l, results_out, "mean_error_lsb", mean_error);
      write_yaml_real(l, results_out, "max_angle_error_deg", max_angle_error_deg);
      write_yaml_real(l, results_out, "rms_angle_error_deg", rms_angle_error_deg);
      write_yaml_real(l, results_out, "snr_db", snr_db);
      write_yaml_real(l, results_out, "enob", enob);
      write_yaml_real(l, results_out, "worst_case_angle_deg", worst_angle_deg);
      write(l, string'("checks_total: ") & integer'image(received));
      writeline(results_out, l);
      write(l, string'("checks_passed: ") & integer'image(checks_passed));
      writeline(results_out, l);
      write(l, string'("checks_failed: ") & integer'image(received - checks_passed));
      writeline(results_out, l);
      if received > 0 then
        write_yaml_real(l, results_out, "pass_rate",
                        100.0 * real(checks_passed) / real(received));
      else
        write_yaml_real(l, results_out, "pass_rate", 0.0);
      end if;

      if reset_ok then
        write(l, string'("reset: OK"));
      else
        write(l, string'("reset: KO"));
      end if;
      writeline(results_out, l);
      if latency_ok then
        write(l, string'("latency_check: OK"));
      else
        write(l, string'("latency_check: KO"));
      end if;
      writeline(results_out, l);
      if completeness_ok then
        write(l, string'("completeness: OK"));
      else
        write(l, string'("completeness: KO"));
      end if;
      writeline(results_out, l);
      if accuracy_ok then
        write(l, string'("accuracy: OK"));
      else
        write(l, string'("accuracy: KO"));
      end if;
      writeline(results_out, l);
      if all_ok then
        write(l, string'("status: OK"));
      else
        write(l, string'("status: KO"));
      end if;
      writeline(results_out, l);
      file_close(results_out);
    end if;

    report_progress(100);

    -- Stop the clock, which ends the simulation
    running <= false;
    wait;
  end process stimulus;

end architecture Behavioral;
