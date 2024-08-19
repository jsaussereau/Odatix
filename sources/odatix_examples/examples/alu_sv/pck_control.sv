`ifndef __PCK_CONTROL__
`define __PCK_CONTROL__

package pck_control;

  typedef enum logic [3:0] {
    alu_nop  = 4'd0,
    alu_add  = 4'd1,
    alu_sub  = 4'd2,
    alu_and  = 4'd3,
    alu_or   = 4'd4,
    alu_xor  = 4'd5,
    alu_slt  = 4'd6,
    alu_sltu = 4'd7,
    alu_sll  = 4'd8,
    alu_srl  = 4'd9,
    alu_sra  = 4'd10,
    alu_cpa  = 4'd11,
    alu_cpb  = 4'd12
  } sel_alu_op_e;

endpackage

`endif