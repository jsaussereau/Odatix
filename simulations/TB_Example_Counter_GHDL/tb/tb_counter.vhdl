library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_counter is
  generic (
    BITS : integer := 8
  );
end entity tb_counter;

architecture Behavioral of tb_counter is
  -- Constants
  constant PERIOD : time := 10 ns;

  -- Signals
  signal clock     : std_logic := '0';
  signal reset     : std_logic := '0';
  signal i_init    : std_logic := '0';
  signal i_inc_dec : std_logic := '0';
  signal o_value   : std_logic_vector(BITS-1 downto 0);

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
  begin
    -- Test case 1: Initialize counter
    reset <= '1';
    i_init <= '0';
    i_inc_dec <= '1';
    wait for PERIOD;

    -- Check reset
    if unsigned(o_value) = 0 then
      report "Reset OK";
    else
      report "Reset KO";
    end if;
    reset <= '0';

    -- Check incrementation
    wait for 1*PERIOD;
    if unsigned(o_value) = 1 then
      wait for 1*PERIOD;
      if unsigned(o_value) = 2 then
        wait for 1*PERIOD;
        if unsigned(o_value) = 3 then
          report "Increment OK";
        else
          report "Increment KO: Expected = 3" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
        end if;
      else
        report "Increment KO: Expected = 2" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
      end if;
    else
      report "Increment KO: Expected = 1" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;

    -- Check decrementation
    i_inc_dec <= '0';
    wait for 1*PERIOD;
    if unsigned(o_value) = 2 then
      wait for 1*PERIOD;
      if unsigned(o_value) = 1 then
        wait for 1*PERIOD;
        if unsigned(o_value) = 0 then
          report "Decrement OK";
        else
          report "Decrement KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
        end if;
      else
        report "Decrement KO: Expected = 1" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
      end if;
    else
      report "Decrement KO: Expected = 2" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;

    -- Check initialization    
    i_inc_dec <= '1';
    wait for 2*PERIOD;
    i_init <= '1';
    wait for 1*PERIOD;
    if unsigned(o_value) = 0 then
      wait for 1*PERIOD;
      if unsigned(o_value) = 0 then
        wait for 1*PERIOD;
        if unsigned(o_value) = 0 then
          report "Initialization OK";
        else
          report "Initialization KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
        end if;
      else
        report "Initialization KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
      end if;
    else
      report "Initialization KO: Expected = 0" & ", Received = " & integer'image(to_integer(unsigned(o_value)));
    end if;
    i_init <= '0';

    -- Stop simulation
    wait;
  end process stimulus;
end architecture Behavioral;
