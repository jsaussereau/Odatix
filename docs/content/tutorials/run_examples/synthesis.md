---
title: "Custom-Frequency Synthesis"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 3
description: "Synthesize an example design at the specific clock frequencies you choose, to study frequency, area and power trade-offs."
categories: ["Tutorial", "Synthesis"]
tags: ["synthesis", "frequency", "examples"]
featured_image: "/images/features/rtl-synthesis.svg"
---

{{< toc >}}

Where [Fmax synthesis](/tutorials/run_examples/fmax_synthesis/) answers *"how fast can it go?"*, **custom-frequency synthesis** answers *"how does it behave at these specific frequencies?"*. It is the tool for power/frequency and area/frequency trade-off studies.


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

Open `odatix_userconfig/custom_freq_synthesis_settings.yml` and select the architectures to run, exactly as for Fmax synthesis.

{{< code lang=yaml filename="odatix_userconfig/custom_freq_synthesis_settings.yml" linenos="true" linenostart="44" >}}
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

Synthesis can be run at specific frequencies, or in a range with a step, or both. For example:


{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix synth --tool vivado --at 50 --at 100

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝


<b>New architectures:</b>
  - Example_Counter_verilog/04bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 100 MHz</font>

<b>Total: 14</b>
Continue? (Y/n)
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix synth --tool vivado --from 100 --to 300 --step 50

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝


<b>New architectures:</b>
  - Example_Counter_verilog/04bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 150 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 200 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 250 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 300 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 150 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 200 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 250 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 300 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 150 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 200 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 250 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 300 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 150 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 200 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 250 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 300 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 150 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 200 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 250 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 300 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 150 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 200 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 250 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 300 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 150 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 200 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 250 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 300 MHz</font>

<b>Total: 35</b>
Continue? (Y/n)
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix synth --tool vivado --at 50 --from 100 --to 150 --step 20

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝

<b>New architectures:</b>
  - Example_Counter_verilog/04bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 120 MHz</font>
  - Example_Counter_verilog/04bits <font color="#555753">@ 140 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 120 MHz</font>
  - Example_Counter_verilog/08bits <font color="#555753">@ 140 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 120 MHz</font>
  - Example_Counter_verilog/16bits <font color="#555753">@ 140 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 120 MHz</font>
  - Example_Counter_verilog/24bits <font color="#555753">@ 140 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 120 MHz</font>
  - Example_Counter_verilog/32bits <font color="#555753">@ 140 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 120 MHz</font>
  - Example_Counter_verilog/48bits <font color="#555753">@ 140 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 50 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 100 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 120 MHz</font>
  - Example_Counter_verilog/64bits <font color="#555753">@ 140 MHz</font>

<b>Total: 28</b>
Continue? (Y/n)
{{< /code >}}

> [!TIP]
> The frequencies can also be set for each design in its `_settings.yml`, per target — as a `list`, a `range`, or both.

> [!INFO]
> Odatix enqueues one job per configuration/target/frequency in the daemon and attaches the Job Monitor.

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
> With this example, an interesting study is to compare the dynamic power consumption of each configuration at different frequencies.  
> The chart below can be obtained by selecting the <kbd>Dynamic Power</kbd> metric for the Y-axis, and  <kbd>Style</kbd> > <kbd>Color by</kbd> > <kbd>Frequency</kbd>.

{{< img src="/images/screenshots/explorer-freq-lines.png" alt="RTL Analysis dashboard" caption="RTL Analysis dashboard" shadow="false" >}}

## Related resources

- **Reference** — [Architecture settings](/docs/reference/architecture/#frequency-settings) (Architecture-, configuration- and targets-pecific frequencies)
- **Reference** — [Run settings files](/docs/reference/run_settings/)
- **Reference** — [Target files](/docs/reference/targets/)
- **Reference** — [Commands](/docs/commands/)
- **Feature** — [Automated RTL synthesis](/docs/features/rtl_synthesis/).
