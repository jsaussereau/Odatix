---
title: "Place & Route a Synthesized Design"
date: 2026-08-01
author: "Jonathan Saussereau"
weight: 5
description: "Chain two EDA tools: synthesize with one, then place & route the resulting netlist with another, and compare estimates against post-route reality."
categories: ["Tutorial", "PNR"]
tags: ["pnr", "innovus", "icc2", "asic"]
featured_image: "/images/features/pnr.svg"
---

{{< toc >}}

`odatix pnr` is the only job type that starts from **another job's output**: it
takes a synthesis that already ran and succeeded, and places & routes it with a
second tool. This tutorial runs that chain end to end.

> [!IMPORTANT] Requires Odatix 4.0+

> [!NOTE]
> You need a synthesis tool (Design Compiler or Genus) **and** a place & route
> tool (Innovus or IC Compiler II), each with its own installation and licence.
> The shipped place & route definitions are a starting point, not a validated
> flow — see [Step 6](#step-6--adapt-the-flow-to-your-pdk).


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

### Step 1 — Run a synthesis

### Step 2 — Run the synthesis that will be the source

A place & route job has nothing to do without a synthesis to consume. Pick a
small design and one frequency:

{{< code lang=yaml filename="odatix_userconfig/custom_freq_synthesis_settings.yml" >}}
nb_jobs: 4

architectures:
  - Example_Counter_sv/08bits
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t design_compiler --at 100
{{< /code >}}

When it finishes, the job's result directory holds the three **handoff files**
place & route reads:

| File | Content |
|------|---------|
| `result/netlist.v` | The synthesized gate-level netlist. |
| `result/design.sdc` | The constraints it was synthesized under. |
| `result/design.sdf` | The delays back-annotated from synthesis. |

> [!IMPORTANT]
> If those files are absent, the synthesis cannot be a source — whatever its
> status says. A flow of your own must write them to be chainable.

### Step 3 — Select which synthesis jobs to implement

Open `odatix_userconfig/pnr_settings.yml`. Each entry is a **selector** pointing
at completed synthesis jobs:

{{< code lang=text filename="Selector grammar" >}}
<source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
nb_jobs: 4

sources:
  - custom_freq_synthesis/design_compiler/gf22/Example_Counter_sv/08bits@100MHz
{{< /code >}}

`*` works at every level, so widening it later is one character at a time:

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
sources:
  - custom_freq_synthesis/design_compiler/gf22/Example_Counter_sv/*
  - fmax_synthesis/genus/*/*/*
{{< /code >}}

### Step 4 — Choose the place & route target

Select the technology in the target file of your place & route tool —
`odatix_userconfig/targets/target_innovus.yml` or `target_icc2.yml`. This is
where the technology setup script that your PDK needs is brought in:

{{< code lang=yaml filename="odatix_userconfig/targets/target_innovus.yml" >}}
constraint_file: constraints.sdc

script_copy_enable: Yes
script_copy_source: "techno/gf22_setup.tcl"

targets:
  - gf22
{{< /code >}}

### Step 5 — Run the place & route

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix pnr -t innovus --from-tool design_compiler
{{< /code >}}

The flow runs as ordered, resumable **steps** — `init`, `place`, `cts`, `route`,
`signoff`. Each is its own process, handing the design over through a saved
database, so you can stop partway and continue later:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix pnr -t innovus --until route          # stop after routing
$ odatix pnr -t innovus                        # continue from where it stopped
$ odatix pnr -t innovus --rerun-from place     # redo placement onwards
{{< /code >}}

The command line can also narrow which synthesis jobs are used, without touching
the settings file:

| Option | Meaning |
|--------|---------|
| `--from-type` | Only `fmax_synthesis` or only `custom_freq_synthesis` jobs. |
| `--from-tool` | Only jobs run with this eda tool. |
| `--from-flow` | Only jobs run with this flow of `--from-tool`. |

### Step 6 — Adapt the flow to your PDK

> [!WARNING]
> The shipped Innovus and IC Compiler II definitions run the usual sequence, but
> the technology setup — LEF, QRC, MMMC, NDM libraries, power intent — is design
> and foundry specific. Adjust the scripts brought in by your target file before
> trusting the numbers.

Adding another place & route tool is the same work as adding any other tool:
declare `pnr_steps` in a `tool.yml`. Your scripts reach the source job through
`$source_netlist`, `$source_sdc`, `$source_sdf` and `$source_work_path`. See
[Add non supported tools](/docs/tools/add_tools/).

### Step 7 — Compare estimate against reality

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Both runs export into the same results files, so the synthesis estimate and the
implemented result sit next to each other per configuration — which is the whole
point of running the chain.

## Doing it from the GUI

`odatix-gui` → **Run** → **Place & Route** lists the tools declaring a `pnr` job
type, then the sources actually available in your work directory — so you pick
from what exists instead of writing a selector. Choosing a step on the tool's
card runs up to that step.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| No sources found | The selector matches nothing, or the synthesis did not write the three handoff files. |
| The tool is not offered | Its `tool.yml` declares no `pnr_command` / `pnr_steps`. |
| A run restarts from the beginning | A step recorded in `log/steps.yml` no longer matches the flow — the `tool.yml` changed. |
| Numbers look wrong | The technology setup is not yours yet. See [step 6](#step-6--adapt-the-flow-to-your-pdk). |

## Related resources

- **Feature** — [Place & route](/docs/features/pnr/).
- **Reference** — [Run settings files](/docs/reference/run_settings/#sources--place--route-inputs) · [Tool definitions](/docs/reference/tools/#steps) · [Target files](/docs/reference/targets/)
- **Guides** — [Tools and flows](/docs/tools/) · [Commands](/docs/commands/)
- **Related tutorial** — [Custom-frequency synthesis](/tutorials/run_examples/synthesis/), which produces the source jobs.
