library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use std.textio.all;

entity tb_counter is
  generic (
    BITS : integer := 8
  );
end entity tb_counter;

architecture Behavioral of tb_counter is
  -- Constants
  constant PERIOD : time := 10 ns;
  constant RESULT_FILE : string := "./results.yml";

  -- Signals
  signal clock     : std_logic := '0';
  signal reset     : std_logic := '0';
  signal i_init    : std_logic := '0';
  signal i_inc_dec : std_logic := '0';
  signal o_value   : std_logic_vector(BITS-1 downto 0);

  -- Write the testbench results as a flat yaml file, so that Odatix can
  -- extract them as metrics (see _metrics.yml of this simulation)
  procedure write_yaml_results(
    path          : in string;
    cycles        : in integer;
    reset_ok      : in boolean;
    increment_ok  : in boolean;
    decrement_ok  : in boolean;
    init_ok       : in boolean
  ) is
    file results_out : text open write_mode is path;
    variable l : line;
    variable checks_passed : integer := 0;

    procedure write_status(name : in string; value : in boolean) is
    begin
      if value then
        write(l, name & ": OK");
      else
        write(l, name & ": KO");
      end if;
      writeline(results_out, l);
    end procedure;
  begin
    if reset_ok then checks_passed := checks_passed + 1; end if;
    if increment_ok then checks_passed := checks_passed + 1; end if;
    if decrement_ok then checks_passed := checks_passed + 1; end if;
    if init_ok then checks_passed := checks_passed + 1; end if;

    write(l, string'("cycles: ") & integer'image(cycles));
    writeline(results_out, l);
    write(l, string'("checks_total: 4"));
    writeline(results_out, l);
    write(l, string'("checks_passed: ") & integer'image(checks_passed));
    writeline(results_out, l);
    write(l, string'("checks_failed: ") & integer'image(4 - checks_passed));
    writeline(results_out, l);
    if checks_passed = 4 then
      write(l, string'("status: OK"));
    else
      write(l, string'("status: KO"));
    end if;
    writeline(results_out, l);

    write_status("reset", reset_ok);
    write_status("increment", increment_ok);
    write_status("decrement", decrement_ok);
    write_status("initialization", init_ok);

    file_close(results_out);
  end procedure;

begin

  -- Instantiate the counter
  uut: entity work.counter
    generic map (
      BITS => BITS
    )
    port map (
      clock     => clock,
      reset     => reset,
      i_init    => i_init,
      i_inc_dec => i_inc_dec,
      o_value   => o_value
    );

  -- Clock generation
  clock <= not clock after PERIOD/2;

  -- Stimulus process
  stimulus: process
    variable reset_ok     : boolean := true;
    variable increment_ok : boolean := true;
    variable decrement_ok : boolean := true;
    variable init_ok      : boolean := true;
    variable cycle_count  : integer := 0;

    procedure tick(n : in integer) is
    begin
      wait for n*PERIOD;
      cycle_count := cycle_count + n;
    end procedure;
  begin
    -- Test case 1: Initialize counter
    reset <= '1';
    i_init <= '0';
    i_inc_dec <= '1';
    tick(1);

    -- Check reset
    if unsigned(o_value) = 0 then
      report "Reset OK";
    else
      reset_ok := false;
      report "Reset KO";
    end if;
    reset <= '0';

    -- Check incrementation
    tick(1);
    if unsigned(o_value) /= 1 then
      increment_ok := false;
      report "Increment KO: Expected = 1" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    tick(1);
    if unsigned(o_value) /= 2 then
      increment_ok := false;
      report "Increment KO: Expected = 2" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    tick(1);
    if unsigned(o_value) /= 3 then
      increment_ok := false;
      report "Increment KO: Expected = 3" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    if increment_ok then
      report "Increment OK";
    end if;

    -- Check decrementation
    i_inc_dec <= '0';
    tick(1);
    if unsigned(o_value) /= 2 then
      decrement_ok := false;
      report "Decrement KO: Expected = 2" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    tick(1);
    if unsigned(o_value) /= 1 then
      decrement_ok := false;
      report "Decrement KO: Expected = 1" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    tick(1);
    if unsigned(o_value) /= 0 then
      decrement_ok := false;
      report "Decrement KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    if decrement_ok then
      report "Decrement OK";
    end if;
    i_inc_dec <= '1';
    i_init <= '1';

    -- Check initialization
    tick(1);
    if unsigned(o_value) /= 0 then
      init_ok := false;
      report "Initialization KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    tick(1);
    if unsigned(o_value) /= 0 then
      init_ok := false;
      report "Initialization KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    tick(1);
    if unsigned(o_value) /= 0 then
      init_ok := false;
      report "Initialization KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    if init_ok then
      report "Initialization OK";
    end if;
    i_init <= '0';

    -- Export the results
    write_yaml_results(RESULT_FILE, cycle_count, reset_ok, increment_ok, decrement_ok, init_ok);

    -- Stop simulation
    wait;
  end process stimulus;
end architecture Behavioral;
