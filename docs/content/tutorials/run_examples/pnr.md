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
> flow — see [step 6](#step-6--adapt-the-flow-to-your-pdk).


## Prerequisites

For this tutorial, you need **both**, installed and available in your `PATH`:
- an ASIC synthesis tool, which writes the gate-level netlist:
  [Synopsys Design Compiler](https://www.synopsys.com/implementation-and-signoff/rtl-synthesis.html)
  or [Cadence Genus](https://www.cadence.com/en_US/home/tools/digital-design-and-signoff/synthesis/genus-synthesis-solution.html);
- a place & route tool: [Cadence Innovus](https://www.cadence.com/en_US/home/tools/digital-design-and-signoff/soc-implementation-and-floorplanning/innovus-implementation-system.html)
  or [Synopsys IC Compiler II](https://www.synopsys.com/implementation-and-signoff/physical-implementation/ic-compiler.html).

The commands below use Design Compiler and Innovus on the AMS C35 1.8 V
technology, whose setup scripts Odatix ships. An FPGA tool such as Vivado places
& routes within its own synthesis flow, so it is not used here. See
[EDA tools](/install/eda_tools/#synopsys-and-cadence-tools) for their setup.

Make sure you have [Odatix installed](/install/) and available in your `PATH`. For example, if you installed Odatix in a virtual environment, activate it first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source odatix_venv/bin/activate
{{< /code >}}
## Steps

### Step 1 — Initialize an example workspace

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/odatix_pnr && cd ~/odatix_pnr
$ odatix init --examples
{{< /code >}}

The target files of the workspace, `odatix_userconfig/targets/target_design_compiler.yml`
and `target_innovus.yml`, both enable the `AMS_c35_1V8` target.

### Step 2 — Run the synthesis that will be the source

A place & route job has nothing to do without a synthesis to consume. Pick a
small design and one frequency:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t design_compiler -a Example_Counter_sv/08bits --at 100 --until netlist
{{< /code >}}

`-a` runs this configuration instead of the list of
`odatix_userconfig/synth_settings.yml`, and `--at` this frequency instead of the
ones of the design.

A synthesis stops by default once its area, timing and power are known; the
netlist is exported by the last step of the Design Compiler flow, `netlist`,
hence `--until netlist`. A synthesis that already ran picks up from where it
stopped. When it finishes, the job's result directory holds the three
**handoff files** place & route reads:

| File | Content |
|------|---------|
| `result/netlist.v` | The synthesized gate-level netlist. |
| `result/design.sdc` | The constraints it was synthesized under. |
| `result/design.sdf` | The delays back-annotated from synthesis. |

> [!IMPORTANT]
> If those files are absent, the synthesis cannot be a source — whatever its
> status says. A flow of your own must write them to be chainable.

### Step 3 — Select which synthesis jobs to implement

Open `odatix_userconfig/pnr_settings.yml`. Each entry of `sources` is a
**selector** pointing at completed synthesis jobs:

{{< code lang=text filename="Selector grammar" >}}
<source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]
{{< /code >}}

`*` works at every level. The file Odatix ships takes every completed
synthesis of the work directory, which is what this tutorial needs:

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
sources:
  - custom_freq_synthesis/*/*/*/*
  - fmax_synthesis/*/*/*/*
{{< /code >}}

To implement only some of them, list them instead:

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
sources:
  - custom_freq_synthesis/design_compiler/AMS_c35_1V8/Example_Counter_sv/08bits@100MHz
  - custom_freq_synthesis/design_compiler/AMS_c35_1V8/Example_Counter_sv/*
{{< /code >}}

A selection that matches no completed synthesis stops the run with the list of
the sources there are.

### Step 4 — Check the place & route target

The technology is selected in the target file of the place & route tool —
`odatix_userconfig/targets/target_innovus.yml` or `target_icc2.yml`. A place &
route job keeps the target of its synthesis, so this file lists the same target
names as the one of the synthesis tool; the workspace already does for
`AMS_c35_1V8`. This is also where the technology setup script that your PDK
needs is brought in:

{{< code lang=yaml filename="odatix_userconfig/targets/target_innovus.yml" >}}
constraint_file: timing_constraints.txt

script_copy_enable: No
script_copy_source: /dev/null

targets:
  - AMS_c35_1V8

target_settings:
  AMS_c35_1V8:
    script_copy_enable: Yes
    script_copy_source: $eda_tools_path/innovus/technology/AMS_c35_1V8/technology_setup.tcl
{{< /code >}}

The Innovus flow sources the script under the name `technology_setup.tcl`.
Odatix ships one for the AMS C35 1.8 V standard cells, to start yours from.

### Step 5 — Run the place & route

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix pnr -t innovus --from-tool design_compiler
{{< /code >}}

The flow runs as ordered, resumable **steps** — `init`, `place`, `cts`, `route`,
`signoff`. Each is its own process, handing the design over through a saved
database, so you can stop partway and continue later:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix pnr -t innovus --until init           # floorplan only, a first check of the setup
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
| `--from-flow` | Only jobs run with this flow of `--from-tool` (a flow the tool does not have is an error). |

### Step 6 — Adapt the flow to your PDK

> [!WARNING]
> The shipped Innovus and IC Compiler II definitions run the usual sequence, but
> the technology setup — LEF, QRC, MMMC, NDM libraries, power intent — is design
> and foundry specific. Adjust the scripts brought in by your target file before
> trusting the numbers.

For Innovus, the technology script declares what the flow steps need:

| Variable | Used by | Content |
|----------|---------|---------|
| `init_lef_file`, `init_mmmc_file` | `init` | Technology and cell LEF, MMMC setup (whose constraint mode reads `$source_sdc`). Without `init_mmmc_file`, `init` reads `$source_sdc` itself. |
| `init_pwr_net`, `init_gnd_net` | `init` | Power nets the cell supply pins are connected to. |
| `odatix_core_site` | `init` | Site of the core rows (default: the core site of the LEF). |
| `odatix_ring_layers` | `init` | Horizontal then vertical layer of the core power ring (no ring without it). |
| `odatix_cts_buffers`, `odatix_cts_inverters` | `cts` | Clock tree cells, for libraries that do not flag theirs. |
| `odatix_gds_map` | `signoff` | `streamOut` layer map file (no GDS without it). |

Adding another place & route tool is the same work as adding any other tool:
declare `pnr_steps` in a `tool.yml`. Your scripts reach the source job through
`$source_netlist`, `$source_sdc`, `$source_sdf` and `$source_work_path`. See
[Add non supported tools](/docs/tools/add_tools/).

### Step 7 — Compare estimate against reality

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Each tool exports into its own results file: the synthesis into
`results/results_design_compiler.yml`, the place & route into
`results/results_innovus.yml`, whose records name the synthesis they started
from (`source_type`, `source_tool`). Explorer reads both, so the synthesis
estimate and the implemented result of a configuration, same target, same
frequency, can be shown side by side — which is the whole point of running the
chain.

## Doing it from the GUI

`odatix-gui` → **Run jobs** → **Run place & route** lists the tools declaring a `pnr` job
type, then the sources actually available in your work directory — so you pick
from what exists instead of writing a selector. Choosing a step on the tool's
card runs up to that step.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| No sources found | The selector matches nothing (the error lists the sources there are), or the synthesis did not write the three handoff files (with Design Compiler, run it `--until netlist`). |
| `init` stops on "no technology_setup.tcl" | The target file brings in no technology script for this target. See [step 4](#step-4--check-the-place--route-target). |
| The tool is not offered | Its `tool.yml` declares no `pnr_command` / `pnr_steps`. |
| A run restarts from the beginning | A step recorded in `log/steps.yml` no longer matches the flow — the `tool.yml` changed. |
| Numbers look wrong | The technology setup is not yours yet. See [step 6](#step-6--adapt-the-flow-to-your-pdk). |

## Related resources

- **Feature** — [Place & route](/docs/features/pnr/).
- **Reference** — [Run settings files](/docs/reference/run_settings/#sources--place--route-inputs) · [Tool definitions](/docs/reference/tools/#steps) · [Target files](/docs/reference/targets/)
- **Guides** — [Tools and flows](/docs/tools/) · [Commands](/docs/commands/)
- **Related tutorial** — [Fixed-frequency synthesis](/tutorials/run_examples/synthesis/), which produces the source jobs.
