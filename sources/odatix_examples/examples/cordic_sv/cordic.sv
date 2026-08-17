// **********************************************************************
//                                Odatix
// **********************************************************************
//
// Pipelined CORDIC rotation core (circular mode).
//
// Rotates the input vector (i_x, i_y) by the angle i_angle and outputs the
// rotated vector (o_x, o_y), scaled by the CORDIC gain (~1.6468).
//
// The angle is encoded on 32 bits, with a full turn mapped to 2^32:
//   angle_rad = i_angle * 2*pi / 2^32
// This makes the [-180 deg, +180 deg[ range map exactly to the signed 32-bit
// range, and lets the argument reduction be a simple test on the two MSBs.
//
// The core is fully pipelined: one result per clock cycle, with a latency of
// ITERATIONS + 2 cycles (1 cycle for the argument reduction, ITERATIONS cycles
// for the rotation stages, 1 cycle for the output register).
//
// The two parameters trade accuracy for area and latency, which makes this
// design a good candidate for a parameter sweep:
//   - WIDTH:      datapath width, sets the quantization floor
//   - ITERATIONS: number of rotation stages, sets the angular resolution

module cordic #(
  parameter WIDTH = 16,
  parameter ITERATIONS = 12
)(
  input  wire                     clock,
  input  wire                     reset,
  input  wire                     i_valid,
  input  wire signed [WIDTH-1:0]  i_x,
  input  wire signed [WIDTH-1:0]  i_y,
  input  wire signed [31:0]       i_angle,
  output wire                     o_valid,
  output wire signed [WIDTH-1:0]  o_x,
  output wire signed [WIDTH-1:0]  o_y
);

  // Two guard bits absorb the CORDIC gain (~1.65) without overflowing
  localparam int IW = WIDTH + 2;

  // atan(2^-i), in the same angle encoding as i_angle
  function automatic signed [31:0] atan_lut(input int i);
    case (i)
      0:  atan_lut = 32'sd536870912;
      1:  atan_lut = 32'sd316933406;
      2:  atan_lut = 32'sd167458907;
      3:  atan_lut = 32'sd85004756;
      4:  atan_lut = 32'sd42667331;
      5:  atan_lut = 32'sd21354465;
      6:  atan_lut = 32'sd10679838;
      7:  atan_lut = 32'sd5340245;
      8:  atan_lut = 32'sd2670163;
      9:  atan_lut = 32'sd1335087;
      10: atan_lut = 32'sd667544;
      11: atan_lut = 32'sd333772;
      12: atan_lut = 32'sd166886;
      13: atan_lut = 32'sd83443;
      14: atan_lut = 32'sd41722;
      15: atan_lut = 32'sd20861;
      16: atan_lut = 32'sd10430;
      17: atan_lut = 32'sd5215;
      18: atan_lut = 32'sd2608;
      19: atan_lut = 32'sd1304;
      20: atan_lut = 32'sd652;
      21: atan_lut = 32'sd326;
      22: atan_lut = 32'sd163;
      23: atan_lut = 32'sd81;
      default: atan_lut = 32'sd0;
    endcase
  endfunction

  // Pipeline registers: stage 0 holds the argument reduction result
  logic signed [IW-1:0]  x_pipe [0:ITERATIONS];
  logic signed [IW-1:0]  y_pipe [0:ITERATIONS];
  logic signed [31:0]    z_pipe [0:ITERATIONS];
  logic                  v_pipe [0:ITERATIONS];

  // ------------------------------------------------------------------
  // Argument reduction: bring the angle back into [-90 deg, +90 deg]
  // ------------------------------------------------------------------
  wire signed [IW-1:0] x_ext = IW'(i_x);
  wire signed [IW-1:0] y_ext = IW'(i_y);

  always_ff @(posedge clock) begin
    if (reset) begin
      x_pipe[0] <= '0;
      y_pipe[0] <= '0;
      z_pipe[0] <= '0;
      v_pipe[0] <= 1'b0;
    end else begin
      v_pipe[0] <= i_valid;
      case (i_angle[31:30])
        // [+90 deg, +180 deg[ : pre-rotate by +90 deg
        2'b01: begin
          x_pipe[0] <= -y_ext;
          y_pipe[0] <= x_ext;
          z_pipe[0] <= i_angle - 32'sh4000_0000;
        end
        // [-180 deg, -90 deg[ : pre-rotate by -90 deg
        2'b10: begin
          x_pipe[0] <= y_ext;
          y_pipe[0] <= -x_ext;
          z_pipe[0] <= i_angle + 32'sh4000_0000;
        end
        // already within [-90 deg, +90 deg[
        default: begin
          x_pipe[0] <= x_ext;
          y_pipe[0] <= y_ext;
          z_pipe[0] <= i_angle;
        end
      endcase
    end
  end

  // ------------------------------------------------------------------
  // Rotation stages
  // ------------------------------------------------------------------
  genvar i;
  generate
    for (i = 0; i < ITERATIONS; i++) begin : gen_stage
      wire signed [IW-1:0] x_shifted = x_pipe[i] >>> i;
      wire signed [IW-1:0] y_shifted = y_pipe[i] >>> i;
      wire                 negative  = z_pipe[i][31];

      always_ff @(posedge clock) begin
        if (reset) begin
          x_pipe[i+1] <= '0;
          y_pipe[i+1] <= '0;
          z_pipe[i+1] <= '0;
          v_pipe[i+1] <= 1'b0;
        end else begin
          v_pipe[i+1] <= v_pipe[i];
          if (negative) begin
            // rotate clockwise
            x_pipe[i+1] <= x_pipe[i] + y_shifted;
            y_pipe[i+1] <= y_pipe[i] - x_shifted;
            z_pipe[i+1] <= z_pipe[i] + atan_lut(i);
          end else begin
            // rotate counter-clockwise
            x_pipe[i+1] <= x_pipe[i] - y_shifted;
            y_pipe[i+1] <= y_pipe[i] + x_shifted;
            z_pipe[i+1] <= z_pipe[i] - atan_lut(i);
          end
        end
      end
    end
  endgenerate

  // ------------------------------------------------------------------
  // Output register (saturating, so a gain overflow does not wrap around)
  // ------------------------------------------------------------------
  function automatic signed [WIDTH-1:0] saturate(input signed [IW-1:0] value);
    localparam signed [IW-1:0] MAX_VAL = IW'((1 <<< (WIDTH-1)) - 1);
    localparam signed [IW-1:0] MIN_VAL = -IW'(1 <<< (WIDTH-1));
    if (value > MAX_VAL) begin
      saturate = WIDTH'(MAX_VAL);
    end else if (value < MIN_VAL) begin
      saturate = WIDTH'(MIN_VAL);
    end else begin
      saturate = WIDTH'(value);
    end
  endfunction

  logic signed [WIDTH-1:0] x_out;
  logic signed [WIDTH-1:0] y_out;
  logic                    valid_out;

  always_ff @(posedge clock) begin
    if (reset) begin
      x_out     <= '0;
      y_out     <= '0;
      valid_out <= 1'b0;
    end else begin
      x_out     <= saturate(x_pipe[ITERATIONS]);
      y_out     <= saturate(y_pipe[ITERATIONS]);
      valid_out <= v_pipe[ITERATIONS];
    end
  end

  assign o_x     = x_out;
  assign o_y     = y_out;
  assign o_valid = valid_out;

endmodule
