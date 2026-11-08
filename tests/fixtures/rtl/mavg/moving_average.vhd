-- Moving average over 2**DEPTH_LOG2 samples
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity moving_average is
  generic (
    WIDTH      : integer := 12;
    DEPTH_LOG2 : integer := 3
  );
  port (
    clock_in  : in  std_logic;
    areset_n  : in  std_logic;
    sample_in : in  std_logic_vector(WIDTH-1 downto 0);
    valid_in  : in  std_logic;
    mean_out  : out std_logic_vector(WIDTH-1 downto 0)
  );
end entity;

architecture rtl of moving_average is
  constant DEPTH : integer := 2**DEPTH_LOG2;
  type window_t is array (0 to DEPTH-1) of unsigned(WIDTH-1 downto 0);
  signal window : window_t;
  signal sum    : unsigned(WIDTH+DEPTH_LOG2-1 downto 0);
begin
  process (clock_in, areset_n)
  begin
    if areset_n = '0' then
      window <= (others => (others => '0'));
      sum    <= (others => '0');
    elsif rising_edge(clock_in) then
      if valid_in = '1' then
        window <= unsigned(sample_in) & window(0 to DEPTH-2);
        sum    <= sum + unsigned(sample_in) - window(DEPTH-1);
      end if;
    end if;
  end process;
  mean_out <= std_logic_vector(sum(WIDTH+DEPTH_LOG2-1 downto DEPTH_LOG2));
end architecture;
