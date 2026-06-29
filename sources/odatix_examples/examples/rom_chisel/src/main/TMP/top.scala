package synthetix

import chisel3._
import chisel3.util._

class Top(
  DATA_BITS: Int,
  ADDR_BITS: Int,
  ROM_CONTENT: Seq[Int]
) extends Module {
  override val desiredName = s"top"

  val o_data = IO(Output(SInt((DATA_BITS + 1).W))) // Add sign bit

  // FSM for quadrants
  val quadrant = RegInit(0.U(2.W)) // 2 bits for 4 quadrants

  // Use Counter module for address generation
  val counter = Module(new synthetix.Counter(ADDR_BITS))

  // Set counter direction based on quadrant
  counter.i_init := false.B
  counter.i_inc_val := 1.U
  counter.i_inc_dec := (quadrant === 0.U || quadrant === 2.U) // increment for 0 and 2, decrement for 1 and 3

  val addr_counter = counter.o_value

  // ROM instantiation
  val rom = Module(new synthetix.Rom(DATA_BITS, ADDR_BITS, ROM_CONTENT))
  rom.i_addr := addr_counter

  // ROM read
  val rom_data = rom.o_data.asUInt

  // Output calculation according to quadrant
  val sin_val = Wire(SInt((DATA_BITS + 1).W))
  when(quadrant === 2.U || quadrant === 3.U) {
    // Two's complement (negative)
    sin_val := -rom_data.asSInt
  } .otherwise {
    sin_val := rom_data.asSInt
  }

  o_data := sin_val

  // FSM and counter update
  when(
    (quadrant === 0.U || quadrant === 2.U) && addr_counter === (ROM_CONTENT.length - 1).U ||
    (quadrant === 1.U || quadrant === 3.U) && addr_counter === 0.U
  ) {
    counter.i_init := true.B // Reset counter
    quadrant := quadrant + 1.U
    when(quadrant === 3.U) {
      quadrant := 0.U
    }
  }
}

object Top extends App {
  val data_bits = 8 // Data width
  val addr_bits = 8 // Address width

  val depth = 1 << addr_bits
  val max_val = (1 << data_bits) - 1

  val rom_content = (0 until depth).map { i =>
    // 0 to Pi/2
    val angle = (math.Pi / 2) * i / (depth - 1)
    val value = (math.sin(angle) * max_val).round.toInt
    value
  }

  _root_.circt.stage.ChiselStage.emitSystemVerilog(
    new Top(data_bits, addr_bits, rom_content),
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