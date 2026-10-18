---
title: "Simulation & Validation"
description: "Validate and benchmark every configuration of your design with the simulator of your choice — from Verilator and GHDL to virtually anything."
layout: "doc-features"
badge: "Validation"
badgeColor: "#16a34a"
cta: true
weight: 6
features:
  - title: "No script to write"
    description: "Templates for GHDL, Verilator, Questa, xsim and Icarus compile and run your testbench."
  - title: "Any simulator"
    description: "Odatix drives the simulator through commands you provide, so any tool fits."
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

Odatix does not embed a simulator, but it knows how to drive the common ones:
its **simulation templates** compile, elaborate and run a design and its
testbench with **GHDL, Verilator, Questa/ModelSim, the Vivado simulator or
Icarus**. You write the testbench, attach it to the design, and name the
simulator:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -s verilator -a "MyCounter/*"
{{< /code >}}

Odatix orders the sources itself, packages first, refuses a language the
simulator does not compile before anything starts, and reports for each
configuration whether it passed, its errors and warnings, how long each stage
took and how many cycles per second were simulated. See [Simulate your own
RTL](/tutorials/own_designs/simulations/).

For anything else, a simulation is described by the commands needed to build
and run your testbench, so **cocotb**, another simulator or a Makefile of your
own all fit.

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
  length — the simulation's own replacements change those without touching the
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
file feeds the [Job Monitor](/docs/sessions/gui_monitor/)'s progress bar.

Two mechanisms are specific to simulations:

- **Replacements of its own**, per architecture (`param_domains` under
  `architectures`): the value of a configuration written into the testbench
  instead of the design, or values only the testbench cares about (a run
  length, a seed), kept separate from the design's configurations.
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

`sim_settings.yml` maps each simulation to the configurations it runs on:

{{< code lang=yaml filename="odatix_userconfig/sim_settings.yml" >}}
nb_jobs: 8

simulations:
  - TB_Example_Counter_GHDL:
    - Example_Counter_vhdl/04bits
    - Example_Counter_vhdl/08bits
    - Example_Counter_vhdl/16bits
{{< /code >}}

The simulation's own `_settings.yml` says what to run, if `make sim` is not
enough. Here, a simulation of your own, `TB_My_Counter_GHDL`, holding the
testbench of the example in its `tb/` directory:

{{< code lang=yaml filename="simulations/TB_My_Counter_GHDL/_settings.yml" >}}
tasks:
  - name: analyze
    commands:
      - ghdl -a ${vhdl_files} ${tb_files}

  - name: main
    dependencies:
      - analyze
    commands:
      - ghdl -e tb_counter
      - ghdl -r tb_counter --stop-time=500ns --vcd=${log_path}/counter.vcd

# The width of each configuration goes into the generic of the testbench,
# which passes it on to the counter
architectures:
  - Example_Counter_vhdl:
      param_domains:
        __main__:
          param_target_file: "tb/tb_counter.vhdl"
{{< /code >}}

`${vhdl_files}` and `${tb_files}` are the sources of the design and of the
testbench, in compilation order, and `${log_path}` a directory Odatix creates
before the first task runs.

And its `_metrics.yml` says what to keep from it, here from the `results.yml`
file the testbench writes:

{{< code lang=yaml filename="simulations/TB_My_Counter_GHDL/_metrics.yml" >}}
metrics:
  cycles:
    type: yaml
    settings:
      file: results.yml
      key: cycles
    format: "%.0f"
    unit: cycles

  status:
    type: yaml
    settings:
      file: results.yml
      key: status
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -s TB_My_Counter_GHDL -a "Example_Counter_vhdl/*"
$ odatix sim -d -S nightly     # detached, named session
$ odatix results sim           # re-export after editing _metrics.yml
{{< /code >}}

A simulation that succeeded is not run again: `-o` runs it again. One that
failed, or was stopped, runs again at the next `odatix sim`; `-r` runs it in its
existing work directory instead of a new one.

Results land in `results/results_simulation.yml`, tagged with both the simulation
and the configuration it ran on. A simulation that failed is exported too, so
that its verdict replaces the one of an earlier run. A simulation without a
`_metrics.yml` exports nothing — perfectly fine for a testbench that only has
to pass.

Every key is on the
[simulation settings reference](/docs/reference/simulation/); every option on the
[commands reference](/docs/commands/).

### From the GUI

In `odatix-gui`, **Configure** → **RTL simulations** opens the **Simulations**
section at the bottom of the Architectures page: a card per simulation opens
the **Simulation editor**, which edits the template it starts from, its
testbench, its tasks and dependencies as cards, the architectures it runs on
and what it changes for each, and opens the metrics editor for `_metrics.yml`.
**Configure** → **Tools** → *Simulators* says which simulators are installed,
and **New simulation** starts one from a template. **Run** → **Simulations**
then picks which simulation runs on which configurations, and launches into
the same daemon.

## Where to go next

- **Tutorials** — [Run the example simulations](/tutorials/run_examples/simulations/) · [Simulate your own RTL](/tutorials/own_designs/simulations/)
- **Reference** — [Simulation settings](/docs/reference/simulation/) · [Run settings files](/docs/reference/run_settings/#simulations--testbench-to-configurations) · [Metrics files](/docs/reference/metrics/)
- **Reference** — [`simulations/<sim>/_settings.yml`](/docs/reference/simulation/) · [Derived metrics](/docs/results/derived_metrics/)
- **Next feature** — [Custom workflows](/docs/features/workflows/), for pipelines a single testbench cannot express.
