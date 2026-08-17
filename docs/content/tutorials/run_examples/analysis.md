---
title: "RTL Analysis"
date: 2026-08-04
# author: "Jonathan Saussereau"
weight: 1
description: "Elaborate the built-in example configurations before synthesis, and inspect the result in Odatix Explorer."
categories: ["Tutorial", "Analysis"]
tags: ["analysis", "verilator", "examples"]
featured_image: "/images/features/analysis.svg"
next_tutorials:
  - /tutorials/run_examples/synthesis
  - /tutorials/run_examples/fmax_synthesis
  - /tutorials/run_examples/simulations
---

{{< toc >}}

Run **RTL analysis** before an expensive synthesis campaign. Odatix prepares
every selected configuration and asks one or several tools to parse and
elaborate it. This finds missing files, unresolved modules, black boxes and
lint issues early.

## Prerequisites

For this tutorial, you need **at least one** of the following tools installed and available in your `PATH`:
- [Verilator](https://www.veripool.org/verilator/)
- [Vivado](https://www.xilinx.com/products/design-tools/vivado.html) (for Xilinx FPGAs)

Make sure you have [Odatix installed](/install/) and available in your `PATH`. For example, if you installed Odatix in a virtual environment, activate it first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source odatix_venv/bin/activate
{{< /code >}}
## Steps

### Step 1 — Initialize an example workspace

Create a new directory for the demonstration and move into it. For example:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/odatix_examples && cd ~/odatix_examples
{{< /code >}}

Create a new Odatix workspace and copy the built-in examples into it:

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix init --examples

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝

<font color="#555753">[settings.py]</font> <font color="#8AE234">Your directory can now be used by Odatix!</font>
<font color="#555753">[settings.py]</font> Run <b>odatix -h</b> to get a list of useful commands
{{< /code >}}

### Step 2 — Select the targeted tools and configurations

Open `odatix_userconfig/analysis_settings.yml`.
This is where you define the tools and configurations to check.  
Select the tool and
configurations to check.  
To disable a tool, comment it out with `#` or simply remove the line.

{{< code lang=yaml filename="odatix_userconfig/analysis_settings.yml" linenos="true" linenostart="24" >}}
tools:
  - vivado
  - verilator
  # - design_compiler

architectures:
  - Example_Counter_sv/*
  - Example_Counter_vhdl/*
{{< /code >}}

> [!NOTE]
> The `*` wildcard selects all configurations in the architecture's directory. You can replace it with a specific configuration name, or use multiple lines to select several configurations.

> [!INFO]
> Example_Counter_sv and Example_Counter_vhdl are two different implementations of the same counter design, one in SystemVerilog and the other in VHDL. The RTL is located in `examples/`. Their Odatix definitions are in `odatix_userconfig/architectures`.

### Step 3 — Run the analysis

{{< code filename="Terminal" prompt="true" fold="true" >}}
$ odatix analyze

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝


New architectures:
  - Example_Counter_sv/04bits (vivado)
  - Example_Counter_sv/08bits (vivado)
  - Example_Counter_sv/16bits (vivado)
  - Example_Counter_sv/24bits (vivado)
  - Example_Counter_sv/32bits (vivado)
  - Example_Counter_sv/48bits (vivado)
  - Example_Counter_sv/64bits (vivado)
  - Example_Counter_vhdl/04bits (vivado)
  - Example_Counter_vhdl/08bits (vivado)
  - Example_Counter_vhdl/16bits (vivado)
  - Example_Counter_vhdl/24bits (vivado)
  - Example_Counter_vhdl/32bits (vivado)
  - Example_Counter_vhdl/48bits (vivado)
  - Example_Counter_vhdl/64bits (vivado)
  - Example_Counter_sv/04bits (verilator)
  - Example_Counter_sv/08bits (verilator)
  - Example_Counter_sv/16bits (verilator)
  - Example_Counter_sv/24bits (verilator)
  - Example_Counter_sv/32bits (verilator)
  - Example_Counter_sv/48bits (verilator)
  - Example_Counter_sv/64bits (verilator)
  - Example_Counter_vhdl/04bits (verilator)
  - Example_Counter_vhdl/08bits (verilator)
  - Example_Counter_vhdl/16bits (verilator)
  - Example_Counter_vhdl/24bits (verilator)
  - Example_Counter_vhdl/32bits (verilator)
  - Example_Counter_vhdl/48bits (verilator)
  - Example_Counter_vhdl/64bits (verilator)

Total: 28
Continue? (Y/n)
{{< /code >}}

Odatix creates jobs in `work/analysis/`, then reports one of four outcomes for
every configuration: **PASSED**, **WARNING**, **INCOMPLETE** or **FAILED**.

You can also override the tool selection on the command line, for example to check only Vivado:
{{< code filename="Terminal" prompt="true" fold="true" >}}
$ odatix analyze -t vivado

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝


New architectures:
  - Example_Counter_sv/04bits
  - Example_Counter_sv/08bits
  - Example_Counter_sv/16bits
  - Example_Counter_sv/24bits
  - Example_Counter_sv/32bits
  - Example_Counter_sv/48bits
  - Example_Counter_sv/64bits
  - Example_Counter_vhdl/04bits
  - Example_Counter_vhdl/08bits
  - Example_Counter_vhdl/16bits
  - Example_Counter_vhdl/24bits
  - Example_Counter_vhdl/32bits
  - Example_Counter_vhdl/48bits
  - Example_Counter_vhdl/64bits

Total: 14
Continue? (Y/n)
{{< /code >}}

### Step 4 — Monitor the jobs

The job monitor shows the status of each job, and the log of the currently selected job. You can detach and re-attach to the monitor at any time. More information is available in [Sessions & Job Monitor](/docs/sessions/) documentation page.

> [!TIP]
> Use <kbd>PageUp</kbd> and <kbd>PageDown</kbd> keys to change jobs and the <kbd>Up</kbd> and <kbd>Down</kbd> keys to scroll logs. The mouse can also be used to scroll and select jobs.  
> Use <kbd>d</kbd> to detach and let the job run in the background, and run `odatix monitor` to re-attach.  
> Use <kbd>q</kbd> to quit when all jobs are complete.

### Step 5 — View the analysis dashboard

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Open the **RTL Analysis** dashboard to group configurations by status and see
error, warning and critical-warning counts.

{{< img src="/images/screenshots/explorer-analysis.png" alt="RTL Analysis dashboard" caption="RTL Analysis dashboard" shadow="false" >}}

> [!NOTE]
> A tool may accept RTL that another rejects. In this examples, Vivado accepts the VHDL counter, but Verilator rejects it because it does not support VHDL.

<!-- ## Troubleshooting
 -->


## Related resources

- **Reference** — [Run settings files](/docs/reference/run_settings/)
- **Reference** — [Commands](/docs/commands/)
- **Feature** — [RTL analysis](/docs/features/analysis/).
