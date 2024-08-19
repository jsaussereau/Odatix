`include "pck_control.sv"

module alu 
  import pck_control::*;
#(
  parameter BITS = 8
)(
  input  wire            i_clk,
  input  wire            i_rst,
  input  sel_alu_op_e    i_sel_op,
  input  wire [BITS-1:0] i_op_a,
  input  wire [BITS-1:0] i_op_b,
  output wire [BITS-1:0] o_res
);

  reg [BITS-1:0] value;

  localparam int SHIFT_BITS = $clog2(BITS);

  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      value <= 0;
    end else begin
      case (i_sel_op)
        alu_add  : value <= i_op_a + i_op_b;
        alu_sub  : value <= i_op_a - i_op_b;
        alu_and  : value <= i_op_a & i_op_b;
        alu_or   : value <= i_op_a | i_op_b;
        alu_xor  : value <= i_op_a ^ i_op_b;
        alu_slt  : value <= ($signed(i_op_a) < $signed(i_op_b)) ? 1 : 0; 
        alu_sltu : value <= (i_op_a < i_op_b) ? 1 : 0;
        alu_sll  : value <= i_op_a << i_op_b[SHIFT_BITS-1:0];
        alu_srl  : value <= i_op_a >> i_op_b[SHIFT_BITS-1:0];
        alu_sra  : value <= $signed(i_op_a) >>> i_op_b[SHIFT_BITS-1:0];
        alu_cpa  : value <= i_op_a;
        alu_cpb  : value <= i_op_b;
        default  : value <= 0;
      endcase
    end
  end

  assign o_res = value;

endmodule
