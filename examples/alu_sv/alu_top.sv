`include "pck_control.sv"

module alu_top 
  import pck_control::*; 
#(
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
  sel_alu_op_e   sel_op;

  // register inputs
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      op_a <= 0;
      op_b <= 0;
      sel_op <= alu_nop;
    end else begin
      op_a <= i_op_a;
      op_b <= i_op_b;
      sel_op <= sel_alu_op_e'(i_sel_op); 
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
