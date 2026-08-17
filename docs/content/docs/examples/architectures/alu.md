---
title: "ALU (SystemVerilog & Chisel)"
description: "A registered arithmetic and logic unit in SystemVerilog and in Chisel — a multi-file design with a package, a submodule, and a top level that is not the interesting module."
weight: 3
---

# ALU (SystemVerilog & Chisel)

The ALU is the first example with **more than one source file**. It is a small arithmetic and logic unit — twelve operations, one result register — described in SystemVerilog and in Chisel, and swept over its datapath width.

What it adds over the [counter](/docs/examples/architectures/counter/) is structure: a package holding the opcode enumeration, a submodule doing the work, and a top level whose only job is to register the inputs. That is enough to show how Odatix handles a design that is not a single file, and why the module a sweep targets is not always the module a designer would consider the main one.

{{< details title="What this example demonstrates" >}}
- **A multi-file design** — Odatix copies the whole `rtl_path` directory, so packages and submodules follow without being listed anywhere.
- **A synthesis wrapper as top level** — `alu_top` registers the inputs so the timing report measures the ALU, not the pad-to-pad path.
- **Delimiters that are not unique in the file** — `#(` appears twice in `alu_top.sv`, and only the first occurrence is substituted.
- **A parameter that must reach a submodule** — `BITS` is set once on the top level and propagated down by the RTL itself.
- **The same design in Chisel** — with a Scala package, a submodule, and the parameter replaced in the elaboration call.
- **Per-target frequency bounds** — an ALU is deeper than a counter, so the search ranges differ.
{{< /details >}}


{{< toc >}}

## What the design does

`alu` computes one of twelve operations on two `BITS`-wide operands, selected by `i_sel_op`, and registers the result:

| Group | Operations |
|---|---|
| Arithmetic | `add`, `sub` |
| Logic | `and`, `or`, `xor` |
| Comparison | `slt` (signed), `sltu` (unsigned) |
| Shifts | `sll`, `srl`, `sra` |
| Pass-through | `cpa`, `cpb` |

The opcodes are a typed enumeration living in its own package, so the `case` statement is exhaustive and readable:

{{< code lang=systemverilog filename="examples/alu_sv/pck_control.sv" >}}
package pck_control;

  typedef enum logic [3:0] {
    alu_nop  = 4'd0,
    alu_add  = 4'd1,
    alu_sub  = 4'd2,
    ...
    alu_cpb  = 4'd12
  } sel_alu_op_e;

endpackage
{{< /code >}}

`alu_top` wraps it and **registers the three inputs** before feeding them in:

{{< code lang=systemverilog filename="examples/alu_sv/alu_top.sv" >}}
  // register inputs
  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      op_a <= 0;
      op_b <= 0;
      sel_op <= alu_nop;
    end else begin
      op_a <= i_op_a;
      op_b <= i_op_b;
      sel_op <= sel_alu_op_e'(i_sel_op);
    end
  end

  alu #(
    .BITS     ( BITS   )
  ) inst_alu (
    ...
  );
{{< /code >}}

> [!TIP]
> That wrapper is not decoration, it is what makes the numbers meaningful. Without it, the critical path reported by the tool would start at an input port and end at a flip-flop, and would depend on how the tool chose to constrain the boundary rather than on the ALU itself. **Registering both ends of the design under test is the reliable way to measure logic depth** — the same reason the [multiplier](/docs/examples/architectures/mult_shift_register/) registers its operands.

{{< details title="Interface" >}}
| Port | Direction | Width | Role |
|---|---|---|---|
| `i_clk` | in | 1 | Clock, rising edge |
| `i_rst` | in | 1 | Synchronous reset, active high |
| `i_sel_op` | in | 5 | Operation code, cast to `sel_alu_op_e` |
| `i_op_a`, `i_op_b` | in | `BITS` | Operands |
| `o_res` | out | `BITS` | Registered result |

Latency is 2 cycles: one for the input registers, one for the result register.
{{< /details >}}

### Parameters

| Parameter | Default | Effect |
|---|---|---|
| `BITS` | 8 | Datapath width. Sets the width of the adder chain, of the comparators, and of the barrel shifters. |

Seven configurations are provided: `04bits` through `64bits`.

Unlike the counter, the ALU's area does **not** grow linearly: the barrel shifters are `O(BITS · log BITS)`, and the adder carry chain is what pushes the critical path. Sweeping the two designs on the same target and comparing the curves in the [Explorer](/docs/features/explorer/) is the point of having both.

## Files

{{< code lang=text filename="workspace" >}}
examples/
├── alu_sv/
│   ├── alu_top.sv                 # top level, registers the inputs
│   ├── alu.sv                     # the ALU itself
│   └── pck_control.sv             # opcode enumeration
└── alu_chisel/
    ├── build.sbt
    └── src/main/scala/
        ├── ALUTop.scala           # top level
        ├── ALU.scala
        └── pck_control.scala

odatix_userconfig/
└── architectures/
    ├── Example_ALU_sv/
    │   ├── _settings.yml
    │   └── 04bits.txt, 08bits.txt, … 64bits.txt
    └── Example_ALU_chisel/        # same configurations, Scala delimiters
{{< /code >}}

> [!INFO]
> Only `top_level_file` is declared. The other two SystemVerilog files are found because Odatix copies the **whole** `rtl_path` directory into the job directory, and the flow then hands the directory to the tool. There is no file list to maintain.

## Architecture settings

{{< code lang=yaml filename="architectures/Example_ALU_sv/_settings.yml" >}}
# Source files
rtl_path: "examples/alu_sv"
top_level_file: "alu_top.sv"
top_level_module: "alu_top"

# Signals
clock_signal: "i_clk"
reset_signal: "i_rst"

# Delimiters for parameter files
use_parameters: Yes
start_delimiter: "#("
stop_delimiter: ")("

# Default frequencies (in MHz)
fmax_synthesis:
  lower_bound: 50
  upper_bound: 1500
custom_freq_synthesis:
  list: [50, 100]
{{< /code >}}

Two details are worth stopping on.

### The clock and reset are not called `clock` and `reset`

`clock_signal` and `reset_signal` are what the flows use to write the timing constraint and to identify the reset network. They name **whatever the design calls them** — here `i_clk` and `i_rst`, where the counter used `clock` and `reset`. Nothing has to be renamed in the RTL.

### The delimiters are the shortest ones that still work

{{< code lang=yaml >}}
start_delimiter: "#("
stop_delimiter: ")("
{{< /code >}}

`alu_top.sv` contains `#(` **twice** — once in its own header, once in the instantiation of `alu`:

{{< code lang=systemverilog filename="examples/alu_sv/alu_top.sv" >}}
module alu_top
  import pck_control::*;
#(
  parameter BITS = 8
)(
  ...
  alu #(
    .BITS     ( BITS   )
  ) inst_alu (
{{< /code >}}

Only the **first** match is substituted, which is the module header — so the sweep works. The `alu` instantiation is left alone, and `BITS` reaches the submodule the normal way, through the port map.

> [!WARNING]
> Short delimiters are convenient but fragile: they depend on where in the file the first match happens to be. Prefer a delimiter that can only match one place, as the [Cordic](/docs/examples/architectures/cordic/) example does with `parameter WIDTH = `. Here the shorter form is kept because it lets `Example_ALU_sv` and `Example_Shift_Register_sv` share the exact same configuration files.

The configuration file holds the fragment to write between the delimiters:

{{< code lang=text filename="architectures/Example_ALU_sv/16bits.txt" >}}

  parameter BITS = 16
{{< /code >}}

### Per-target frequency bounds

An ALU has a deeper critical path than a counter, so its search ranges start lower:

{{< code lang=yaml filename="architectures/Example_ALU_sv/_settings.yml" >}}
xc7a100t-csg324-1:
  fmax_synthesis:
    lower_bound: 150
    upper_bound: 450
xc7k70t-fbg676-2:
  fmax_synthesis:
    lower_bound: 50
    upper_bound: 1200
XFAB180CMOS:
  fmax_synthesis:
    lower_bound: 300
    upper_bound: 700
{{< /code >}}

Compare with the counter's `250 – 900` on the same Artix-7 part: the counter's carry chain is the only thing in its way, the ALU also has to get through a barrel shifter and a result multiplexer.

## The Chisel version

`Example_ALU_chisel` describes the same structure — a package, an `ALU` module, an `ALUTop` wrapper — and differs from the SystemVerilog architecture only in the way the RTL comes into existence:

{{< code lang=yaml filename="architectures/Example_ALU_chisel/_settings.yml" >}}
# Source files
design_path: "examples/alu_chisel"
design_path_whitelist: ['project', 'src', 'build.sbt']
design_path_blacklist: []

# Generate the rtl (from chisel for example)
generate_rtl: Yes
generate_command: "sbt 'runMain ALUTop --o=rtl'"  # requires sbt and firtool
generate_output: "rtl"

# Generated design settings
top_level_file: "ALUTop.sv"
top_level_module: "ALUTop"
clock_signal: "clock"
reset_signal: "reset"

# Delimiters for parameter files
use_parameters: Yes
param_target_file: "src/main/scala/ALUTop.scala"
start_delimiter: "new ALUTop("
stop_delimiter: ")"
{{< /code >}}

The substitution target is the **elaboration call** at the bottom of the Scala file, so the width is fixed before Chisel emits anything:

{{< code lang=scala filename="examples/alu_chisel/src/main/scala/ALUTop.scala" >}}
object ALUTop extends App {
  ChiselStage.emitSystemVerilog(
    new ALUTop(8),
    firtoolOpts = ...
  )
}
{{< /code >}}

and the configuration file holds a Scala named argument instead of a Verilog parameter declaration:

{{< code lang=text filename="architectures/Example_ALU_chisel/16bits.txt" >}}
BITS = 16
{{< /code >}}

Note that the Chisel version keeps Chisel's own `clock` and `reset` names, while the SystemVerilog one uses `i_clk` / `i_rst`. This is exactly the kind of difference `clock_signal` and `reset_signal` exist to absorb: both architectures are otherwise interchangeable in a run.

> [!WARNING]
> The Chisel version needs **sbt** and **firtool** installed.

## Running the sweep

The ALU entries live in the run settings, mostly commented out:

{{< code lang=yaml filename="fmax_synthesis_settings.yml" >}}
architectures:
  - Example_ALU_sv/08bits
  - Example_ALU_sv/16bits
{{< /code >}}

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado
{{< /code >}}

Or, without touching the file, from the command line:

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado -a "Example_ALU_sv/*"
{{< /code >}}

Running both architectures side by side and opening the [Explorer](/docs/features/explorer/) answers the question the example is really about: **does the Chisel-generated netlist cost anything compared to the hand-written one?**

## Where to go next

- [Multiplier & Shift Register](/docs/examples/architectures/mult_shift_register/) — two more `BITS` sweeps, sharing the same configuration files, whose curves make a good three-way comparison with the ALU.
- [Counter](/docs/examples/architectures/counter/) — the same architecture settings, one file and one always block.
- [Cordic](/docs/examples/architectures/cordic/) — where one parameter is no longer enough.
- [All architecture examples](/docs/examples/architectures/) — the six designs and what each one adds.
