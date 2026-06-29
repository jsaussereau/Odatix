package synthetix

import chisel3._
import chisel3.util._
import _root_.circt.stage.{ChiselStage}

class Counter(BITS: Int) extends Module {
  override val desiredName = s"counter"

  val i_init    = IO(Input(Bool()))
  val i_inc_dec = IO(Input(Bool()))
  val i_inc_val = IO(Input(UInt(BITS.W)))
  val o_value   = IO(Output(UInt(BITS.W)))

  val value = RegInit(0.U(BITS.W))

  when (i_init) {
    value := 0.U
  } .otherwise {
    when (i_inc_dec) {
      value := value + i_inc_val
    } .otherwise {
      value := value - i_inc_val
    }
  }

  o_value := value

}

object Counter extends App {
  _root_.circt.stage.ChiselStage.emitSystemVerilog(
    new Counter(8),
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