`ifndef __PCK_CONTROL__
`define __PCK_CONTROL__

package pck_control;

  typedef enum logic [3:0] {
    alu_nop,
    alu_add,
    alu_sub,
    alu_and,
    alu_or,
    alu_xor,
    alu_slt,
    alu_sltu,
    alu_sll,
    alu_srl,
    alu_sra,
    alu_cpa,
    alu_cpb
  } sel_alu_op_e;

endpackage

`endif