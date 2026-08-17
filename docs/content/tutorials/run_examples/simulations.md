---
title: "Parallel Simulations"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 2
description: "Validate and benchmark every configuration of an example design in parallel, using a simulator such as Verilator or GHDL."
categories: ["Tutorial", "Simulation"]
tags: ["simulation", "verilator", "ghdl", "examples"]
featured_image: "/images/features/simulation.svg"
---

{{< toc >}}

In this tutorial, you will run **simulations** for every configuration of a Cordic example design. This design has two parameters: `iterations` and `width`. Each parameter has several values, which combine into several configurations. Odatix will run a simulation for each configuration, in parallel. This example has two identical implementations, one in SystemVerilog and one in VHDL.

## Prerequisites

For this tutorial, you need **at least one** of the following tools installed and available in your `PATH`:
- [Verilator](https://www.veripool.org/verilator/)
- [GHDL](https://github.com/ghdl/ghdl)
- [QuestaSim](https://www.mentor.com/products/fv/questa/) / [ModelSim](https://www.mentor.com/products/fv/modelsim/)
- [Vivado](https://www.xilinx.com/products/design-tools/vivado.html)

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

### Step 2 — Choose what to simulate

Open `odatix_userconfig/simulations_settings.yml`. Each entry maps a **simulation** to the list of **architectures** to run it on:

{{< code lang=yaml filename="odatix_userconfig/simulations_settings.yml" linenos="true" linenostart="23" >}}
simulations:
  - TB_Example_Cordic_Verilator:
    - Example_Cordic_sv + iterations/* + width/*
 
  - TB_Example_Cordic_GHDL:
    - Example_Cordic_vhdl + iterations/* + width/*

  - TB_Example_Cordic_QuestaSim:
    - Example_Cordic_sv + iterations/* + width/*
    - Example_Cordic_vhdl + iterations/* + width/*

  - TB_Example_Cordic_Vivado:
    - Example_Cordic_sv + iterations/* + width/*
    - Example_Cordic_vhdl + iterations/* + width/*

  # - TB_Example_Counter_GHDL:
  #   - Example_Counter_vhdl/*

  # - TB_Example_Counter_Verilator:
  #   - Example_Counter_sv/*
{{< /code >}}

To disable a confiuguration and/or simulation, comment it out with `#` or simply remove the line.  

> [!NOTE]
> The `*` wildcard selects all configurations in the architecture's directory. You can replace it with a specific configuration name, or use multiple lines to select several configurations. Here ` + iterations/* + width/*` means "all combinations of the `iterations` and `width` parameters". 

### Step 3 — Run

Simulations are run with the `odatix sim` command:

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix sim

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝


<b>New simulations:</b>
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:4]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:8]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:12]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:4]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:8]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:12]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:4]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:8]
  - TB_Example_Cordic_Verilator: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:12]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:4]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:12]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:4]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:8]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:12]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:4]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:8]
  - TB_Example_Cordic_GHDL: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:12]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:4]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:8]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:12]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:4]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:8]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:12]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:4]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:8]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:12]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:4]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:12]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:4]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:8]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:12]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:4]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:8]
  - TB_Example_Cordic_QuestaSim: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:12]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:4]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:8]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:12, width:12]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:4]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:8]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:16, width:12]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:4]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:8]
  - TB_Example_Cordic_Vivado: Example_Cordic_sv/Example_Cordic_sv [iterations:24, width:12]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:4]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:12]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:4]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:8]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:16, width:12]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:4]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:8]
  - TB_Example_Cordic_Vivado: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:24, width:12]

<b>Total: 54</b>
Continue? (Y/n)
{{< /code >}}

> [!NOTE]
> Like every run command, `sim` enqueues jobs in the daemon and attaches the Job Monitor, so you see progress and logs for each configuration live.


### Step 4 — Monitor the jobs

The job monitor shows the status of each job, and the log of the currently selected job. You can detach and re-attach to the monitor at any time. More information is available in [Sessions & Job Monitor](/docs/sessions/) documentation page.

> [!TIP]
> Use <kbd>PageUp</kbd> and <kbd>PageDown</kbd> keys to change jobs and the <kbd>Up</kbd> and <kbd>Down</kbd> keys to scroll logs. The mouse can also be used to scroll and select jobs.  
> Use <kbd>d</kbd> to detach and let the job run in the background, and run `odatix monitor` to re-attach.  
> Use <kbd>q</kbd> to quit when all jobs are complete.

### Step 5 — Explore the results

What each simulation exports is declared in its `_metrics.yml`; results land in
`results/results_simulation.yml` as jobs finish. Re-export at any time — for
instance after editing a metric — then open the dashboard:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

## Going further

Because simulation metrics live next to synthesis metrics, you can answer questions that need both — such as *which configuration has the best benchmark score per watt/usage/area.* Computing a value from both, such as a runtime, is what [derived metrics](/docs/results/derived_metrics/) are for.

For validation pipelines with several steps, dependencies or non-HDL tools, use [workflows](/docs/features/workflows/) instead of `sim`.

## Related resources

- **Your own testbench** — [Simulate your own RTL](/tutorials/own_designs/simulations/).
- **Feature** — [Simulation & validation](/docs/features/simulation/).
- **Reference** — [Simulation settings](/docs/reference/simulation/) · [Run settings files](/docs/reference/run_settings/#simulations--testbench-to-configurations) · [Metrics files](/docs/reference/metrics/)
- **Next** — [Explore your results](/tutorials/run_examples/rtl_analysis/).
