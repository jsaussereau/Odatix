library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity counter is
  generic (
    BITS : integer := 8
  );
  port (
    i_clk      : in  std_logic;
    i_rst      : in  std_logic;
    i_init     : in  std_logic;
    i_inc_dec  : in  std_logic;
    o_value    : out std_logic_vector(BITS-1 downto 0)
  );
end entity counter;

architecture Behavioral of counter is
  signal counter : unsigned(BITS-1 downto 0);
begin
  process(i_clk)
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        counter <= (others => '0');
      else
        if i_init = '1' then
          counter <= (others => '0');
        else
          if i_inc_dec = '1' then
            counter <= counter + 1;
          else
            counter <= counter - 1;
          end if;
        end if;
      end if;
    end if;
  end process;

  o_value <= std_logic_vector(counter);

end architecture Behavioral;
