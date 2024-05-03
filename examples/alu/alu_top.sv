`include "pck_control.sv"

module alu_top 
  import pck_control::*; 
# (
  parameter BITS = 8
)(
  input  wire            i_clk,
  input  wire            i_rst,
  input  wire      [4:0] i_sel_op,
  input  wire [BITS-1:0] i_op_a,
  input  wire [BITS-1:0] i_op_b,
  output wire [BITS-1:0] o_res
);

  reg [BITS-1:0] op_a;
  reg [BITS-1:0] op_b;
  sel_alu_op_e   sel_op_e;
  sel_alu_op_e   sel_op;

  always_comb begin
    case (i_sel_op)
      4'h1    : sel_op_e = alu_add;
      4'h2    : sel_op_e = alu_sub;
      4'h3    : sel_op_e = alu_and;
      4'h4    : sel_op_e = alu_or;
      4'h5    : sel_op_e = alu_xor;
      4'h6    : sel_op_e = alu_slt;
      4'h7    : sel_op_e = alu_sltu;
      4'h8    : sel_op_e = alu_sll;
      4'h9    : sel_op_e = alu_srl;
      4'ha    : sel_op_e = alu_sra;
      4'hb    : sel_op_e = alu_cpa;
      4'hc    : sel_op_e = alu_cpb;
      default : sel_op_e = alu_nop;
    endcase
  end

  // register inputs
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      op_a <= 0;
      op_b <= 0;
      sel_op <= alu_nop;
    end else begin
      op_a <= i_op_a;
      op_b <= i_op_b;
      sel_op <= sel_op_e;
    end
  end

  alu #(
    .BITS     ( BITS   )
  ) inst_alu (
    .i_clk    ( i_clk  ),
    .i_rst    ( i_rst  ),
    .i_sel_op ( sel_op ),
    .i_op_a   ( op_a   ),
    .i_op_b   ( op_b   ),
    .o_res    ( o_res  )
  );
endmodule
