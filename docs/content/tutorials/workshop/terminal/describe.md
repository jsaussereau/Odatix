---
draft: true
title: "Describe the design"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 1
description: "The terminal variant of the common track, part 1: write the YAML files of the CORDIC architecture yourself, in SystemVerilog or VHDL — nine configurations."
categories: ["Tutorial", "Design"]
tags: ["workshop", "terminal", "architecture", "parameter domains", "cordic"]
featured_image: "/images/tutorials/own-rtl.svg"
next_tutorials: ["/tutorials/workshop/terminal/analysis"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| A text editor and a terminal | 15 min | Nine configurations you described |

The common track does everything in `odatix-gui`. These four pages are the
same work with a text editor and a terminal: the files the interface writes,
written by hand, and the commands its **Run** pages run. Take them instead of
[Describe the design](/tutorials/workshop/common/describe/) and the pages after it if you prefer
the terminal, or after them, to see that nothing in the interface is magic.

The result is the same architecture, under the same name — so take one or the
other, not both, in the same workspace. Every later page works with either.

> [!NOTE]
> Run every command from the workspace created in [Create a
> workspace](/tutorials/workshop/common/workspace/), and pick the tab of the language
> you chose there — the same one on every page.

## Step 1 — Look at what has to be described

Odatix asks three questions of a design: **where are its sources**, **what
changes between two configurations**, and **what does its testbench measure**.
This page answers the first two; the testbench comes [after the synthesis](/tutorials/workshop/terminal/simulate/).

Open the sources and look at the top of the module:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=systemverilog filename="examples/cordic_sv/cordic.sv" >}}
module cordic #(
  parameter WIDTH = 16,
  parameter ITERATIONS = 12
)(
  input  wire                     clock,
  input  wire                     reset,
  input  wire                     i_valid,
  ...
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=vhdl filename="examples/cordic_vhdl/cordic.vhdl" >}}
entity cordic is
  generic (
    WIDTH : integer := 16;
    ITERATIONS : integer := 12
  );
  port (
    clock   : in  std_logic;
    reset   : in  std_logic;
    i_valid : in  std_logic;
    ...
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

Four things to note, in either language:

| What | Value |
|---|---|
| The top-level module (or entity) | `cordic` |
| Its clock and its reset | `clock`, `reset` |
| The parameters to sweep | `WIDTH` (datapath width) and `ITERATIONS` (rotation stages) |
| **How each value ends** | `WIDTH` by a separator (`,` in SystemVerilog, `;` in VHDL), `ITERATIONS` by the end of the line |

The last line is the one detail of this page worth getting right: Odatix
changes a parameter by replacing the text between two delimiters, and the end
of each value is its second delimiter.

## Step 2 — Create the architecture

An architecture is a directory of `odatix_userconfig/architectures/`, named
after the design. Create it, with one directory per parameter you will sweep:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/architectures/My_Cordic_sv/WIDTH
$ mkdir -p odatix_userconfig/architectures/My_Cordic_sv/ITERATIONS
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/architectures/My_Cordic_vhdl/WIDTH
$ mkdir -p odatix_userconfig/architectures/My_Cordic_vhdl/ITERATIONS
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

Then describe the sources in its `_settings.yml`, with the four values of
step 1:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/_settings.yml" >}}
# Source files
rtl_path: "examples/cordic_sv"      # a directory, copied whole into every job
top_level_file: "cordic.sv"         # relative to rtl_path
top_level_module: "cordic"

# Signals
clock_signal: "clock"
reset_signal: "reset"
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_vhdl/_settings.yml" >}}
# Source files
rtl_path: "examples/cordic_vhdl"    # a directory, copied whole into every job
top_level_file: "cordic.vhdl"       # relative to rtl_path
top_level_module: "cordic"

# Signals
clock_signal: "clock"
reset_signal: "reset"
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

That is already a design Odatix can synthesize — with one configuration, the
values written in the RTL. The two directories make it a design space.

## Step 3 — Describe what changes

Each of the two directories is a **parameter domain**: it replaces one value of
the parameter list, between the two delimiters you give, by the value of each
of its configurations. Rather than writing the configurations one file at a
time, give the rule that lists them. Here is the width:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/WIDTH/_settings.yml" >}}
use_parameters: Yes
param_target_file: ''               # empty: the top level file
start_delimiter: 'parameter WIDTH = '
stop_delimiter: ','

variables:
  WIDTH:
    type: list
    settings:
      list: [4, 8, 12]
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_vhdl/WIDTH/_settings.yml" >}}
use_parameters: Yes
param_target_file: ''               # empty: the top level file
start_delimiter: 'WIDTH : integer := '
stop_delimiter: ';'

variables:
  WIDTH:
    type: list
    settings:
      list: [4, 8, 12]
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

Read it as: *in the top-level file, the text between `start_delimiter` and
`stop_delimiter` becomes 4, then 8, then 12*. The delimiters are copied from
the RTL character for character, spaces included.

Now write `ITERATIONS/_settings.yml` yourself, for `12`, `16` and `24` stages,
under a variable named `ITERATIONS`. Mind how the value ends.

{{< details title="The answer" >}}
In SystemVerilog:

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/ITERATIONS/_settings.yml" >}}
use_parameters: Yes
param_target_file: ''
start_delimiter: 'parameter ITERATIONS = '
stop_delimiter: '\n'                # the last parameter: no comma after it

variables:
  ITERATIONS:
    type: list
    settings:
      list: [12, 16, 24]
{{< /code >}}

In VHDL:

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_vhdl/ITERATIONS/_settings.yml" >}}
use_parameters: Yes
param_target_file: ''
start_delimiter: 'ITERATIONS : integer := '
stop_delimiter: '\n'                # the last generic: no semicolon after it

variables:
  ITERATIONS:
    type: list
    settings:
      list: [12, 16, 24]
{{< /code >}}

{{< /details >}}

> [!NOTE]
> Name the variables `WIDTH` and `ITERATIONS`, like the shipped description:
> the testbench, the charts and the modules all refer to them by those names.

Write the configurations out, and check what the workspace now holds:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix generate --architecture My_Cordic_sv -y
$ odatix ls -a --arch My_Cordic_sv
<b>Architectures (1)</b>
<font color="#729FCF">  My_Cordic_sv</font>
<font color="#34E2E2">    + ITERATIONS</font>
      12  16  24
<font color="#34E2E2">    + WIDTH</font>
      4  8  12
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix generate --architecture My_Cordic_vhdl -y
$ odatix ls -a --arch My_Cordic_vhdl
<b>Architectures (1)</b>
<font color="#729FCF">  My_Cordic_vhdl</font>
<font color="#34E2E2">    + ITERATIONS</font>
      12  16  24
<font color="#34E2E2">    + WIDTH</font>
      4  8  12
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

`odatix generate` wrote one file per value — `WIDTH/8.txt` holds nothing but
`8`. Two domains of three values each, and Odatix combines them on its own:
that is **nine designs**, not two sweeps, and nothing was written per
combination.

## If something did not work

| Symptom | What to do |
|---|---|
| `odatix generate` wrote nothing | `variables:` must be at the root of the domain's `_settings.yml`, with `settings` nested under the variable. |
| `odatix ls` shows the architecture without its domains | The two directories must be **inside** the architecture's directory, each with its own `_settings.yml`. |
