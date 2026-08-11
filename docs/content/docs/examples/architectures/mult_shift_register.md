---
title: "Multiplier & Shift Register"
description: "Two minimal designs swept over the same widths — one that costs almost nothing and one that costs a lot — chosen to make the shape of a trade-off curve visible."
weight: 4
---

# Multiplier & Shift Register

These two examples are deliberately unremarkable as designs. They exist because a trade-off curve only means something **next to another one**, and the counter, the shift register, the ALU and the multiplier make a set of four `BITS` sweeps that behave very differently on the same target.

They also make a practical point about configurations: `Example_ALU_sv`, `Example_Shift_Register_sv` and `Example_Mult` all use `parameter BITS = <n>` as their substitution text, so **the same seven configuration files are reused verbatim** across three architectures.

{{< details title="What these examples demonstrate" >}}
- **Configuration files shared between architectures** — the same `04bits.txt` … `64bits.txt` content serves three different designs.
- **Two opposite cost profiles** — a shift register is wires and flip-flops, a multiplier is a whole array of adders.
- **Registered boundaries** — the multiplier registers its operands so that what is measured is the multiplier, not the I/O path.
- **A configuration that legitimately fails** — `Example_Mult/16bits` is documented as failing with Vivado, and is kept in the run settings on purpose.
- **A Chisel counterpart** — `Example_Shift_Register_chisel`, to compare a generated netlist against a hand-written one.
{{< /details >}}


{{< toc >}}

## Shift Register

### What the design does

A `BITS`-wide shift register with a direction input. On every rising edge, `i_bit_in` is inserted at one end and the register shifts towards the other, `i_right_nleft` choosing which:

{{< code lang=systemverilog filename="examples/shift_register_sv/shift_register.sv" >}}
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      shift_reg <= 0;
    end else begin
      if (i_right_nleft) begin
        shift_reg <= {i_bit_in, shift_reg[BITS-1:1]};
      end else begin
        shift_reg <= {shift_reg[BITS-2:0], i_bit_in};
      end
    end
  end
{{< /code >}}

{{< details title="Interface" >}}
| Port | Direction | Width | Role |
|---|---|---|---|
| `i_clk` | in | 1 | Clock, rising edge |
| `i_rst` | in | 1 | Synchronous reset, active high |
| `i_bit_in` | in | 1 | Bit shifted in |
| `i_right_nleft` | in | 1 | 1 = shift right, 0 = shift left |
| `o_value` | out | `BITS` | Register contents |
{{< /details >}}

This is the **cheapest possible** `BITS` sweep: `BITS` flip-flops, one 2-to-1 multiplexer per bit, and no carry, no comparison, nothing chained. The critical path is one multiplexer and is **independent of `BITS`**, which is why its fmax bounds are the highest of all the examples:

{{< code lang=yaml filename="architectures/Example_Shift_Register_sv/_settings.yml" >}}
xc7a100t-csg324-1:
  fmax_synthesis:
    lower_bound: 650
    upper_bound: 1000
xc7k70t-fbg676-2:
  fmax_synthesis:
    lower_bound: 450
    upper_bound: 2500
{{< /code >}}

Plotted against the counter and the ALU, it gives the **flat reference line** the other curves bend away from.

### Architecture settings

{{< code lang=yaml filename="architectures/Example_Shift_Register_sv/_settings.yml" >}}
# Source files
rtl_path: "examples/shift_register_sv"
top_level_file: "shift_register.sv"
top_level_module: "shift_register"

# Signals
clock_signal: "i_clk"
reset_signal: "i_rst"

# Delimiters for parameter files
use_parameters: Yes
start_delimiter: "#("
stop_delimiter: ")("
{{< /code >}}

The delimiters are the same `#(` / `)(` as the [ALU](/docs/examples/architectures/alu/) — and here they are unambiguous, since the file contains a single module and no instantiation.

### The Chisel version

`Example_Shift_Register_chisel` is the same design in Chisel, elaborated before synthesis:

{{< code lang=yaml filename="architectures/Example_Shift_Register_chisel/_settings.yml" >}}
design_path: "examples/shift_register_chisel"
design_path_whitelist: ['project', 'src', 'build.sbt']

generate_rtl: Yes
generate_command: "sbt 'runMain ShiftRegister --o=rtl'"
generate_output: "rtl"

top_level_file: "ShiftRegister.sv"
top_level_module: "ShiftRegister"
clock_signal: "clock"
reset_signal: "reset"

use_parameters: Yes
param_target_file: "src/main/scala/ShiftRegister.scala"
start_delimiter: "new ShiftRegister("
stop_delimiter: ")"
{{< /code >}}

with configuration files holding a Scala named argument (`BITS = 16`) instead of a Verilog parameter declaration. It carries the same frequency bounds as the SystemVerilog version, so any difference in the results comes from the netlist and not from the search.

## Multiplier

### What the design does

A registered `BITS` × `BITS` multiplier, truncated back to `BITS` bits:

{{< code lang=systemverilog filename="examples/mult/mult.sv" >}}
  // register inputs
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      op_a <= 0;
      op_b <= 0;
    end else begin
      op_a <= i_op_a;
      op_b <= i_op_b;
    end
  end

  // multiplier logic
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      value <= 0;
    end else begin
      value <= op_a * op_b;
    end
  end
{{< /code >}}

Both ends are registered, for the same reason as in the [ALU](/docs/examples/architectures/alu/): the timing report must measure the multiplier array and nothing else. Latency is 2 cycles.

{{< details title="Interface" >}}
| Port | Direction | Width | Role |
|---|---|---|---|
| `i_clk` | in | 1 | Clock, rising edge |
| `i_rst` | in | 1 | Synchronous reset, active high |
| `i_op_a`, `i_op_b` | in | `BITS` | Operands |
| `o_res` | out | `BITS` | Registered low `BITS` bits of the product |

The product is truncated, not saturated: only the low `BITS` bits are kept.
{{< /details >}}

### Architecture settings

{{< code lang=yaml filename="architectures/Example_Mult/_settings.yml" >}}
# Source files
rtl_path: "examples/mult"
top_level_file: "mult.sv"
top_level_module: "mult"

# Signals
clock_signal: "i_clk"
reset_signal: "i_rst"

# Delimiters for parameter files
use_parameters: Yes
start_delimiter: "mult #("
stop_delimiter: ")("
{{< /code >}}

The start delimiter includes the module name, which is the safe form: it can only match the header.

### The interesting part: this one is expensive

A combinational multiplier is the **opposite** of the shift register. Its area grows roughly as `BITS²` and its critical path grows with `BITS`, and on an FPGA it hits a second effect: below a certain width the tool infers a DSP block and the design is nearly free, above it the multiplier spills into fabric and both area and delay jump.

That discontinuity is visible in the frequency bounds — much wider than the shift register's, because the answer moves a lot across the sweep:

{{< code lang=yaml filename="architectures/Example_Mult/_settings.yml" >}}
xc7a100t-csg324-1:
  fmax_synthesis:
    lower_bound: 100
    upper_bound: 600
XFAB180CMOS:
  fmax_synthesis:
    lower_bound: 150
    upper_bound: 1400
{{< /code >}}

> [!INFO]
> `Example_Mult/16bits` is annotated in the run settings as **failing with Vivado**. It is left enabled deliberately: a sweep that maps out a design space will hit configurations a tool cannot handle, and Odatix reports them as failed jobs and carries on with the rest rather than aborting the run. Seeing one in the shipped examples is the point.

## Shared configuration files

All three of `Example_ALU_sv`, `Example_Shift_Register_sv` and `Example_Mult` substitute the same fragment:

{{< code lang=text filename="architectures/Example_Mult/16bits.txt" >}}

  parameter BITS = 16
{{< /code >}}

so their configuration directories are identical, byte for byte. This is a direct consequence of how substitution works: a configuration file holds a **fragment of source code**, and any design declaring a `BITS` parameter in the usual place accepts the same fragment. Adding a fourth design with a `BITS` parameter means copying the seven files and nothing else.

## Running the sweeps

{{< code lang=yaml filename="fmax_synthesis_settings.yml" >}}
architectures:
  - Example_Shift_Register_sv/16bits
  - Example_Shift_Register_sv/24bits

  - Example_Mult/04bits
  - Example_Mult/08bits
  - Example_Mult/16bits  # this configuration fails with vivado
  - Example_Mult/24bits
{{< /code >}}

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado
{{< /code >}}

Or the whole four-design comparison at once, without editing the settings file:

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado -a "Example_Counter_verilog/*" "Example_Shift_Register_sv/*" "Example_ALU_sv/*" "Example_Mult/*"
{{< /code >}}

Then open the [Explorer](/docs/features/explorer/) and plot fmax and area against `BITS`. Four curves, four shapes:

| Design | Area vs `BITS` | Critical path vs `BITS` |
|---|---|---|
| Shift register | linear, small | flat |
| Counter | linear | slowly degrading (carry chain) |
| ALU | superlinear (barrel shifters) | degrading |
| Multiplier | quadratic | degrading fast, with an FPGA DSP discontinuity |

## Where to go next

- [ALU](/docs/examples/architectures/alu/) — the third curve of the comparison, and where the `#(` delimiter needs more care.
- [Counter](/docs/examples/architectures/counter/) — the reference sweep, in four languages.
- [Explorer](/docs/features/explorer/) — where these curves are meant to end up.
- [All architecture examples](/docs/examples/architectures/) — the six designs and what each one adds.
