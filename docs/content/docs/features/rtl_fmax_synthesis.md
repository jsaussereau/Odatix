---
title: "Maximum Frequency Search"
description: "Automatically find the maximum operating frequency (Fmax) of any digital design, for every configuration and every target, in parallel."
layout: "doc-features"
badge: "Implementation"
badgeColor: "#0ea5e9"
cta: true
weight: 4
features:
  - title: "Fully automatic"
    description: "No scripting: Odatix drives the tool, reads timing, and converges to Fmax on its own."
  - title: "Binary search"
    description: "A binary search on the clock constraint finds Fmax in a handful of synthesis runs."
  - title: "Per-target bounds"
    description: "Set search bounds per target and per configuration to keep runs fast and relevant."
  - title: "Massively parallel"
    description: "Every configuration and target searches for its own Fmax at the same time."
---

## What is Fmax synthesis?

The **maximum operating frequency** (Fmax) is one of the most telling metrics of
a digital design: it says how fast a configuration can run on a given target. But
finding it by hand is tedious — you tighten the clock constraint, re-synthesize,
check whether timing still closes, and repeat until you converge.

Odatix does exactly that, automatically. Give it a lower and an upper bound, and
it performs a **binary search** on the clock constraint until it pins down the
highest frequency at which timing closes — for **each configuration** of your
design and **each target** you selected.

![Fmax across configurations of a RISC-V core, one curve per multiplier variant](/images/screenshots/fmax-lines.png)

## When you need it

- **Comparing architectures fairly.** The fastest 8-bit ALU against the fastest
  32-bit ALU, each at *its own* best clock, on the same FPGA. Anything else
  compares tool effort rather than designs.
- **Finding the ceiling of a design.** Before choosing a system clock, you need
  to know what the block can actually sustain.
- **Measuring the cost of a feature.** Adding a bypass path or a wider datapath
  costs frequency — this quantifies it, per configuration.
- **Qualifying across targets.** The same RTL on a mid-range and a high-end FPGA,
  or on two technology nodes, each with its own bounds.
- **Feeding derived metrics.** Fmax is the denominator of real runtime: cycles
  from a simulation divided by Fmax from here. See
  [derived metrics](/docs/metrics/derived/).

## How it works

Each configuration/target pair gets its own binary search. Odatix synthesizes at
a candidate frequency, reads the timing report, and moves the bound that the
result rules out — closing timing raises the floor, failing lowers the ceiling —
until the interval collapses on the highest frequency that still passes.

Every search runs as an independent job in the daemon, so a whole design space
converges in parallel and the [Job Monitor](/docs/gui/monitor/) shows each search
narrowing live.

Bounds matter. Too wide and you pay for synthesis runs that were never going to
be the answer; too narrow and a search stops at an edge without having found the
real maximum. That is why they can be set per target and per configuration.

A tool whose fmax flow is [split into steps](/docs/reference/tools/#steps-of-an-fmax-search)
searches at increasing depth: `synthesis` converges on post-synthesis timing —
fast and optimistic, ideal for screening a large space — while `pnr` converges on
post-route timing, which is what the design really reaches. Screen cheaply, then
implement only the part of the space that turned out to be worth it.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | Every configuration gets its own Fmax — this is what makes a design space explorable. |
| [RTL analysis](/docs/features/analysis/) | A configuration that does not elaborate wastes an entire binary search. Check first. |
| [Custom-frequency synthesis](/docs/features/rtl_synthesis/) | Once you know the ceiling, study area and power below it. |
| [Place & route](/docs/features/pnr/) | Take the netlist of a completed fmax job to a second tool for post-route numbers. |
| [Simulation](/docs/features/simulation/) | Cycles × 1/Fmax = real runtime, across the whole space. |
| [Explorer](/docs/features/explorer/) | Fmax across configurations is the chart this feature exists for. |

## Using it

### From the configuration files and the CLI

Bounds live in the design's `_settings.yml`, and can be tuned per target and per
configuration so no synthesis run is wasted:

{{< code lang=yaml filename="architectures/ALU/_settings.yml" >}}
fmax_synthesis:              # applies everywhere
  lower_bound: 50
  upper_bound: 500

xc7s25-csga225-1:            # ... except on this target
  fmax_synthesis:
    lower_bound: 100
    upper_bound: 450

xc7a100t-csg324-1:
  fmax_synthesis:
    lower_bound: 50
    upper_bound: 800
  32bits:                    # ... and this configuration of it
    fmax_synthesis:
      upper_bound: 600
{{< /code >}}

Which designs and how many jobs at once come from the run settings file, and the
targets from the tool's target file — exactly as for
[custom-frequency synthesis](/docs/features/rtl_synthesis/#from-the-configuration-files-and-the-cli):

{{< code lang=yaml filename="odatix_userconfig/fmax_synthesis_settings.yml" >}}
nb_jobs: 12

architectures:
  - Example_ALU_sv/*
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado
$ odatix fmax --tool design_compiler --from 100 --to 900   # narrow this run only
$ odatix fmax --tool vivado --until synthesis              # screen cheaply first
$ odatix fmax --tool vivado -j auto -d -S nightly          # detached session
{{< /code >}}

Every key is on the
[architecture settings reference](/docs/reference/architecture/#frequency-settings);
every option on the [commands reference](/docs/commands/).

### From the GUI

`odatix-gui` → **Run Jobs** → **Fmax Synthesis** picks the tool and flow, the
targets, and the designs, with the search bounds editable per target from the
**RTL Architectures** page. Launching enqueues the jobs in the same daemon and
opens the Monitor, where each binary search reports the frequency it is currently
probing.

## Where to go next

- **Tutorial** — [Run a parallel Fmax synthesis](/tutorials/run_examples/fmax_synthesis/).
- **Reference** — [Architecture settings](/docs/reference/architecture/#frequency-settings) · [Run settings files](/docs/reference/run_settings/) · [Tool definitions](/docs/reference/tools/#steps-of-an-fmax-search)
- **Related features** — [Automated RTL synthesis](/docs/features/rtl_synthesis/) · [Results exploration](/docs/features/explorer/)
