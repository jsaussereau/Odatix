
module mult #(
  parameter BITS = 8
)(
  input  wire            i_clk,
  input  wire            i_rst,
  input  wire [BITS-1:0] i_op_a,
  input  wire [BITS-1:0] i_op_b,
  output wire [BITS-1:0] o_res
);

  reg [BITS-1:0] op_a;
  reg [BITS-1:0] op_b;
  reg [BITS-1:0] value;

  // register inputs
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      op_a <= 0;
      op_b <= 0;
    end else begin
      op_a <= i_op_a;
      op_b <= i_op_b;
    end
  end

  // multiplier logic
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      value <= 0;
    end else begin
      value <= op_a * op_b;
    end
  end

  assign o_res = value;

endmodule
