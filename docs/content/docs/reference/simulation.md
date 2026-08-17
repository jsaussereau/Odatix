---
title: "Simulation Settings"
description: "Every key of simulations/<sim>/_settings.yml — what the testbench runs, how parameters reach it, progress reporting and invariant domains."
weight: 4
---

# `simulations/<sim>/_settings.yml`

A **simulation** is a directory under `sim_path` (default
`odatix_userconfig/simulations/`) holding a testbench and everything needed to
run it. The whole directory is copied into each job's work directory, next to
the RTL of the configuration under test.

{{< code lang=text filename="A simulation directory" >}}
odatix_userconfig/simulations/TB_Example_Counter_GHDL/
├── _settings.yml    # this page — optional
├── _metrics.yml     # what to extract — optional
├── Makefile         # the default entry point: "make sim"
└── tb/              # testbench sources
{{< /code >}}

`_settings.yml` is **optional**. Without it, the architecture's own settings are
used and Odatix runs `make sim` from the simulation's `Makefile`.

{{< toc >}}

## What the simulation runs

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `tasks` | list | No | Task graph run by the workflow engine. Without it, Odatix runs `make sim`, which then requires a `Makefile`. |

Task entries take exactly the same keys as a
[workflow's](/docs/reference/workflow/#task-entries): `name`, `commands`,
`dependencies`, `path`, `platforms`. Execution always starts at the task named
**`main`**.

{{< code lang=yaml filename="_settings.yml" >}}
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

### Placeholders available in commands

| Placeholder | Value |
|-------------|-------|
| `${simulation}` | Name of this simulation. |
| `${architecture}` | Design under test. |
| `${configuration}` | Configuration under test. |
| `${arch_full}` | Full name of the variant, domains included. |
| `${top_level_module}` | Top-level module of the design. |
| `${clock_signal}` | Its clock signal. |
| `${work_path}` | The simulation's work directory. |
| `${rtl_path}` | Directory holding the copied RTL. |
| `${log_path}` | Directory logs are expected in. |
| `${script_path}` | The simulation's script directory. |
| `${sim_path}` | This simulation's definition directory. |
| `${design_path}` | Source directory of the design under test. |
| `${odatix_path}` | Odatix installation directory. |
| `${<domain>}` | One placeholder per parameter domain of the design under test. |

`${rtl_dir}`, `${log_dir}` and `${odatix_dir}` are the former names of
`${rtl_path}`, `${log_path}` and `${odatix_path}`. They still work, but the new
ones match the variables of the [EDA tools](/docs/reference/tool/) and are what
the editors offer.

## Progress reporting

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `progress.file` | path | `log/progress.log` | File the run writes its progress to, relative to the run directory. |
| `progress.regex` | regex | `(.*): ([0-9]+)%(.*)` | Pattern the percentage is read from. |

{{< code lang=yaml filename="_settings.yml" >}}
progress:
  file: "log/progress.log"
  regex: "(.*): ([0-9]+)%(.*)"
{{< /code >}}

The value feeds the progress bar of the [Job Monitor](/docs/gui/monitor/).

## Architectures

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `architectures` | list | No | The architectures this simulation runs on, and what it changes for each of them. |

A testbench is written for a design, or for a handful of designs sharing an
interface. Which ones they are is the `architectures` block, and an architecture
with nothing to change is written as its bare name:

{{< code lang=yaml filename="_settings.yml" >}}
architectures:
  - Example_Cordic_sv
  - Example_Cordic_vhdl
{{< /code >}}

Listing an architecture is an **indication, not a restriction**. Running the
simulation on one it does not list works exactly as before, and only prints a
warning:

{{< code lang=text >}}
[simulation_handler.py] warning: "Example_Counter_vhdl" is not one of the architectures "TB_Example_Cordic_GHDL" runs on
{{< /code >}}

An empty list, or no key at all, means the simulation lists nothing: the run
warns about no architecture, and the GUI offers none until you add one.

An architecture that needs something done differently holds it under its name:

| Key | Type | Description |
|-----|------|-------------|
| `architectures.<architecture>.param_domains` | mapping | How the configuration values are substituted for this architecture (see below). |
| `architectures.<architecture>.metrics_file` | path | Metrics file to extract this architecture's runs with, instead of `_metrics.yml`. |

{{< code lang=yaml filename="_settings.yml" >}}
architectures:
  - Example_Cordic_sv:
      param_domains:
        width:
          param_target_file: "tb/tb_cordic.sv"
      metrics_file: "_metrics_sv.yml"

  - Example_Cordic_vhdl:
      param_domains:
        width:
          param_target_file: "tb/tb_cordic.vhdl"
{{< /code >}}

Names accept wildcards, `"*"` standing for every architecture, and every entry
matching the design under test applies, in the order they are written — so a
specific architecture placed **after** a wildcard refines it instead of being
shadowed by it:

{{< code lang=yaml filename="_settings.yml" >}}
architectures:
  - "*":
      param_domains:
        width:
          param_target_file: "tb/tb_cordic.sv"
  - Example_Cordic_vhdl:
      param_domains:
        width:
          param_target_file: "tb/tb_cordic.vhdl"
{{< /code >}}

### Parameters

A simulation inherits the design's parameter replacement: every [parameter
domain](/docs/configurations/) of the configuration is spliced into the design
before the testbench runs. `param_domains` adjusts that for one architecture —
the testbench often needs the same value the design got, but in a file of its
own.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `<domain>.use_parameters` | bool | No | Disable (or re-enable) the replacement for this domain. |
| `<domain>.param_target_file` | path | No | File the replacement is applied to, instead of the design's. |
| `<domain>.start_delimiter` / `.stop_delimiter` | string | No | Markers of the replaced block. |
| `<domain>.param_file` | path | No | Parameter file, relative to the simulation directory, instead of the configuration's. |

Every key is optional: what is not listed is inherited from the domain's own
settings in the architecture. Domain names match the directories under the
architecture (`width/`, `iterations/`, …).

{{< code lang=yaml filename="_settings.yml" >}}
architectures:
  - Example_Cordic_sv:
      param_domains:
        width:
          param_target_file: "tb/tb_cordic.sv"   # same value, applied to the testbench
        iterations:
          use_parameters: No                     # testbench does not care about this one
{{< /code >}}

#### Simulation-only domains

A name that matches **no** domain of the architecture declares a replacement of
the simulation's own. Use it for values only the testbench cares about — a run
length, a seed, a verbosity level. `param_file`, `start_delimiter` and
`stop_delimiter` are then required, since there is nothing to inherit them from.

{{< code lang=yaml filename="_settings.yml" >}}
architectures:
  - Example_Counter_vhdl:
      param_domains:
        sim_config:
          param_file:        "sim_params.txt"
          param_target_file: "tb/tb_counter.vhdl"
          start_delimiter:   "-- <sim>"
          stop_delimiter:    "-- </sim>"
{{< /code >}}

> [!WARNING]
> The top-level `use_parameters` / `param_target_file` / `start_delimiter` /
> `stop_delimiter` keys, and the `override_parameters` / `override_param_file` /
> `override_param_target_file` / `override_start_delimiter` /
> `override_stop_delimiter` keys, are **deprecated**. They still work and still
> run, but they only ever covered a single replacement each. Express both with
> the syntax above instead

## Invariant domains

| Key | Type | Description |
|-----|------|-------------|
| `invariant_domains` | list or mapping | Parameter domains this simulation's result does not depend on. |

Declaring one has two effects: only **one** value of that domain is simulated
instead of all of them, and the result carries no such dimension — so a
synthesis result borrowing a metric from this simulation gets it whatever the
value of that domain.

{{< code lang=yaml filename="_settings.yml" >}}
invariant_domains: [MEM]          # let Odatix pick which value runs
{{< /code >}}

{{< code lang=yaml filename="_settings.yml" >}}
invariant_domains:
  MEM: 1024I_1024D                # run this one
{{< /code >}}

See [Derived metrics](/docs/results/derived_metrics/) for why this matters when
simulation and synthesis figures are combined.

## `_metrics.yml`

Optional, and identical in format to a workflow's — see
[Metrics files](/docs/reference/metrics/). It declares what to extract from each
run; results land in `results/results_simulation.yml`. A simulation with no
`_metrics.yml` exports nothing, which is fine for a testbench that only has to
pass.

An architecture whose runs report something else names its own file with
[`metrics_file`](#architectures), which then replaces `_metrics.yml` for that
architecture alone.

{{< code lang=yaml filename="simulations/<sim>/_metrics.yml" >}}
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

## In the GUI

**RTL Architectures** → **Simulations** edits this file, with the same task
editor as workflows, and the metrics editor for `_metrics.yml`. See
[The Odatix GUI](/docs/gui/app/).

**Run Jobs** → *Simulations* shows only the architectures a simulation lists.
The cross next to an architecture takes it out of the list, and the dropdown at
the bottom of the simulation card puts one back. Both are edits like any other:
the **Save** button turns orange, and `architectures` is written to this file
when you press it.

Each card of the **Parameter Domains** section of the [Simulation
Editor](/docs/gui/app/) carries an **Architecture** field holding the
architecture the override applies to — wildcards included, and `*` for every
architecture. Two cards with the same domain name but a different architecture
are two independent overrides. Editing them never touches what else an
architecture entry holds, so a `metrics_file` set by hand survives.

## See also

- Feature: [Simulation & validation](/docs/features/simulation/) — what this file is for.
- Tutorial: [Simulate your own RTL](/tutorials/own_designs/simulations/).
- [Workflow settings](/docs/reference/workflow/) — the task graph format in full.
- [Run settings files](/docs/reference/run_settings/#simulations--testbench-to-configurations) — mapping a simulation to configurations.
