library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity counter is
  generic (
    BITS : integer := 8
  );
  port (
    clock      : in  std_logic;
    reset      : in  std_logic;
    i_init     : in  std_logic;
    i_inc_dec  : in  std_logic;
    o_value    : out std_logic_vector(BITS-1 downto 0)
  );
end entity counter;

architecture Behavioral of counter is
  signal value : unsigned(BITS-1 downto 0);
begin
  process(clock)
  begin
    if rising_edge(clock) then
      if reset = '1' then
        value <= (others => '0');
      else
        if i_init = '1' then
          value <= (others => '0');
        else
          if i_inc_dec = '1' then
            value <= value + 1;
          else
            value <= value - 1;
          end if;
        end if;
      end if;
    end if;
  end process;

  o_value <= std_logic_vector(value);

end architecture Behavioral;
