import chisel3._
import chisel3.util._

class ShiftRegister(BITS: Int) extends Module {
  val io = IO(new Bundle {
    val i_bit_in = Input(Bool())
    val i_right_nleft = Input(Bool())
    val o_value = Output(UInt(BITS.W))
  })

  val shift_reg = RegInit(0.U(BITS.W))

  when(io.i_right_nleft) {
    shift_reg := Cat(io.i_bit_in, shift_reg(BITS-1, 1))
  } .otherwise {
    shift_reg := Cat(shift_reg(BITS-2, 0), io.i_bit_in)
  }

  io.o_value := shift_reg
}

object ShiftRegister extends App {
  _root_.circt.stage.ChiselStage.emitSystemVerilog(
    new ShiftRegister(8),
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