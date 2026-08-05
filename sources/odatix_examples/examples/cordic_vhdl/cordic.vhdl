-- **********************************************************************
--                                Odatix
-- **********************************************************************
--
-- Pipelined CORDIC rotation core (circular mode).
--
-- Rotates the input vector (i_x, i_y) by the angle i_angle and outputs the
-- rotated vector (o_x, o_y), scaled by the CORDIC gain (~1.6468).
--
-- The angle is encoded on 32 bits, with a full turn mapped to 2^32:
--   angle_rad = i_angle * 2*pi / 2^32
-- This makes the [-180 deg, +180 deg[ range map exactly to the signed 32-bit
-- range, and lets the argument reduction be a simple test on the two MSBs.
--
-- The core is fully pipelined: one result per clock cycle, with a latency of
-- ITERATIONS + 2 cycles (1 cycle for the argument reduction, ITERATIONS cycles
-- for the rotation stages, 1 cycle for the output register).
--
-- The two generics trade accuracy for area and latency, which makes this
-- design a good candidate for a parameter sweep:
--   - WIDTH:      datapath width, sets the quantization floor
--   - ITERATIONS: number of rotation stages, sets the angular resolution
--
-- This is the VHDL counterpart of examples/cordic_sv/cordic.sv.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity cordic is
  generic (
    WIDTH : integer := 16;
    ITERATIONS : integer := 12
  );
  port (
    clock   : in  std_logic;
    reset   : in  std_logic;
    i_valid : in  std_logic;
    i_x     : in  std_logic_vector(WIDTH-1 downto 0);
    i_y     : in  std_logic_vector(WIDTH-1 downto 0);
    i_angle : in  std_logic_vector(31 downto 0);
    o_valid : out std_logic;
    o_x     : out std_logic_vector(WIDTH-1 downto 0);
    o_y     : out std_logic_vector(WIDTH-1 downto 0)
  );
end entity cordic;

architecture Behavioral of cordic is

  -- Two guard bits absorb the CORDIC gain (~1.65) without overflowing
  constant IW : integer := WIDTH + 2;

  -- A quarter turn, in the angle encoding of i_angle
  constant QUARTER_TURN : signed(31 downto 0) := to_signed(1073741824, 32);

  -- atan(2^-i), in the same angle encoding as i_angle
  type atan_lut_t is array (0 to 23) of signed(31 downto 0);
  constant ATAN_LUT : atan_lut_t := (
    to_signed(536870912, 32),
    to_signed(316933406, 32),
    to_signed(167458907, 32),
    to_signed(85004756, 32),
    to_signed(42667331, 32),
    to_signed(21354465, 32),
    to_signed(10679838, 32),
    to_signed(5340245, 32),
    to_signed(2670163, 32),
    to_signed(1335087, 32),
    to_signed(667544, 32),
    to_signed(333772, 32),
    to_signed(166886, 32),
    to_signed(83443, 32),
    to_signed(41722, 32),
    to_signed(20861, 32),
    to_signed(10430, 32),
    to_signed(5215, 32),
    to_signed(2608, 32),
    to_signed(1304, 32),
    to_signed(652, 32),
    to_signed(326, 32),
    to_signed(163, 32),
    to_signed(81, 32)
  );

  -- Beyond the table the rotation step is below the angle resolution
  function atan_value(i : integer) return signed is
  begin
    if i <= ATAN_LUT'high then
      return ATAN_LUT(i);
    else
      return to_signed(0, 32);
    end if;
  end function;

  -- Saturating narrowing, so that a gain overflow does not wrap around
  function saturate(value : signed; w : integer) return signed is
    constant MAX_VAL : signed(value'length-1 downto 0) := to_signed(2**(w-1) - 1, value'length);
    constant MIN_VAL : signed(value'length-1 downto 0) := -to_signed(2**(w-1), value'length);
  begin
    if value > MAX_VAL then
      return resize(MAX_VAL, w);
    elsif value < MIN_VAL then
      return resize(MIN_VAL, w);
    else
      return resize(value, w);
    end if;
  end function;

  -- Pipeline registers: stage 0 holds the argument reduction result
  type data_pipe_t is array (0 to ITERATIONS) of signed(IW-1 downto 0);
  type angle_pipe_t is array (0 to ITERATIONS) of signed(31 downto 0);

  signal x_pipe : data_pipe_t;
  signal y_pipe : data_pipe_t;
  signal z_pipe : angle_pipe_t;
  signal v_pipe : std_logic_vector(0 to ITERATIONS);

  signal x_out     : signed(WIDTH-1 downto 0);
  signal y_out     : signed(WIDTH-1 downto 0);
  signal valid_out : std_logic;

begin

  -- ------------------------------------------------------------------
  -- Argument reduction: bring the angle back into [-90 deg, +90 deg]
  -- ------------------------------------------------------------------
  argument_reduction : process(clock)
    variable x_ext : signed(IW-1 downto 0);
    variable y_ext : signed(IW-1 downto 0);
  begin
    if rising_edge(clock) then
      if reset = '1' then
        x_pipe(0) <= (others => '0');
        y_pipe(0) <= (others => '0');
        z_pipe(0) <= (others => '0');
        v_pipe(0) <= '0';
      else
        x_ext := resize(signed(i_x), IW);
        y_ext := resize(signed(i_y), IW);
        v_pipe(0) <= i_valid;
        case i_angle(31 downto 30) is
          -- [+90 deg, +180 deg[ : pre-rotate by +90 deg
          when "01" =>
            x_pipe(0) <= -y_ext;
            y_pipe(0) <= x_ext;
            z_pipe(0) <= signed(i_angle) - QUARTER_TURN;
          -- [-180 deg, -90 deg[ : pre-rotate by -90 deg
          when "10" =>
            x_pipe(0) <= y_ext;
            y_pipe(0) <= -x_ext;
            z_pipe(0) <= signed(i_angle) + QUARTER_TURN;
          -- already within [-90 deg, +90 deg[
          when others =>
            x_pipe(0) <= x_ext;
            y_pipe(0) <= y_ext;
            z_pipe(0) <= signed(i_angle);
        end case;
      end if;
    end if;
  end process;

  -- ------------------------------------------------------------------
  -- Rotation stages
  -- ------------------------------------------------------------------
  gen_stage : for i in 0 to ITERATIONS-1 generate
    stage : process(clock)
      variable x_shifted : signed(IW-1 downto 0);
      variable y_shifted : signed(IW-1 downto 0);
    begin
      if rising_edge(clock) then
        if reset = '1' then
          x_pipe(i+1) <= (others => '0');
          y_pipe(i+1) <= (others => '0');
          z_pipe(i+1) <= (others => '0');
          v_pipe(i+1) <= '0';
        else
          x_shifted := shift_right(x_pipe(i), i);
          y_shifted := shift_right(y_pipe(i), i);
          v_pipe(i+1) <= v_pipe(i);
          if z_pipe(i)(31) = '1' then
            -- rotate clockwise
            x_pipe(i+1) <= x_pipe(i) + y_shifted;
            y_pipe(i+1) <= y_pipe(i) - x_shifted;
            z_pipe(i+1) <= z_pipe(i) + atan_value(i);
          else
            -- rotate counter-clockwise
            x_pipe(i+1) <= x_pipe(i) - y_shifted;
            y_pipe(i+1) <= y_pipe(i) + x_shifted;
            z_pipe(i+1) <= z_pipe(i) - atan_value(i);
          end if;
        end if;
      end if;
    end process;
  end generate;

  -- ------------------------------------------------------------------
  -- Output register
  -- ------------------------------------------------------------------
  output_register : process(clock)
  begin
    if rising_edge(clock) then
      if reset = '1' then
        x_out     <= (others => '0');
        y_out     <= (others => '0');
        valid_out <= '0';
      else
        x_out     <= saturate(x_pipe(ITERATIONS), WIDTH);
        y_out     <= saturate(y_pipe(ITERATIONS), WIDTH);
        valid_out <= v_pipe(ITERATIONS);
      end if;
    end if;
  end process;

  o_x     <= std_logic_vector(x_out);
  o_y     <= std_logic_vector(y_out);
  o_valid <= valid_out;

end architecture Behavioral;
