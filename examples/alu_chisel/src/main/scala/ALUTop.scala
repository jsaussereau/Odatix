import chisel3._
import chisel3.util._
import pck_control.ALUOp

class ALUTop(BITS: Int) extends Module {
  val io = IO(new Bundle {
    val i_clk    = Input(Bool())
    val i_rst    = Input(Bool())
    val i_sel_op = Input(UInt(4.W))
    val i_op_a   = Input(UInt(BITS.W))
    val i_op_b   = Input(UInt(BITS.W))
    val o_res    = Output(UInt(BITS.W))
  })

  val op_a = RegInit(0.U(BITS.W))
  val op_b = RegInit(0.U(BITS.W))
  val sel_op = RegInit(ALUOp.alu_nop)

  when (io.i_rst) {
    op_a := 0.U
    op_b := 0.U
    sel_op := ALUOp.alu_nop
  } .otherwise {
    op_a := io.i_op_a
    op_b := io.i_op_b
    sel_op := ALUOp(io.i_sel_op)
  }

  val alu = Module(new ALU(BITS))
  alu.io.i_clk := io.i_clk
  alu.io.i_rst := io.i_rst
  alu.io.i_sel_op := sel_op
  alu.io.i_op_a := op_a
  alu.io.i_op_b := op_b
  io.o_res := alu.io.o_res
}

object ALUTop extends App {
  _root_.circt.stage.ChiselStage.emitSystemVerilog(
    new ALUTop(8),
    firtoolOpts = Array.concat(
      Array(
        "--disable-all-randomization",
        "--strip-debug-info",
        "--split-verilog"
      ),
      args
    )      
  )
}