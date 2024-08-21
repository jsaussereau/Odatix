package pck_control

import chisel3._
import chisel3.util._

object ALUOp extends ChiselEnum {
  val alu_nop  = Value(0.U)
  val alu_add  = Value(1.U)
  val alu_sub  = Value(2.U)
  val alu_and  = Value(3.U)
  val alu_or   = Value(4.U)
  val alu_xor  = Value(5.U)
  val alu_slt  = Value(6.U)
  val alu_sltu = Value(7.U)
  val alu_sll  = Value(8.U)
  val alu_srl  = Value(9.U)
  val alu_sra  = Value(10.U)
  val alu_cpa  = Value(11.U)
  val alu_cpb  = Value(12.U)
}
