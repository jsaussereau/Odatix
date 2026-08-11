---
title: "Parallel Fmax Synthesis"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 4
description: "Run a parallel maximum-frequency synthesis on the built-in example designs, using the EDA tool of your choice."
categories: ["Tutorial", "Fmax"]
tags: ["fmax", "synthesis", "examples"]
featured_image: "/images/features/fmax-synthesis.svg"
---

{{< toc >}}

In this tutorial you will find the **maximum operating frequency** (Fmax) of several configurations of an example design, in parallel, on the FPGA or ASIC tool of your choice. It takes only a few commands.

## Prerequisites

For this tutorial, you need **at least one** of the following tools installed and available in your `PATH`:
- [AMD Vivado](https://www.xilinx.com/products/design-tools/vivado.html) (for Xilinx FPGAs)
- [Synopsys Design Compiler](https://www.synopsys.com/implementation-and-signoff/rtl-synthesis.html) (for ASICs)
- [Cadence Genus](https://www.cadence.com/en_US/home/tools/digital-design-and-signoff/synthesis/genus-synthesis-solution.html) (for ASICs)

[](/install/eda_tools/)

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

### Step 2 — Choose your target

Open the device or technology in the target file for your tool (`target_vivado.yml`, `target_design_compiler.yml`, or `target_openlane.yml`).

For instance for Vivado, open `odatix_userconfig/targets/target_vivado.yml` and select the target device:

{{< code lang=yaml filename="odatix_userconfig/targets/target_vivado.yml" linenos="true" linenostart="15" >}}
# FPGA target
targets:
  # - xc7s6-cpga196-1
  # - xc7s25-csga225-1
  # - xc7a15t-cpg236-1
  # - xc7a35t-cpg236-1
  - xc7a100t-csg324-1
  # - xc7k70t-fbg676-2
  # - xc7k70t-fbg676-3
  # - xc7k160t-fbg484-2
  # - xc7k160t-fbg484-3
  # - xc7k325t-ffg900-2
{{< /code >}}

To disable a target, comment it out with `#` or simply remove the line.  

> [!WARNING]
> With ASIC tools, the listed targets are only examples. You must provide your own target definition for your technology, with the correct libraries. See the [Add targets](/tutorials/own_flows/add_targets/) tutorial.

### Step 3 — Choose design configurations

Open `odatix_userconfig/fmax_synthesis_settings.yml` and select the architectures to run, exactly as for Fmax synthesis.

{{< code lang=yaml filename="odatix_userconfig/fmax_synthesis_settings.yml" linenos="true" linenostart="44" >}}
  - Example_Counter_verilog/04bits
  - Example_Counter_verilog/08bits
  - Example_Counter_verilog/16bits
  - Example_Counter_verilog/24bits
  - Example_Counter_verilog/32bits
  - Example_Counter_verilog/48bits
  - Example_Counter_verilog/64bits
{{< /code >}}

> [!NOTE]
> The `*` wildcard can be used to select all configurations in the architecture's directory instead of listing them one by one. You can list multiple architectures, and mix wildcards and specific configurations.

### Step 4 — Run

The frequency bounds for the binary search can be set in the command line with `--from` and `--to`. For example, to find the maximum frequency between 50 and 500 MHz for all configurations of the example counter design, run:

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix fmax --tool vivado --from 50 --to 500

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝


<b>New architectures:</b>
  - Example_Counter_verilog/04bits <font color="#555753">(50 - 500 MHz)</font>
  - Example_Counter_verilog/08bits <font color="#555753">(50 - 500 MHz)</font>
  - Example_Counter_verilog/16bits <font color="#555753">(50 - 500 MHz)</font>
  - Example_Counter_verilog/24bits <font color="#555753">(50 - 500 MHz)</font>
  - Example_Counter_verilog/32bits <font color="#555753">(50 - 500 MHz)</font>
  - Example_Counter_verilog/48bits <font color="#555753">(50 - 500 MHz)</font>
  - Example_Counter_verilog/64bits <font color="#555753">(50 - 500 MHz)</font>

<b>Total: 7</b>
Continue? (Y/n)
{{< /code >}}

> [!TIP]
> The bounds can also be set for each design in its `_settings.yml`, per target.

> [!INFO]
> Odatix enqueues one job per configuration/target in the daemon and attaches the Job Monitor.

### Step 5 — Monitor the jobs

The job monitor shows the status of each job, and the log of the currently selected job. You can detach and re-attach to the monitor at any time. More information is available in [Sessions & Job Monitor](/docs/sessions/) documentation page.

> [!TIP]
> Use <kbd>PageUp</kbd> and <kbd>PageDown</kbd> keys to change jobs and the <kbd>Up</kbd> and <kbd>Down</kbd> keys to scroll logs. The mouse can also be used to scroll and select jobs.  
> Use <kbd>d</kbd> to detach and let the job run in the background, and run `odatix monitor` to re-attach.  
> Use <kbd>q</kbd> to quit when all jobs are complete.

### Step 6 — Explore the results

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

> [!TIP]
> With this example, we can easily compare the maximum frequency of each configuration at a specific target.
> The chart below can be obtained by selecting the <kbd>Fmax</kbd> metric for the Y-axis.

{{< img src="/images/screenshots/explorer-fmax.png" shadow="false" >}}

> [!TIP]
> With this example, another interesting study is to compare the dynamic power consumption of each configuration at fmax, and compare it with [results from custom frequency synthesis](/tutorials/run_examples/synthesis/).
> The chart below can be obtained by selecting the <kbd>Dynamic Power</kbd> metric for the Y-axis, and  <kbd>Style</kbd> > <kbd>Color by</kbd> > <kbd>Frequency</kbd>.

{{< img src="/images/screenshots/explorer-fmax-lines.png" shadow="false" >}}

## Related resources

- **Reference** — [Architecture settings](/docs/reference/architecture/#frequency-settings) (Architecture-, configuration- and targets-pecific frequencies)
- **Reference** — [Run settings files](/docs/reference/run_settings/)
- **Reference** — [Target files](/docs/reference/targets/)
- **Reference** — [Commands](/docs/commands/)
- **Feature** — [Automated RTL synthesis](/docs/features/rtl_synthesis/).
