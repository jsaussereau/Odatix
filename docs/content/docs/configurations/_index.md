---
title: "Design configurations (variants)"
description: "Define parametrizable designs, organize parameters into domains, and generate configurations automatically."
weight: 2
---

# Configurations

A **design** in Odatix is parametrizable; a **configuration** is one concrete set of parameter values for that design. This section covers how to describe configurations — from writing individual parameter files by hand to generating hundreds of them automatically.

{{< toc >}}

## The building blocks

Odatix builds configurations from three mechanisms that stack on top of each other:

| Mechanism | What it is | Use it when |
|-----------|-----------|-------------|
| **Parameter files** | One file per configuration, splicing values into the delimited section of your top level. | You have a handful of variants to compare. |
| **[Parameter domains](/docs/configurations/param_domains/)** | Independent groups of parameters combined with `+`. | Parameters are independent (memory depth, ISA extensions, multiplier type…). |
| **[Configuration generation](/docs/configurations/config_generation/)** | Rules that create the parameter files for you. | The value set follows a pattern — ranges, powers of two, lists, functions. |

## Defining a design

A design lives in `odatix_userconfig/architectures/<name>/`, with a `_settings.yml` that tells Odatix where your sources are and how to instantiate the design.

{{< tabs >}}
{{% tab name="VHDL / Verilog / SystemVerilog" %}}
{{< code lang=yaml filename="architectures/ALU/_settings.yml" >}}
rtl_path: "examples/alu_sv"

top_level_file: "alu_top.sv"   # relative to rtl_path
top_level_module: "alu_top"

clock_signal: "i_clk"
reset_signal: "i_rst"

# delimiters that mark the parameter section of the top level
use_parameters: Yes
start_delimiter: "#("
stop_delimiter: ")("

# target-specific bounds
xc7a100t-csg324-1:
  fmax_synthesis:
    lower_bound: 50
    upper_bound: 800
{{< /code >}}
{{% /tab %}}
{{% tab name="Chisel / HLS" %}}
{{< code lang=yaml filename="architectures/ALU/_settings.yml" >}}
design_path: "examples/alu_chisel"

# generate the RTL first (from Chisel, HLS, ...)
generate_rtl: Yes
generate_command: "sbt 'runMain ALUTop --o=rtl'"
generate_output: "rtl"

top_level_file: "ALUTop.sv"    # relative to generate_output
top_level_module: "ALUTop"
clock_signal: "clock"
reset_signal: "reset"

# with generated RTL, replacement targets the *source*, not the top level
use_parameters: Yes
param_target_file: "src/main/scala/ALUTop.scala"
start_delimiter: "new ALUTop("
stop_delimiter: ")"
{{< /code >}}
{{% /tab %}}
{{< /tabs >}}

> [!IMPORTANT]
> With generated RTL (Chisel, HLS), `param_target_file` is **mandatory**: the top level does not exist yet when parameters are replaced, so replacement must target the source file that produces it.

A full list of `_settings.yml` keys is on the [Configuration reference](/docs/reference/) page.

## Writing parameter files by hand

Each parameter file contains the exact text that replaces the delimited section of your top level. Given this module:

{{< code lang=verilog filename="alu_top.sv" >}}
module alu_top #(
  parameter BITS = 8
)(
  input  wire            i_clk,
  input  wire      [4:0] i_sel_op,
  output wire [BITS-1:0] o_res
);
{{< /code >}}

a configuration file simply provides the replacement:

{{< code lang=verilog filename="architectures/ALU/16bits.txt" >}}
  parameter BITS = 16
{{< /code >}}

Create as many files as you want. The only constraint is a strict correspondence — in names and count — between the parameter files and the parameter section of your top level.

## Test a replacement on its own

`odatix replace` is useful when preparing a new design: it applies the same
delimiter-based replacement as a job, without invoking a simulator or EDA tool.
Use it to inspect the generated source before launching an expensive run.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix replace \
  --startdel "// odatix: begin parameters" \
  --stopdel "// odatix: end parameters" \
  --input rtl/alu_top.sv \
  --replace architectures/ALU/16bits.txt \
  --output /tmp/alu_top_16bits.sv
{{< /code >}}

By default, the first delimited block is replaced. Add `--all` when every
matching block must receive the same replacement. The command keeps the
delimiter text itself, so the output remains suitable for a later Odatix run.

## Scaling up

Writing files by hand does not scale to large design spaces. The next two pages remove that work:

- **[Parameter domains](/docs/configurations/param_domains/)** — combine independent parameters automatically.
- **[Configuration generation](/docs/configurations/config_generation/)** — generate the parameter files from compact rules.
