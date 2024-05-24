package example

import chisel3._
import chisel3.util._
import _root_.circt.stage.{ChiselStage}

class Counter(bits: Int) extends Module {
  val io = IO(new Bundle {
    val i_clk     = Input(Clock())
    val i_rst     = Input(Bool())
    val i_init    = Input(Bool())
    val i_inc_dec = Input(Bool())
    val o_value   = Output(UInt(bits.W))
  })

  // Create a register to hold the counter value
  val counter = RegInit(0.U(bits.W))

  // Define the behavior of the counter
  when (io.i_rst) {
    counter := 0.U
  } .elsewhen (io.i_init) {
    counter := 0.U
  } .otherwise {
    when (io.i_inc_dec) {
      counter := counter + 1.U
    } .otherwise {
      counter := counter - 1.U
    }
  }

  // Connect the output
  io.o_value := counter
}

// Objet pour générer le SystemVerilog du module Counter
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