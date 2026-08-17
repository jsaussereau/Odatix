package example

import chisel3._
import chisel3.util._
import _root_.circt.stage.{ChiselStage}

class Counter(BITS: Int) extends Module {
  override val desiredName = s"counter"

  val i_init    = IO(Input(Bool()))
  val i_inc_dec = IO(Input(Bool()))
  val o_value   = IO(Output(UInt(BITS.W)))

  val value = RegInit(0.U(BITS.W))

  when (i_init) {
    value := 0.U
  } .otherwise {
    when (i_inc_dec) {
      value := value + 1.U
    } .otherwise {
      value := value - 1.U
    }
  }

  o_value := value

}

object Counter extends App {
  // The counter width comes from the command line ("--width 8") instead of being
  // replaced in this file: Odatix fills it in from the "width" variable of the
  // architecture settings, one run per value.
  val DEFAULT_BITS = 8

  val widthIndex = args.indexOf("--width")
  val bits =
    if (widthIndex >= 0 && widthIndex + 1 < args.length) args(widthIndex + 1).toInt
    else DEFAULT_BITS

  // Everything else is passed on to firtool, "--width <n>" excluded.
  val firtoolArgs =
    if (widthIndex >= 0) args.patch(widthIndex, Nil, 2)
    else args

  _root_.circt.stage.ChiselStage.emitSystemVerilog(
    new Counter(bits),
    firtoolOpts = Array.concat(
      Array(
        "--disable-all-randomization",
        "--strip-debug-info",
        "--split-verilog"
      ),
      firtoolArgs
    )
  )
}
