---
title: "Simulation & Validation"
description: "Validate and benchmark every configuration of your design with the simulator of your choice — from Verilator and GHDL to virtually anything."
layout: "doc-features"
badge: "Validation"
badgeColor: "#16a34a"
cta: true
weight: 6
features:
  - title: "Any simulator"
    description: "Odatix drives the simulator through commands you provide, so any tool fits."
  - title: "Ready-made examples"
    description: "Verilator and GHDL examples are included to get you running in minutes."
  - title: "Per-configuration runs"
    description: "Simulate every configuration of your design to validate the whole design space."
  - title: "Benchmark metrics"
    description: "Capture pass/fail and benchmark numbers, then compare them in Odatix Explorer."
---

## Validate the whole design space

Synthesis tells you whether a configuration *fits* and how *fast* it goes.
Simulation tells you whether it is *correct* — and how well it *performs*. Odatix
runs simulations the way it runs synthesis: for **every configuration** of your
design, in **parallel**, with the results collected in one place.

Odatix does not embed a simulator. A simulation is described by the commands
needed to build and run your testbench, so **Verilator, GHDL, ModelSim, cocotb**
or a Makefile of your own all fit.

<!-- ![Simulation results](/images/screenshots/simulation.png "Placeholder — replace with a screenshot of benchmark results in Explorer") -->

## When you need it

- **Regression across a design space.** Your testbench passes on the 32-bit
  configuration. Does it pass on the other eleven?
- **Benchmarking.** Cycle counts, throughput, scores — captured as metrics, so
  performance becomes a chartable dimension rather than a number in a log.
- **Real runtime, not just Fmax.** Cycles from a simulation divided by Fmax from
  a synthesis is what a design actually takes. That is one
  [derived metric](/docs/results/derived_metrics/) away.
- **Guarding a sweep.** Before implementing 200 configurations, confirm they are
  functionally worth implementing.
- **Sweeping testbench parameters.** A shorter run time, a seed, a stimulus
  length — the simulation's own override pass changes those without touching the
  design's configurations.

## How it works

A simulation lives in `odatix_userconfig/simulations/<name>/`:

{{< code lang=text filename="A simulation directory" >}}
odatix_userconfig/simulations/TB_Example_Counter_GHDL/
├── _settings.yml    # what it runs and how parameters are replaced (optional)
├── _metrics.yml     # what to extract from the run (optional)
├── Makefile         # the default entry point: "make sim"
└── tb/              # testbench sources, scripts, whatever the run needs
{{< /code >}}

The whole directory is copied into the job's work directory next to the RTL of
the configuration under test, so the testbench always sees the design it was
built for. Without a `_settings.yml`, Odatix simply runs `make sim` — that is the
entire contract for a first testbench.

To drive the tools yourself instead, declare a **task graph**: the same format as
a [workflow](/docs/features/workflows/), with dependencies, per-platform variants
and placeholders for the configuration under test. Progress reported to a log
file feeds the [Job Monitor](/docs/gui/monitor/)'s progress bar.

Two mechanisms are specific to simulations:

- **A second, simulation-only replacement pass** (`override_parameters`) for
  values only the testbench cares about, kept separate from the design's
  configurations.
- **Invariant domains** — parameter domains a testbench is blind to (a memory
  configuration, a target voltage). Declaring one runs a single value instead of
  all of them, and drops that dimension from the result, so a synthesis result of
  *any* value of that domain can borrow the metric.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | The testbench is swept across every configuration, using the same domains as synthesis. |
| [RTL analysis](/docs/features/analysis/) | Complementary verdicts: analysis says the RTL is valid, simulation says it is correct. |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) | Cycles here + Fmax there = runtime, through [derived metrics](/docs/results/derived_metrics/). |
| [Workflows](/docs/features/workflows/) | For validation pipelines that go beyond one testbench — several tools, several stages, non-HDL steps. |
| [Explorer](/docs/features/explorer/) | Benchmark figures sit next to area and timing, so throughput-per-LUT is one chart. |

## Using it

### From the configuration files and the CLI

`simulations_settings.yml` maps each simulation to the configurations it runs on:

{{< code lang=yaml filename="odatix_userconfig/simulations_settings.yml" >}}
nb_jobs: 8

simulations:
  - TB_Example_Counter_GHDL:
    - Example_Counter_vhdl/04bits
    - Example_Counter_vhdl/08bits
    - Example_Counter_vhdl/16bits
{{< /code >}}

The simulation's own `_settings.yml` says what to run, if `make sim` is not
enough:

{{< code lang=yaml filename="simulations/TB_Example_Counter_GHDL/_settings.yml" >}}
tasks:
  - name: analyze
    commands:
      - ghdl -a --workdir=obj rtl/* tb/*

  - name: main
    dependencies:
      - analyze
    commands:
      - ghdl -e --workdir=obj tb_counter
      - ghdl -r --workdir=obj tb_counter --stop-time=500ns | tee log/sim.log
{{< /code >}}

And its `_metrics.yml` says what to keep from it:

{{< code lang=yaml filename="simulations/TB_Example_Counter_GHDL/_metrics.yml" >}}
metrics:
  Cycles:
    type: regex
    settings:
      file: log/sim.log
      pattern: "Total cycles: ([0-9]+)"
      group_id: 1
    format: "%.0f"
    unit: cycles
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim
$ odatix sim -d -S nightly     # detached, named session
$ odatix res_simulation        # re-export after editing _metrics.yml
{{< /code >}}

Results land in `results/results_simulation.yml`, tagged with both the simulation
and the configuration it ran on. A simulation without a `_metrics.yml` exports
nothing — perfectly fine for a testbench that only has to pass.

Every key is on the
[simulation settings reference](/docs/reference/simulation/); every option on the
[commands reference](/docs/commands/).

### From the GUI

`odatix-gui` → **RTL Architectures** → **Simulations** edits the testbench
definition: its tasks and dependencies as cards, the parameter delimiters, the
override pass, and the metrics editor for `_metrics.yml`. **Run Jobs** →
**Simulation** then picks which simulation runs on which configurations, and
launches into the same daemon.

## Where to go next

- **Tutorials** — [Run the example simulations](/tutorials/run_examples/simulations/) · [Simulate your own RTL](/tutorials/own_designs/simulations/)
- **Reference** — [Simulation settings](/docs/reference/simulation/) · [Run settings files](/docs/reference/run_settings/#simulations--testbench-to-configurations) · [Metrics files](/docs/reference/metrics/)
- **Reference** — [`simulations/<sim>/_settings.yml`](/docs/reference/simulation/) · [Derived metrics](/docs/results/derived_metrics/)
- **Next feature** — [Custom workflows](/docs/features/workflows/), for pipelines a single testbench cannot express.
