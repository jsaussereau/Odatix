package synthetix

import chisel3._
import chisel3.util._
import _root_.circt.stage.{ChiselStage}
import scala.math._

object Quadrant extends Enumeration {
  type Quadrant = Value
  val QUARTER, HALF, FULL = Value
}
import Quadrant._

class Rom(
  DATA_BITS: Int, 
  ADDR_BITS: Int,
  QUADRANT: Quadrant,
  REGISTER_INPUT: Boolean = true,
  ROM_CONTENT: Seq[Int]
) extends Module {
  override val desiredName = s"rom"

  // IOs definition
  val i_addr  = IO(Input(UInt(ADDR_BITS.W)))
  val o_data  = QUADRANT match {
    case Quadrant.FULL => IO(Output(SInt(DATA_BITS.W)))
    case _             => IO(Output(UInt(DATA_BITS.W)))
  }

  // ROM
  val rom_vec = QUADRANT match {
    case Quadrant.FULL => VecInit(ROM_CONTENT.map(_.S(DATA_BITS.W)))
    case _             => VecInit(ROM_CONTENT.map(_.U(DATA_BITS.W)))
  }

  // Registers
  val addr_reg = if (REGISTER_INPUT) RegNext(i_addr) else i_addr
  val data_reg = QUADRANT match {
    case Quadrant.FULL => RegInit(0.S(DATA_BITS.W))
    case _             => RegInit(0.U(DATA_BITS.W))
  }

  data_reg := rom_vec(addr_reg)
  o_data := data_reg
}

object Rom extends App {
  // Parameters
  val data_bits = 8 // Data width
  val addr_bits = 8 // Address width
  val quadrant = Quadrant.FULL // Quadrant type
  val register_input = true // Register input signal

  // Derived parameters
  val depth = 1 << addr_bits
  val max_val = (1 << data_bits) - 1

  // ROM content generation
  val rom_content = quadrant match {
    case Quadrant.QUARTER =>
      // 0 to Pi/2
      (0 until depth).map { i =>
        val angle = (math.Pi / 2) * i / (depth - 1)
        val value = (math.sin(angle) * max_val).round.toInt
        value
      }
    case Quadrant.HALF =>
      // 0 to Pi
      (0 until depth).map { i =>
        val angle = math.Pi * i / (depth - 1)
        val value = (math.sin(angle) * max_val).round.toInt
        value
      }
    case Quadrant.FULL =>
      // 0 to 2*Pi
      (0 until depth).map { i =>
        val angle = (2 * math.Pi) * i / (depth - 1)
        val value = (math.sin(angle) * max_val).round.toInt
        value
      }
  }

  // Emit Verilog
  _root_.circt.stage.ChiselStage.emitSystemVerilog(
    new Rom(
      data_bits,
      addr_bits,
      quadrant,
      register_input,
      rom_content
    ),
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