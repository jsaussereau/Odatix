---
title: "Implement your own RTL architectures"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 1
description: "Add an existing RTL design, configurations and a target to an Odatix workspace."
categories: ["Tutorial", "Design"]
tags: ["synthesis", "own design"]
featured_image: "/images/tutorials/own-rtl.svg"
---

{{< toc >}}

This tutorial turns a small existing SystemVerilog design into an Odatix
architecture. The same layout applies to Verilog and VHDL; only the source file
and tool command change.

> [!NOTE]
> Use an EDA tool and target supported by your environment. The example uses
> Verilator for the fast analysis step and Vivado for synthesis, but neither is
> required by the architecture definition itself.

## Step 1 — Initialize the workspace

Create a directory beside the source tree, or initialize the root of an
existing project:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/my-adder-odatix && cd ~/my-adder-odatix
$ odatix init
$ mkdir -p rtl odatix_userconfig/architectures/MyAdder
{{< /code >}}

Place the HDL sources in `rtl/`. In this example, the top-level file is
`rtl/adder.sv` and its module name is `adder`.

## Step 2 — Mark the configurable parameters

Use delimiters around the parameter text Odatix should replace. They can be
comments, which makes the intent clear to both people and tools:

{{< code lang=systemverilog filename="rtl/adder.sv" >}}
module adder #(
  // odatix: begin parameters
  parameter WIDTH = 8
  // odatix: end parameters
) (
  input  logic             clk,
  input  logic             rst,
  input  logic [WIDTH-1:0] a,
  input  logic [WIDTH-1:0] b,
  output logic [WIDTH:0]   sum
);
  assign sum = a + b;
endmodule
{{< /code >}}

Create a configuration file whose content replaces only the text between the
two markers:

{{< code lang=systemverilog filename="odatix_userconfig/architectures/MyAdder/16bits.txt" >}}
parameter WIDTH = 16
{{< /code >}}

Create more files such as `08bits.txt` or `32bits.txt` when you want more
variants. If the values follow a rule, use [configuration generation](/docs/configurations/config_generation/)
instead of maintaining every file manually.

## Step 3 — Describe the architecture

Create `odatix_userconfig/architectures/MyAdder/_settings.yml`:

{{< code lang=yaml filename="_settings.yml" >}}
generate_rtl: false

rtl_path: rtl
top_level_file: adder.sv
top_level_module: adder

clock_signal: clk
reset_signal: rst

use_parameters: true
start_delimiter: "// odatix: begin parameters"
stop_delimiter: "// odatix: end parameters"

custom_freq_synthesis:
  list: [100, 200]
{{< /code >}}

`rtl_path` is resolved from the workspace where you run Odatix. Keep setting
paths relative whenever possible so the project can be moved or shared.

## Step 4 — Inspect one replacement

Test the markers before invoking a tool:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix replace \
    -s "// odatix: begin parameters" \
    -S "// odatix: end parameters" \
    -i rtl/adder.sv \
    -r odatix_userconfig/architectures/MyAdder/16bits.txt \
    -o /tmp/adder_16bits.sv
{{< /code >}}

Open the generated file and confirm that it is valid HDL. This is the fastest
way to catch mistyped delimiters or parameter text.

## Step 5 — Select the configuration and target

In `odatix_userconfig/custom_freq_synthesis_settings.yml`, select the design:

{{< code lang=yaml filename="custom_freq_synthesis_settings.yml" >}}
architectures:
  - MyAdder/16bits
{{< /code >}}

Then select a device or technology in the target file for the tool you intend
to use, for example `odatix_userconfig/targets/target_vivado.yml`. The exact target and
library setup are specific to your installation.

## Step 6 — Analyze before synthesis

If Verilator is available, check elaboration first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze --tool verilator -E
{{< /code >}}

Correct missing-module, syntax or black-box errors before synthesis. The
[RTL analysis tutorial](/tutorials/run_examples/analysis/) shows the result
dashboard.

## Step 7 — Run a small synthesis campaign

Run the two configured frequencies on the selected target:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool vivado -E
$ odatix-explorer
{{< /code >}}

Once this works, add configurations, targets or parameter domains gradually.
Use `odatix fmax --tool vivado` when the goal is maximum frequency rather than
a fixed-frequency trade-off.

## Next steps

- **Feature** — [Architecture exploration](/docs/features/architecture-exploration/).
- **Reference** — [Architecture settings](/docs/reference/architecture/) (every key) · [Run settings files](/docs/reference/run_settings/) · [Target files](/docs/reference/targets/)
- **Guides** — [Parameter domains](/docs/configurations/param_domains/) · [Configuration generation](/docs/configurations/config_generation/) · [Troubleshooting](/docs/troubleshooting/)
- **Next** — [Simulate your own RTL](/tutorials/own_designs/simulations/) · [Create your own workflow](/tutorials/own_designs/workflows/)
