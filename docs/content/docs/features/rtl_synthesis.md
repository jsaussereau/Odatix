---
title: "Automated RTL Synthesis"
description: "Run synthesis for every configuration of your design across FPGA and ASIC tools, at the frequencies you choose, and collect area, resource, timing and power metrics automatically."
layout: "doc-features"
badge: "Implementation"
badgeColor: "#7c3aed"
cta: true
weight: 3
features:
  - title: "FPGA & ASIC"
    description: "Target FPGA devices and ASIC technologies from the same design and the same command."
  - title: "Multiple tools"
    description: "Drives AMD Vivado, Synopsys Design Compiler, Cadence Genus and OpenLane — and anything you wrap yourself."
  - title: "Every configuration"
    description: "Each configuration of each design is synthesized independently, in parallel."
  - title: "Metrics out of the box"
    description: "Area, LUTs, registers, DSPs, timing and power are extracted and tabulated automatically."
---

## From RTL to metrics, automatically

Odatix wraps the EDA tools you already use and runs them for you. You point it at
a design, pick a target and a tool, and it synthesizes **every configuration** —
extracting the metrics you care about into a single, comparable table.

This page covers **custom-frequency synthesis** (`odatix synth`): synthesis at
clock constraints *you* choose. Its sibling,
[fmax synthesis](/docs/features/rtl_fmax_synthesis/), searches for the highest
frequency a configuration can reach.

| Mode | Command | What it answers |
|------|---------|-----------------|
| **Custom-frequency synthesis** | `odatix synth` | *"How does this configuration behave at 200 MHz?"* |
| **Fmax synthesis** | `odatix fmax` | *"How fast can this configuration go?"* |

<!-- ![Synthesis results in the Explorer table: one row per configuration, target and frequency](/images/screenshots/synthesis-results.png) -->

## When you need it

- **Power/frequency trade-offs.** Power only means something at a stated clock.
  Synthesize at 100, 200, 300 and 400 MHz and watch it climb.
- **Comparing configurations fairly at a fixed clock.** Every variant meets the
  same constraint, so differences in area and power belong to the design, not to
  how hard the tool tried.
- **Meeting a specification.** Your system runs at 250 MHz: synthesize there and
  see which configurations close timing and what they cost.
- **Comparing targets.** The same design on two FPGAs or two technology nodes,
  from one settings file.
- **Comparing flows.** A timing-oriented flow against a power-optimized one, on
  the same design, in the same results file.

## How it works

Every **configuration × target × frequency** triple is an independent job. Odatix
prepares an isolated work directory for each one — copying the RTL, splicing the
configuration's parameters in, writing the timing constraint — then runs the
tool's script and extracts the metrics from its reports.

Jobs are scheduled across your CPU cores through the Odatix daemon, so a large
sweep finishes as fast as your machine allows, and the
[Job Monitor](/docs/gui/monitor/) shows progress and logs live. A job whose
result already exists is skipped unless you ask for `--overwrite`.

Two mechanisms shape *how* a tool is run:

- **[Flows](/docs/commands/#selecting-a-flow)** — alternative ways of running the
  same tool (Vivado timing-oriented versus power-optimized with clock gating,
  Design Compiler with `dc_shell` versus `dcnxt_shell`). Each runs in its own
  work directory and is exported into the same results file, tagged with a `flow`
  key, so Explorer compares them directly.
- **[Steps](/docs/reference/tools/#steps)** — a flow split into resumable stages
  (`synthesis`, `pnr`, `bitstream`). Stop at post-synthesis estimates for a whole
  design space, then carry only the interesting part further.

> [!NOTE]
> The EDA tools themselves are **not** included with Odatix. You need your own
> installation and licence. See [Install EDA tools](/install/eda_tools/).

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | Supplies the configurations being synthesized — this feature is what makes exploring worth it. |
| [RTL analysis](/docs/features/analysis/) | Run it first: seconds of elaboration save hours of synthesis on a broken configuration. |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) | Find the ceiling with `fmax`, then study behaviour below it with `synth`. |
| [Place & route](/docs/features/pnr/) | Hand the netlist to a second tool for post-route numbers. |
| [Simulation](/docs/features/simulation/) | Cycles from a testbench plus Fmax from a synthesis give real runtime, via [derived metrics](/docs/results/derived_metrics/). |
| [Explorer](/docs/features/explorer/) | Turns the resulting table into charts you can publish. |

## Using it

### From the configuration files and the CLI

Three files matter. Which designs to run:

{{< code lang=yaml filename="odatix_userconfig/custom_freq_synthesis_settings.yml" >}}
nb_jobs: 8

architectures:
  - Example_Counter_verilog/08bits        # only the 8-bit configuration
  - Example_ALU_sv/*                      # all configurations
  - Example_Rom_Chisel + addr/* + data/*  # every combination of every domain
{{< /code >}}

Which devices or technologies to run on:

{{< code lang=yaml filename="odatix_userconfig/targets/target_vivado.yml" >}}
constraint_file: constraints.xdc
targets:
  - xc7a100t-csg324-1
  - xcku035-fbva676-3-e
{{< /code >}}

And which frequencies, in the design's own settings — globally, per target, or
per configuration:

{{< code lang=yaml filename="architectures/Example_ALU_sv/_settings.yml" >}}
custom_freq_synthesis:
  lower_bound: 100
  upper_bound: 400
  step: 100
{{< /code >}}

Then run, overriding the frequency set on the command line when you want a
one-off:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool vivado
$ odatix synth --tool vivado --from 100 --to 500 --step 50
$ odatix synth --tool openlane --at 50 --at 100 --at 150
$ odatix synth --tool vivado --flow power_opt --until pnr
$ odatix synth --tool design_compiler -j auto -d -S nightly   # detached session
{{< /code >}}

Every key is in the [architecture](/docs/reference/architecture/#frequency-settings),
[run settings](/docs/reference/run_settings/) and
[target file](/docs/reference/targets/) references; every option in the
[commands reference](/docs/commands/).

### From the GUI

`odatix-gui` → **Run Jobs** → **Custom Frequency Synthesis** walks the same
path: pick the tool (its card shows the available flows, and the steps you can
stop at), pick the targets, set the frequency range, the designs and the number
of parallel jobs, and launch. The page writes the same settings files before
enqueueing, and drops you on the Monitor — where a run started from a terminal
shows up too, since there is one daemon for both.

## Where to go next

- **Tutorial** — [Custom-frequency synthesis](/tutorials/run_examples/synthesis/), on the bundled examples.
- **Reference** — [Architecture settings](/docs/reference/architecture/) · [Run settings files](/docs/reference/run_settings/) · [Target files](/docs/reference/targets/) · [Tool definitions](/docs/reference/tools/)
- **Guides** — [Commands](/docs/commands/) · [Tools and flows](/docs/tools/)
- **Next feature** — [Maximum frequency search](/docs/features/rtl_fmax_synthesis/).
