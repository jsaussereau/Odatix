---
draft: true
title: "Synthesize it"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 3
description: "The terminal variant of the common track, part 3: choose a synthesis target and start the fixed-frequency synthesis of the nine configurations with odatix synth, in the background."
categories: ["Tutorial", "Design"]
tags: ["workshop", "terminal", "synthesis", "cordic"]
featured_image: "/images/features/rtl-synthesis.svg"
next_tutorials: ["/tutorials/workshop/terminal/simulate"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Yosys + nextpnr, or your own synthesis tool | 15 min, then a few minutes in the background | Nine configurations synthesized |

The synthesis takes a while; the [next page](/tutorials/workshop/terminal/simulate/) has you write the
simulation while it runs.

## Step 1 — Choose the synthesis target

The page is written for **Yosys + nextpnr**, from the [OSS CAD
Suite](/install/oss_cad_suite/): free, and the same on every system. Another
synthesis tool works the same way — take its tab at each step. Whichever it
is, it has to work in your terminal before Odatix can drive it: Odatix runs the
executable the way you would. The **Tools** page of
`odatix-gui` says which tools answer here.

Each tool has a target file in `odatix_userconfig/targets/`, and every target
it enables is one more synthesis per configuration. Keep **one**:

{{< tabs >}}

{{% tab name="Yosys + nextpnr" %}}

Nothing to change: the default is a Lattice ECP5, which has the pins for every
width of the CORDIC.

{{< code lang=yaml filename="odatix_userconfig/targets/target_yosys_fpga.yml" >}}
targets:
  - ecp5-25k-CABGA381-6
{{< /code >}}

`yosys -V` and `nextpnr-ecp5 --version` must answer in your terminal: see
[Install the OSS CAD Suite](/install/oss_cad_suite/).

{{% /tab %}}

{{% tab name="Vivado" %}}

Nothing to change: the default is a small, fast Artix-7.

{{< code lang=yaml filename="odatix_userconfig/targets/target_vivado.yml" >}}
targets:
  - xc7a100t-csg324-1
{{< /code >}}

{{% /tab %}}

{{% tab name="Quartus" %}}

{{< code lang=yaml filename="odatix_userconfig/targets/target_quartus.yml" >}}
targets:
  - A3CW135BM16AE6S       # Agilex 3
  # - AGFB014R24B2E2V     # Agilex 7 F-Series
{{< /code >}}

Quartus is found through its target file rather than the `PATH`:
`tool_install_path` in the same file is the directory holding `qinit.sh`.

{{% /tab %}}

{{% tab name="Design Compiler / Genus" %}}

The targets of `target_design_compiler.yml` and `target_genus.yml` are
**examples**: one target is one technology setup script, which you have to
provide.

{{< code lang=yaml filename="odatix_userconfig/targets/target_design_compiler.yml" >}}
targets:
  - MY_TECH_1V2

target_settings:
  MY_TECH_1V2:
    script_copy_enable: Yes
    script_copy_source: /path/to/my/synopsys_dc_setup.tcl
{{< /code >}}

See [Add targets](/tutorials/own_flows/add_targets/). With no library at hand,
take an FPGA tool, or LibreLane, which brings its own open PDK.

{{% /tab %}}

{{% tab name="LibreLane (SystemVerilog only)" %}}

Nothing to change: the target is the open sky130 PDK. LibreLane has to be set
up first — see step 1 of [ASIC with open-source
tools](/tutorials/workshop/modules/asic/#step-1--point-odatix-at-your-librelane). It
reads the SystemVerilog core only.

{{% /tab %}}

{{< /tabs >}}

## Step 2 — Launch the synthesis

A **fixed-frequency synthesis** synthesizes each configuration once, at the
clock you give, and reports its area and its slack. Nine configurations, one
synthesis each:

{{< tabs >}}

{{% tab name="Yosys + nextpnr" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool yosys_fpga --at 100 -j 4 -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y
$ odatix synth --tool yosys_fpga --at 100 -j 4 -a "My_Cordic_vhdl + ITERATIONS/* + WIDTH/*" -y
{{< /code >}}

The first line for SystemVerilog, the second for VHDL. Each job synthesizes,
places and routes its configuration: about **two minutes** for the nine at
`-j 4` on a laptop. There is no step to stop at, so no `--until`. The area
metric is `LUT_count`.

{{% /tab %}}

{{% tab name="Vivado" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool vivado --at 100 --until synthesis -j 4 -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y
$ odatix synth --tool vivado --at 100 --until synthesis -j 4 -a "My_Cordic_vhdl + ITERATIONS/* + WIDTH/*" -y
{{< /code >}}

The first line for SystemVerilog, the second for VHDL. About **twelve
minutes** at `-j 4` on a laptop (Vivado 2024.2, Artix-7).

{{% /tab %}}

{{% tab name="Quartus" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool quartus --at 100 --until synthesis -j 4 -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y
$ odatix synth --tool quartus --at 100 --until synthesis -j 4 -a "My_Cordic_vhdl + ITERATIONS/* + WIDTH/*" -y
{{< /code >}}

The first line for SystemVerilog, the second for VHDL. The area metric is
`ALM_count`.

{{% /tab %}}

{{% tab name="Design Compiler / Genus" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool design_compiler --at 50 -j 4 -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y
$ odatix synth --tool genus           --at 50 -j 4 -a "My_Cordic_vhdl + ITERATIONS/* + WIDTH/*" -y
{{< /code >}}

Either tool, either language: change the name after `-a`. A synthesis of
Design Compiler or Genus has no later step, so there is no `--until`. On an
older technology, 50 MHz is a fairer question than 100. The area metric is
`Cell_Area`.

{{% /tab %}}

{{% tab name="LibreLane (SystemVerilog only)" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool librelane --at 40 --until synthesis -j 4 -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y
{{< /code >}}

On sky130 the core runs between 40 and 63 MHz, hence 40. The area metric is
`Cell_Area`.

{{% /tab %}}

{{< /tabs >}}

What the options say:

- `--at 100` — the clock frequency, in MHz. `--at` can be repeated, and
  `--from`/`--to`/`--step` sweep a range.
- `--until synthesis` (Vivado, Quartus, LibreLane) — stop each job after
  synthesis, where the numbers are optimistic but cheap. A later run without it
  **resumes** at place and route rather than starting over.
- `-j 4` — four jobs at once. On a shared virtual machine, fewer jobs with more
  cores each is often faster overall.

Odatix lists the nine jobs, hands them to its daemon and attaches the **Job
Monitor**:

{{< img src="/images/screenshots/job-monitor.png" title="The Job Monitor: one line per job, the log of the selected one below" shadow="false" >}}

> [!TIP]
> In the monitor: <kbd>PageUp</kbd> / <kbd>PageDown</kbd> change job,
> <kbd>Up</kbd> / <kbd>Down</kbd> scroll the log. **Press <kbd>d</kbd> now**:
> it detaches and leaves the jobs running. `odatix monitor` re-attaches,
> `odatix ps` says how far they are.

**Do not wait for it.** The synthesis runs in the background, on its own, and
the next page needs nothing but your simulator.

{{< details title="No synthesis tool on this machine?" >}}
Skip this step: nothing in the next page depends on it. Ask for the **results
bundle** — a `results/` directory from a complete run — to see the synthesis
results at the end of the next page, and take [Shape your own design
space](/tutorials/workshop/modules/design_space/) as your first module: it needs no EDA
tool at all.
{{< /details >}}

## If something did not work

| Symptom | What to do |
|---|---|
| `odatix synth` runs many more than nine jobs | Step 1: exactly one target enabled in the target file of your tool. |
| Every synthesis job fails at once | Run [the analysis](/tutorials/workshop/terminal/analysis/) with your synthesis tool (`--tool yosys` for Yosys + nextpnr, `--tool vivado`...): it says whether the tool or the design is at fault. |
