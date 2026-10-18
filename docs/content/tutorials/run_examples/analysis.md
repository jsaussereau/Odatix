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
- [AMD Vivado](https://www.xilinx.com/products/design-tools/vivado.html) (for Xilinx FPGAs)
- [Altera Quartus Prime Pro](https://www.altera.com/downloads) (for Altera FPGAs)
- [Synopsys Design Compiler](https://www.synopsys.com/implementation-and-signoff/rtl-synthesis.html) (for ASICs)
- [Cadence Genus](https://www.cadence.com/en_US/home/tools/digital-design-and-signoff/synthesis/genus-synthesis-solution.html) (for ASICs)

Make sure you have [Odatix installed](/install/) and available in your `PATH`. For example, if you installed Odatix in a virtual environment, activate it first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source odatix_venv/bin/activate
{{< /code >}}
## Steps

### Step 1 — Initialize an example workspace

Create a new directory for the demonstration and move into it. For example:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p ~/odatix_examples && cd ~/odatix_examples
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

<font color="#555753">[odatix init]</font> <font color="#34E2E2">note: This command will create all the configuration files needed by Odatix in the current directory.</font>
<font color="#555753">[odatix init]</font> Would you like to continue? (Y/n) y
<font color="#555753">[odatix init]</font> <font color="#8AE234">Your directory can now be used by Odatix!</font>
<font color="#555753">[odatix init]</font> Try a first run (with your tool in place of vivado): <b>odatix fmax --tool vivado -a "Example_Counter_verilog/08bits" --until synthesis</b>
<font color="#555753">[odatix init]</font> Run <b>odatix -h</b> to get a list of useful commands
<font color="#555753">[odatix init]</font> New to Odatix? Follow https://odatix.readthedocs.io/en/latest/docs/getting-started/
{{< /code >}}

### Step 2 — Select the targeted tools and configurations

Open `odatix_userconfig/analyze_settings.yml`.
This is where you define the tools and configurations to check.
To disable a tool, comment it out with `#` or simply remove the line.
Keep only the tools installed on your machine: a listed tool that cannot be
launched is reported as an error and its analyses are skipped, while the other
tools run (when none of them can, the run stops).

{{< code lang=yaml filename="odatix_userconfig/analyze_settings.yml" linenos="true" linenostart="22" >}}
tools:
  - vivado
  - verilator
  # - quartus
  # - design_compiler
  # - genus
{{< /code >}}

Further down, the `architectures` list selects the configurations; the
examples section of the file selects the two counters:

{{< code lang=yaml filename="odatix_userconfig/analyze_settings.yml" linenos="true" linenostart="67" >}}
  - Example_Counter_sv/*
  - Example_Counter_vhdl/*
  # - Example_Counter_verilog/*
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

Odatix creates jobs in `work/analysis/`, runs them through the daemon, and once
they are done prints its report: the status of every configuration with each
tool — **Passed**, **Warnings**, **Failed**, **Tool failure**, **Incomplete** or
**Not supported** — the kinds of findings each tool reported, and one line per
configuration that needs attention. Verilator does not read VHDL: the
`Example_Counter_vhdl` configurations are reported as *not supported* by it.
See [RTL analysis](/docs/features/analysis/#how-it-works) for what each status
means.

An analysis that already ran is not run again: after changing the RTL, run
`odatix analyze -o` to analyze it anew.

The command line can also override the tool selection, for example to check only Vivado (here on a workspace where nothing was analyzed yet; otherwise, those analyses are already done and skipped):
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

The job monitor shows the status of each job, and the log of the currently selected job. You can detach and re-attach to the monitor at any time. More information is available in [Sessions & job monitor](/docs/sessions/) documentation page.

> [!TIP]
> Use <kbd>PageUp</kbd> and <kbd>PageDown</kbd> keys to change jobs and the <kbd>Up</kbd> and <kbd>Down</kbd> keys to scroll logs. The mouse can also be used to scroll and select jobs.  
> Use <kbd>d</kbd> to detach and let the job run in the background, and run `odatix monitor` to re-attach.  
> Use <kbd>q</kbd> to quit when all jobs are complete.

A job of the monitor says whether its tool ran, not what it found: the job of a
design with errors in its RTL is done all the same, its verdict being in the
report printed at the end. A job fails when the tool could not analyze the
design (not installed, no licence, stopped before the end): the report then
says **Tool failure** or **Incomplete**.

### Step 5 — View the analysis dashboard

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Open the **RTL analysis** page. It counts the configurations of each status
(click one to keep only them), shows the status of every configuration with each
tool, then the kinds of findings each tool reported (click one to keep the
configurations it was reported for). Below, every configuration lists what needs
attention first, with the source excerpt the tool printed, and the expected
findings apart.

{{< img src="/images/screenshots/explorer-analysis.png" alt="RTL analysis page of Odatix Explorer" caption="RTL analysis page of Odatix Explorer" shadow="false" >}}

> [!NOTE]
> A tool may accept RTL that another cannot read. In these examples, Vivado
> accepts the VHDL counter, while Verilator reports it as *not supported*: it
> does not read VHDL.

<!-- ## Troubleshooting
 -->


## Related resources

- **Reference** — [Run settings files](/docs/reference/run_settings/)
- **Reference** — [Commands](/docs/commands/)
- **Feature** — [RTL analysis](/docs/features/analysis/).
