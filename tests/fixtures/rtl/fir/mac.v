// Multiply-accumulate stage of the FIR filter
module mac #(
  parameter A_WIDTH = 16,
  parameter B_WIDTH = 12,
  parameter ACC_WIDTH = 32
)(
  input  wire                        clk,
  input  wire signed [A_WIDTH-1:0]   a,
  input  wire signed [B_WIDTH-1:0]   b,
  input  wire signed [ACC_WIDTH-1:0] acc_in,
  output reg  signed [ACC_WIDTH-1:0] acc_out
);
  always @(posedge clk)
    acc_out <= acc_in + a * b;
endmodule
