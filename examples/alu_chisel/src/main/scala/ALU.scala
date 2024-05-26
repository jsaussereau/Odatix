import chisel3._
import chisel3.util._
import pck_control.ALUOp

class ALU(BITS: Int) extends Module {
  val io = IO(new Bundle {
    val i_sel_op = Input(ALUOp())
    val i_op_a   = Input(UInt(BITS.W))
    val i_op_b   = Input(UInt(BITS.W))
    val o_res    = Output(UInt(BITS.W))
  })

  val value = RegInit(0.U(BITS.W))

  switch(io.i_sel_op) {
    is (ALUOp.alu_add)  { value := io.i_op_a + io.i_op_b }
    is (ALUOp.alu_sub)  { value := io.i_op_a - io.i_op_b }
    is (ALUOp.alu_and)  { value := io.i_op_a & io.i_op_b }
    is (ALUOp.alu_or)   { value := io.i_op_a | io.i_op_b }
    is (ALUOp.alu_xor)  { value := io.i_op_a ^ io.i_op_b }
    is (ALUOp.alu_slt)  { value := io.i_op_a.asSInt < io.i_op_b.asSInt }
    is (ALUOp.alu_sltu) { value := io.i_op_a < io.i_op_b }
    is (ALUOp.alu_sll)  { value := io.i_op_a << io.i_op_b(log2Ceil(BITS)-1, 0) }
    is (ALUOp.alu_srl)  { value := io.i_op_a >> io.i_op_b(log2Ceil(BITS)-1, 0) }
    is (ALUOp.alu_sra)  { value := (io.i_op_a.asSInt >> io.i_op_b(log2Ceil(BITS)-1, 0)).asUInt }
    is (ALUOp.alu_cpa)  { value := io.i_op_a }
    is (ALUOp.alu_cpb)  { value := io.i_op_b }
    is (ALUOp.alu_nop)  { value := 0.U }
  }

  io.o_res := value
}
