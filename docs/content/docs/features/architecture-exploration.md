---
title: "Architecture Exploration"
description: "Define a parametrizable design once, then let Odatix generate and implement every configuration you want to compare."
layout: "doc-features"
badge: "Design Space Exploration"
badgeColor: "#2563eb"
cta: true
weight: 1
features:
  - title: "Parameter files"
    description: "Describe each design variant with a small parameter file that Odatix splices into your top-level source."
  - title: "Parameter domains"
    description: "Group independent parameters into domains and combine them automatically to cover the full design space."
  - title: "Configuration generation"
    description: "Generate hundreds of configurations from a few YAML rules — ranges, powers of two, lists, functions and set operations."
  - title: "Any HDL flow"
    description: "Works with VHDL, Verilog, SystemVerilog, and even generated RTL from Chisel or HLS."
---

## Why architecture exploration?

Most interesting digital designs are **configurable**: a data width here, a
memory depth there, an optional multiplier, a pipeline depth. Each choice changes
area, timing and power — and the best combination depends on your target
technology and your application constraints.

Exploring that space by hand means editing sources, launching a tool, writing
down a number, and repeating dozens or hundreds of times. Architecture
exploration removes that toil: you describe the **parameters**, and Odatix
produces and implements every **configuration**.

It is the foundation the rest of Odatix stands on. Synthesis, simulation,
analysis and workflows all run *per configuration* — so whatever you set up here
is swept by every other feature for free.

{{< img src="/images/diagrams/architecture-exploration.svg" shadow="false" >}}

## When you need it

- **Sizing a design.** You want the area and Fmax of your ALU at 4, 8, 16, 32 and
  64 bits, on two FPGAs, without maintaining five copies of the source.
- **Choosing between implementations.** A fast multiplier, a basic one, or none
  at all — three variants of one parameter, compared on equal footing.
- **Sweeping a large, structured space.** A RISC-V core with independent choices
  for instruction memory, data memory, ISA extensions and multiplier: dozens of
  combinations you never want to write out by hand.
- **Publishing a comparison.** A paper or a report that needs the same design
  measured consistently across a parameter range.
- **Non-HDL sweeps.** The same mechanism drives [workflows](/docs/features/workflows/),
  so a script, a compiler flag or a training hyper-parameter sweeps identically.

## How it works

### 1. Mark the parameter section of your design

In your top-level source, wrap the block that changes between configurations with
delimiters. Any delimiter works, as long as it is valid in your HDL — Odatix
keeps the delimiters and replaces what is between them.

{{< code lang=verilog filename="alu_top.sv" >}}
module alu_top #(
  parameter BITS = 8   // <-- this block is replaced per configuration
)(
  input  wire            i_clk,
  input  wire            i_rst,
  input  wire      [4:0] i_sel_op,
  input  wire [BITS-1:0] i_op_a,
  input  wire [BITS-1:0] i_op_b,
  output wire [BITS-1:0] o_res
);
{{< /code >}}

### 2. Provide one parameter file per configuration

Each parameter file contains the exact replacement for the delimited section, and
nothing else:

{{< code lang=verilog filename="architectures/ALU/16bits.txt" >}}
  parameter BITS = 16
{{< /code >}}

There is no limit to the number of parameter files or the number of parameters
they contain. The only rule is a strict correspondence between the parameter
files and the parameter section of your top level.

### 3. Let Odatix combine everything

For large spaces, writing each file by hand is still too much work. Two
mechanisms remove it:

**[Parameter domains](/docs/configurations/param_domains/)** split independent
parameters (memory depth, ISA extensions, multiplier type…) into separate
folders, each replacing a different delimited block. Combine them with `+`, or
expand everything with `*`:

{{< code lang=yaml filename="fmax_synthesis_settings.yml" >}}
architectures:
  - AsteRISC/* + DMEM/* + IMEM/* + Baseline/* + Mul/*
{{< /code >}}

**[Configuration generation](/docs/configurations/config_generation/)** creates
the parameter files themselves from compact rules — ranges, powers of two,
explicit lists, multiples, computed functions, and set operations:

{{< code lang=yaml filename="_settings.yml" >}}
generate_configurations: Yes
generate_configurations_settings:
  template: "parameter BITS = $var;"
  name: "config_${var}"
  variables:
    var:
      type: power_of_two
      settings:
        from: 8
        to: 1024
{{< /code >}}

### Works with any HDL — even generated RTL

Odatix does not care whether you write **VHDL, Verilog or SystemVerilog** by
hand, or **generate your RTL** from **Chisel** or **HLS**. For generated flows,
the replacement targets the *source* file (via `param_target_file`) before the
RTL is produced, so exploration works end to end. Parameters passed on a
generation command line instead of edited into a file are covered by
[virtual parameter domains](/docs/configurations/virtual_param_domains/).

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [RTL analysis](/docs/features/analysis/) | Elaborate every generated configuration in seconds, before spending hours synthesizing a space with a typo in it. |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) | Each configuration reaches *its own* maximum frequency — the only fair way to compare variants. |
| [Custom-frequency synthesis](/docs/features/rtl_synthesis/) | Compare the same configurations at a common clock, for area and power studies. |
| [Simulation](/docs/features/simulation/) | Confirm every configuration still passes its testbench, not just the one you developed on. |
| [Workflows](/docs/features/workflows/) | Reuse the same domains and generation rules on anything that runs from a shell. |
| [Explorer](/docs/features/explorer/) | Every parameter domain becomes an axis you can plot metrics against. |

## Using it

### From the configuration files and the CLI

A design is a directory under `odatix_userconfig/architectures/`, holding a
`_settings.yml` and one parameter file per configuration:

{{< code lang=text filename="odatix_userconfig/architectures/ALU/" >}}
_settings.yml     # sources, top level, clock/reset, delimiters
08bits.txt        # a configuration
16bits.txt        # another one
Mul/              # a parameter domain
  _settings.yml
  Fast.txt
  Off.txt
{{< /code >}}

{{< code lang=yaml filename="architectures/ALU/_settings.yml" >}}
rtl_path: "examples/alu_sv"

top_level_file:   "alu_top.sv"
top_level_module: "alu_top"
clock_signal:     "i_clk"
reset_signal:     "i_rst"

use_parameters:  Yes
start_delimiter: "#("
stop_delimiter:  ")("
{{< /code >}}

Check the replacement without launching a tool, then select the configurations in
the run settings file of whichever job type you want:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix replace --startdel "#(" --stopdel ")(" \
    --input rtl/alu_top.sv --replace architectures/ALU/16bits.txt \
    --output /tmp/alu_top_16bits.sv     # inspect what a job would build

$ odatix generate                        # write the generated parameter files
$ odatix fmax -t vivado                  # run every selected configuration
{{< /code >}}

Every key of `_settings.yml` is on the
[architecture settings reference](/docs/reference/architecture/); the selector
syntax is on the [run settings reference](/docs/reference/run_settings/#architectures--designs-and-configurations).

### From the GUI

`odatix-gui` → **RTL Architectures** (`/architectures`) does the same without
YAML: a form for the sources, top level, clock, reset and delimiters, the list of
configurations with an editor for each parameter file, and per-target frequency
bounds. The **Configuration Generator** builds a whole set of parameter files
from a rule, previewing the values before writing them.

From there, **Run Jobs** picks the configurations to launch. Everything the GUI
writes is the same YAML described above — the two interfaces edit one workspace.

## Where to go next

- **Tutorial** — [Implement your own RTL](/tutorials/own_designs/synthesis/): a design, its configurations and a first run, end to end.
- **Reference** — [Architecture settings](/docs/reference/architecture/) · [Run settings files](/docs/reference/run_settings/)
- **Guides** — [Parameter domains](/docs/configurations/param_domains/) · [Configuration generation](/docs/configurations/config_generation/) · [Virtual parameter domains](/docs/configurations/virtual_param_domains/)
- **Next feature** — [RTL analysis](/docs/features/analysis/), the cheap check to run before implementing a whole space.
