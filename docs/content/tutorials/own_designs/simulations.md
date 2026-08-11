---
title: "Simulate your own RTL architectures"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 2
description: "Connect your own testbench to an Odatix design, run it across every configuration, and export what it measures as metrics."
categories: ["Tutorial", "Simulation"]
tags: ["simulation", "own design"]
featured_image: "/images/tutorials/own-simulation.svg"
---

{{< toc >}}

This tutorial connects a testbench you already have to a design already described
in Odatix, runs it across **every configuration** of that design, and turns what
it prints into charts.

> [!NOTE]
> Start from a design that works: follow
> [Implement your own RTL](/tutorials/own_designs/synthesis/) first if you have
> not defined an architecture yet. The example uses a simulator on your `PATH`
> (Verilator, GHDL, or whatever you already run).

## Step 1 — Create the simulation directory

A simulation is a directory holding the testbench and everything needed to run
it:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/simulations/TB_MyAdder/tb
{{< /code >}}

{{< code lang=text filename="odatix_userconfig/simulations/TB_MyAdder/" >}}
_settings.yml    # what it runs (optional)
_metrics.yml     # what to keep from it (optional)
Makefile         # the default entry point
tb/              # your testbench sources
{{< /code >}}

The **whole directory is copied** into each job's work directory, next to the RTL
of the configuration under test. That is the one rule to keep in mind: your
testbench always finds the design it was built for, at a predictable place.

## Step 2 — The simplest possible setup

Without a `_settings.yml`, Odatix runs `make sim`. If your testbench already has
a Makefile, you are one target away from being done:

{{< code lang=makefile filename="simulations/TB_MyAdder/Makefile" >}}
sim:
	verilator --binary --top-module adder_tb -Irtl tb/adder_tb.sv rtl/*.sv -o sim
	./obj_dir/sim | tee log/sim.log
{{< /code >}}

Now map the simulation to the configurations it runs on:

{{< code lang=yaml filename="odatix_userconfig/simulations_settings.yml" >}}
nb_jobs: 1
ask_continue: Yes

simulations:
  - TB_MyAdder:
    - MyAdder/16bits
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim
{{< /code >}}

Watch it in the [Job Monitor](/docs/gui/monitor/). If it fails, go into the job's
work directory under `work/simulations/` — it contains exactly what ran, so you
can reproduce the failure by hand.

## Step 3 — Drive the tools yourself (optional)

When a Makefile is not the right shape, declare a **task graph** instead. Tasks
have dependencies, and execution always starts at `main`:

{{< code lang=yaml filename="simulations/TB_MyAdder/_settings.yml" >}}
tasks:
  - name: compile
    commands:
      - verilator --binary --top-module ${top_level_module}_tb -Irtl tb/*.sv rtl/*.sv -o sim

  - name: main
    dependencies:
      - compile
    commands:
      - ./obj_dir/sim | tee ${log_dir}/sim.log
{{< /code >}}

Commands can use `${architecture}`, `${configuration}`, `${top_level_module}`,
`${clock_signal}`, `${rtl_dir}`, `${log_dir}` and one placeholder per parameter
domain of the design — the full list is in the
[simulation settings reference](/docs/reference/simulation/#placeholders-available-in-commands).

## Step 4 — Make the testbench follow the configuration

The design's parameter file is spliced into the design automatically. If your
testbench has a generic or parameter that must follow it, declare the same kind
of replacement on a file of the *simulation*:

{{< code lang=yaml filename="simulations/TB_MyAdder/_settings.yml" >}}
use_parameters:    Yes
param_target_file: "tb/adder_tb.sv"
start_delimiter:   "// odatix: begin parameters"
stop_delimiter:    "// odatix: end parameters"
{{< /code >}}

For values only the testbench cares about — a shorter run time, a seed — use the
separate override pass instead, so they stay independent of the design's
configurations:

{{< code lang=yaml filename="simulations/TB_MyAdder/_settings.yml" >}}
override_parameters:        Yes
override_param_file:        "sim_params.txt"
override_param_target_file: "tb/adder_tb.sv"
override_start_delimiter:   "// <sim>"
override_stop_delimiter:    "// </sim>"
{{< /code >}}

## Step 5 — Report progress

Write a percentage to a log file and the monitor shows a real progress bar:

{{< code lang=yaml filename="simulations/TB_MyAdder/_settings.yml" >}}
progress:
  file: "log/progress.log"
  regex: "(.*): ([0-9]+)%(.*)"
{{< /code >}}

Those are the defaults, so a testbench printing `simulating: 40%` into
`log/progress.log` needs no configuration at all.

## Step 6 — Export what it measured

A testbench that only has to pass needs nothing more. To keep numbers, add a
`_metrics.yml`:

{{< code lang=yaml filename="simulations/TB_MyAdder/_metrics.yml" >}}
metrics:
  Cycles:
    type: regex
    settings:
      file: log/sim.log
      pattern: "Total cycles: ([0-9]+)"
      group_id: 1
    format: "%.0f"
    unit: cycles

  Errors:
    type: regex
    settings:
      file: log/sim.log
      pattern: "([0-9]+) mismatches"
      group_id: 1
    format: "%.0f"
    error_if_missing: false
{{< /code >}}

Results land in `results/results_simulation.yml`, tagged with the simulation and
the configuration it ran on.

## Step 7 — Run the whole design space

{{< code lang=yaml filename="odatix_userconfig/simulations_settings.yml" >}}
nb_jobs: 8

simulations:
  - TB_MyAdder:
    - MyAdder/*
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -j auto
$ odatix-explorer
{{< /code >}}

Edited a metric afterwards? Re-extract without re-simulating:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix res_simulation
{{< /code >}}

## Step 8 — Combine with synthesis

Cycle counts get much more useful next to an Fmax. Once you have run both a
simulation and a synthesis, a [derived metric](/docs/results/derived_metrics/) computes
the runtime:

{{< code lang=yaml filename="odatix_userconfig/derived_metrics.yml" >}}
derived_metrics:
  Cycles:
    from: simulation        # import the simulation's value into synthesis results
  Runtime:
    op: "Cycles / Fmax"
    unit: µs
{{< /code >}}

If your testbench is blind to one of the design's parameter domains, declare it
`invariant_domains` — Odatix then simulates a single value of it, and the result
applies to all of them:

{{< code lang=yaml filename="simulations/TB_MyAdder/_settings.yml" >}}
invariant_domains: [MEM]
{{< /code >}}

## Doing it from the GUI

`odatix-gui` → **RTL Architectures** → **Simulations** creates and edits the same
definition through forms — tasks, delimiters, override pass, metrics. **Run
Jobs** → **Simulation** maps it to configurations and launches.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| The testbench cannot find the RTL | Use `${rtl_dir}`; the copied design is not where it is in your source tree. |
| Every configuration produces the same numbers | Parameter replacement is not reaching the testbench — check `param_target_file` and the delimiters. |
| Nothing appears in Explorer | No `_metrics.yml`, or the file a metric reads was never written. |
| Jobs are skipped | They already have results; add `-o/--overwrite`. |

## Next steps

- **Feature** — [Simulation & validation](/docs/features/simulation/).
- **Reference** — [Simulation settings](/docs/reference/simulation/) · [Metrics files](/docs/reference/metrics/) · [Run settings files](/docs/reference/run_settings/#simulations--testbench-to-configurations)
- **Guides** — [Simulation reference](/docs/reference/simulation/) · [Derived metrics](/docs/results/derived_metrics/)
- **Going further** — [Create your own workflow](/tutorials/own_designs/workflows/), when one testbench command is not enough.
