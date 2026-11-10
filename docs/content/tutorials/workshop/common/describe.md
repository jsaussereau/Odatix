---
title: "Describe the design"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 2
description: "The common track, part 1: in odatix-gui, describe the CORDIC core to Odatix yourself, in SystemVerilog or VHDL — nine configurations, without writing a configuration file."
categories: ["Tutorial", "Design"]
tags: ["workshop", "gui", "architecture", "parameter domains", "cordic"]
featured_image: "/images/tutorials/own-rtl.svg"
next_tutorials: ["/tutorials/workshop/common/analysis"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| None but `odatix-gui` | 15 min | Nine configurations you described |

The design is a **pipelined CORDIC rotation core**: it rotates a vector by an
angle using nothing but additions and shifts. Two parameters describe it, and
they pull in opposite directions — more bits and more stages mean a more
accurate result and a bigger, slower circuit. The whole workshop is about
putting numbers on that sentence.

{{< img src="/images/diagrams/cordic-core.svg" title="The CORDIC core: x, y on WIDTH bits and a 32-bit angle in, the rotated vector out, one result per cycle after ITERATIONS + 2 cycles" shadow="false" >}}

On this page you describe that core to Odatix in its graphical interface,
without opening a single configuration file. The [next
page](/tutorials/workshop/common/analysis/) checks it in seconds, and the one after
[starts its synthesis](/tutorials/workshop/common/synthesis/).

> [!NOTE]
> The screenshots show the SystemVerilog core. In VHDL, everything is the
> same but the values the tables of each step give under **VHDL**.

## Step 1 — Look at what has to be described

Odatix asks three questions of a design: **where are its sources**, **what
changes between two configurations**, and **what does its testbench measure**.
This page answers the first two; the testbench comes [after the synthesis](/tutorials/workshop/common/simulate/).

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

## Step 2 — Open the interface

From the workspace directory:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

It opens in your browser. Click on **RTL architectures**. It lists the
designs of the workspace — none yet:

{{< img src="/images/screenshots/workshop/gui-architectures.png" title="Configure → RTL architectures, in a new workspace" >}}

Leave the terminal running: it is the server of the interface. Use a second
terminal for anything else.

## Step 3 — Create the architecture

Click **Create new architecture manually**, and fill in the form.  

The folder button of a path field browses the workspace, and the **magic wand** next to the module, the clock and the reset reads them from the sources: click the three wands, and check that they found what step 1 says.

{{< img src="/images/screenshots/workshop/gui-arch-settings.png" title="The new architecture: sources, signals detected from the RTL, and 100 MHz for the synthesis" >}}

Put `100` in the **Fixed-frequency synthesis** field.
It is the clock the [synthesis](/tutorials/workshop/common/synthesis/) runs at, in MHz. Leave the rest empty, and click **Save all**: the button turns orange whenever something is not saved yet.

> [!NOTE]
> That is already a design Odatix can synthesize — with one configuration, the values written in the RTL. The parameter domains make it a design space.

## Step 4 — Describe what changes

A **parameter domain** replaces one value of the parameter list, between two
delimiters, by the value of each of its configurations. Each of the two
parameters gets one.

Click **Edit configs** at the top of the architecture. On the **Main parameter
domain**, click **Detect**: Odatix lists the parameters of the top-level file,
with the two to sweep already ticked.

{{< img src="/images/screenshots/workshop/gui-detect.png" title="Detect: the parameters of cordic.sv, WIDTH and ITERATIONS ticked" >}}

Click **Create domains**. Odatix creates one domain per parameter, **with the
delimiters already found** in the RTL:

| Domain | Start delimiter (SV) | Stop delimiter (SV) | Start delimiter (VHDL) | Stop delimiter (VHDL) |
|---|---|---|---|---|
| `WIDTH` | `WIDTH = ` | `,` | `WIDTH : integer := ` | `;` |
| `ITERATIONS` | `ITERATIONS = ` | `\n` | `ITERATIONS : integer := ` | `\n` |

That is the detail step 1 warned about, done for you: `ITERATIONS` is the last
parameter, so its value ends with the line (`\n`), not with a separator.

Each domain holds one variable, with the value of the RTL as its only value.  

For each of the two domains, in turn:

1. In its **List**, type the values: `4, 8, 12` for `WIDTH`, `12, 16, 24` for
   `ITERATIONS`.
2. Click **Save rules**.

{{< img src="/images/screenshots/workshop/gui-domain-width.png" title="The WIDTH domain: delimiters found by Detect, its three values typed, Save rules waiting" >}}

> [!TIP]
> The **Preview pane** shows the top-level file as one configuration will see it: pick a value in its menu and look for the line of the parameter.

> [!INFO]
> We now have two domains of three values each, and Odatix combines them on its own: that is **nine designs**.


## Step 5 — Read what the interface wrote

Everything you did in the interface is in four short files, in
`odatix_userconfig/architectures/`. Open them in any editor.

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< details title="The four files" >}}

{{< code lang=text filename="odatix_userconfig/architectures/My_Cordic_sv/" >}}
My_Cordic_sv/
├── _settings.yml          # the form of step 3
├── WIDTH/
│   └── _settings.yml      # the WIDTH domain
└── ITERATIONS/
    └── _settings.yml      # the ITERATIONS domain
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/_settings.yml" >}}
# RTL generation
generate_rtl: No

# Source files
rtl_path: examples/cordic_sv
top_level_file: cordic.sv
top_level_module: cordic

# Signals
clock_signal: clock
reset_signal: reset

# Delimiters for parameter files
use_parameters: No
start_delimiter: ''
stop_delimiter: ''

# Constraints
fixed_freq_synthesis:
  list: [100]
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/WIDTH/_settings.yml" >}}
# Delimiters for parameter files
use_parameters: Yes
param_target_file: ''
start_delimiter: 'WIDTH = '
stop_delimiter: ','

# Variables
variables:
  WIDTH:
    type: list
    settings:
      list: [4, 8, 12]
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/ITERATIONS/_settings.yml" >}}
# Delimiters for parameter files
use_parameters: Yes
param_target_file: ''
start_delimiter: 'ITERATIONS = '
stop_delimiter: "\n"

# Variables
variables:
  ITERATIONS:
    type: list
    settings:
      list: [12, 16, 24]
{{< /code >}}

{{< /details >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< details title="The four files" >}}

{{< code lang=text filename="odatix_userconfig/architectures/My_Cordic_vhdl/" >}}
My_Cordic_vhdl/
├── _settings.yml          # the form of step 3
├── WIDTH/
│   └── _settings.yml      # the WIDTH domain
└── ITERATIONS/
    └── _settings.yml      # the ITERATIONS domain
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_vhdl/_settings.yml" >}}
# RTL generation
generate_rtl: No

# Source files
rtl_path: examples/cordic_vhdl
top_level_file: cordic.vhdl
top_level_module: cordic

# Signals
clock_signal: clock
reset_signal: reset

# Delimiters for parameter files
use_parameters: No
start_delimiter: ''
stop_delimiter: ''

# Constraints
fixed_freq_synthesis:
  list: [100]
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_vhdl/WIDTH/_settings.yml" >}}
# Delimiters for parameter files
use_parameters: Yes
param_target_file: ''
start_delimiter: 'WIDTH : integer := '
stop_delimiter: ;

# Variables
variables:
  WIDTH:
    type: list
    settings:
      list: [4, 8, 12]
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_vhdl/ITERATIONS/_settings.yml" >}}
# Delimiters for parameter files
use_parameters: Yes
param_target_file: ''
start_delimiter: 'ITERATIONS : integer := '
stop_delimiter: "\n"

# Variables
variables:
  ITERATIONS:
    type: list
    settings:
      list: [12, 16, 24]
{{< /code >}}

{{< /details >}}

{{% /tab %}}

{{< /tabs >}}

Every line is a field you filled in, or one the interface found for you:

| In the interface | In the files |
|---|---|
| The name of the architecture | the name of its directory |
| **RTL path**, **Top level file**, the three wands | `rtl_path`, `top_level_file`, `top_level_module`, `clock_signal`, `reset_signal` |
| **Fixed-frequency synthesis** → **List** | `fixed_freq_synthesis: list: [100]` |
| A domain, and its name | a sub-directory, and its name |
| The delimiters **Detect** found | `start_delimiter`, `stop_delimiter` of the domain |
| The variable, its type and its **List** | `variables:` of the domain |

> [!NOTE]
> The main `_settings.yml` says `use_parameters: No` because it replaces nothing itself: each domain does, in its own file, with `use_parameters: Yes`.

The lines starting with `#` are comments. Odatix writes a header at the top of each file, with the date; it is left out above.

**Nothing else is needed.** Ten minutes in a text editor would have given the
same four files, and Odatix would not see the difference.
Use whichever you like best, and switch at any time: the interface reads the files you write, and writes the files you read.

> [!NOTE]
> The domain directories also hold a hidden `.odatix_configs/`, with one file per value (`4.txt` holds `4`): the configurations the interface generated from your list, kept for the run. You never edit them — change the list, and they follow.
