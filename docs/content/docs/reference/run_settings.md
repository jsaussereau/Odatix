---
title: "Run Settings Files"
description: "The six files that say what each odatix run command executes — plus the selector grammars they use and clean_settings.yml."
weight: 2
---

# Run settings files

Every run command reads one settings file that answers two questions: **how** to
run (parallelism, confirmation, overwrite) and **what** to run (which designs,
simulations, workflows or synthesis results).

| Command | Settings file | Selection key |
|---------|---------------|---------------|
| `odatix fmax` | `odatix_userconfig/fmax_settings.yml` | `architectures` |
| `odatix synth` | `odatix_userconfig/synth_settings.yml` | `architectures` |
| `odatix analyze` | `odatix_userconfig/analyze_settings.yml` | `architectures` + `tools` |
| `odatix sim` | `odatix_userconfig/sim_settings.yml` | `simulations` |
| `odatix workflow` | `odatix_userconfig/workflow_settings.yml` | `workflows` |
| `odatix pnr` | `odatix_userconfig/pnr_settings.yml` | `sources` |
| `odatix dse` | `odatix_userconfig/dse_settings.yml` | `campaigns` |

Each path is a default and can be changed in
[`odatix.yml`](/docs/reference/workspace/) or, for one run, with `-i/--input`.

{{< toc >}}

## Keys common to every run settings file

| Key | Type | Default | Overridden by | Description |
|-----|------|---------|---------------|-------------|
| `overwrite` | bool | **required** | `-o`, `--overwrite` | Re-run jobs that already have a result instead of skipping them. |
| `ask_continue` | bool | **required** | `-y`, `--noask` | Prompt `Continue? (Y/n)` after the pre-run checklist. |
| `nb_jobs` | int or `auto` | **required** | `-j`, `--jobs` | Maximum jobs running at once. `auto` means available CPUs − 1. |
| `exit_when_done` | bool | `No` | `-E`, `--exit` | Close the Job Monitor when the last job finishes. |
| `log_size_limit` | int | `300` | `--logsize` | Lines of log history kept per job in the monitor. |

The first three keys must be in the file, even when a command-line option
overrides them: they say what happens to results that already exist and how much
of the machine a run takes, so Odatix does not guess them. The files that
`odatix init` writes already set them (to `No`, `Yes` and `8`); when you write a
settings file yourself, keep these three lines and change only the selection.

> [!TIP]
> About 75 % of your logical cores is usually a good value for `nb_jobs`. EDA
> tools are memory hungry: a job that gets swapped out is slower than a job that
> waited its turn.

## `architectures` — designs and configurations

Used by `fmax`, `synth` and `analyze`. Each list entry is one **design variant**
to run: a design, one of its configurations, and optionally one value per
[parameter domain](/docs/configurations/param_domains/).

{{< code lang=text filename="Architecture selector grammar" >}}
<design>/<configuration> [ + <domain>/<value> ]...
{{< /code >}}

`*` stands for "every one of them" and can be used at any level; a line
containing wildcards expands to every matching combination.

{{< code lang=yaml filename="odatix_userconfig/fmax_settings.yml" >}}
architectures:
  - Example_Counter_sv/08bits                        # one configuration
  - Example_ALU_sv/*                                 # every configuration of a design
  - AsteRISC/M0000 + DMEM/1024 + Baseline/I + Mul/Off
  - AsteRISC/*     + DMEM/*    + Baseline/* + Mul/*  # the full cross-product
{{< /code >}}

A design whose parameters are swept through
[variables](/docs/configurations/virtual_param_domains/) rather than parameter
files is selected the same way, its variable acting as a domain:

{{< code lang=yaml >}}
architectures:
  - Example_Counter_chisel_cli                 # every value of every variable
  - Example_Counter_chisel_cli + width/16bits  # just one
{{< /code >}}

On the command line, `-a/--architecture` takes the same selectors and replaces
this list for one run, the file staying as it is (`odatix fmax`, `synth` and
`analyze`):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax -a "Example_Counter_sv/*" "Example_Counter_chisel_cli + width/16bits"
{{< /code >}}

## `tools` — analysis only

`analyze_settings.yml` additionally lists the eda tools to elaborate with, since
`odatix analyze` runs several at once. `-t/--tool` overrides the list.

{{< code lang=yaml filename="odatix_userconfig/analyze_settings.yml" >}}
tools:
  - vivado
  - verilator

architectures:
  - Example_Counter_sv/*
{{< /code >}}

## `expected` — analysis only

What is normal for the designs of `analyze_settings.yml`: the findings it
describes are reported apart, as *expected*, and do not count — a design whose
findings are all expected passes. Each entry is a set of conditions and a
reason; see [Expected findings](/docs/reference/analysis/#expected-findings).

{{< code lang=yaml filename="odatix_userconfig/analyze_settings.yml" >}}
expected:
  debug_bus:
    category: unused
    subject: dbg_*
    reason: "Debug bus, only connected in the lab build"
{{< /code >}}

## `fmax_synthesis` — fmax only

`fmax_settings.yml` can give the bounds of the binary search for the whole run.

| Key | Type | Default | Overridden by | Description |
|-----|------|---------|---------------|-------------|
| `override` | bool | `No` | | Use the bounds below. With `No`, they are ignored and each design point keeps the bounds of its [architecture](/docs/reference/architecture/#frequency-settings). |
| `lower_bound` | int (MHz) | empty | `--from` | Lowest frequency tried. Empty: the bound of the architecture. |
| `upper_bound` | int (MHz) | empty | `--to` | Highest frequency tried. Empty: the bound of the architecture. |

{{< code lang=yaml filename="odatix_userconfig/fmax_settings.yml" >}}
fmax_synthesis:
  override:    Yes
  lower_bound: 50
  upper_bound: 500
{{< /code >}}

## `frequencies` — fixed-frequency synthesis only

`synth_settings.yml` can give the frequencies to synthesize at, as a list, a
range, or both (their union).

| Key | Type | Default | Overridden by | Description |
|-----|------|---------|---------------|-------------|
| `override` | bool | `No` | | `Yes`: these frequencies replace those of the architectures. `No`: they are only used for an architecture that gives none. |
| `list` | list of int (MHz) | `[50, 100]` | `--at` | Frequencies to synthesize at. |
| `range` | mapping | | `--from`, `--to`, `--step` | `from`, `to` and `step`, in MHz: every frequency from `from` to `to`, `step` apart. |
| `disabled_list` | list of int (MHz) | | | A `list` switched off: kept in the file, not run. |
| `disabled_range` | mapping | | | A `range` switched off: kept in the file, not run. |

{{< code lang=yaml filename="odatix_userconfig/synth_settings.yml" >}}
frequencies:
  override: Yes
  list: [50, 100, 250]
  disabled_range:          # remembered, not run
    from: 100
    to:   500
    step: 50
{{< /code >}}

`disabled_list` and `disabled_range` are what the GUI writes when the **List**
or **Range** switch of the synthesis frequencies is off: the values are
remembered for when the switch is turned back on. The command line never runs
them.

## `simulations` — testbench to configurations

`sim_settings.yml` maps each [simulation](/docs/reference/simulation/) to
the architecture selectors it runs on. The selectors are the ones above.

{{< code lang=yaml filename="odatix_userconfig/sim_settings.yml" >}}
simulations:
  - TB_Example_Counter_GHDL:
    - Example_Counter_vhdl/04bits
    - Example_Counter_vhdl/08bits

  - TB_Example_Counter_Verilator:
    - Example_Counter_sv/*
{{< /code >}}

On the command line, `odatix sim -s/--sim` runs some of these simulations only,
and `-a/--architecture` replaces their architectures, written the same way; the
file stays as it is:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -s TB_Example_Counter_Verilator -a "Example_Counter_sv/08bits"
{{< /code >}}

## `workflows` — workflows and their parameters

`workflow_settings.yml` lists [workflows](/docs/reference/workflow/) to run. A
workflow that has parameter files takes a configuration after a `/`; domains and
variables are appended with `+`, exactly as for architectures.

{{< code lang=text filename="Workflow selector grammar" >}}
<workflow>[/<configuration>] [ + <domain>/<value> ]...
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
workflows:
  - crossplatform                    # no parameter file
  - cli_profile/default              # one configuration of it
  - cli_profile/aggressive
  - tensorflow + epochs/*            # one run per value of the "epochs" domain
  - param_domains_cli + max_speed/* + num_vehicles/* + road_length/* + signal_timing/*
{{< /code >}}

A domain the commands of a workflow use must be in the selection: one left out
reaches the command as an empty value, which the run warns about.

On the command line, `odatix workflow -W/--workflow` takes the same selectors
and replaces this list for one run, the file staying as it is:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -W "cli_profile/*" "tensorflow + epochs/10"
{{< /code >}}

## `sources` — place & route inputs

`odatix pnr` does not start from RTL: it starts from a **synthesis job that has
already run and succeeded**. `pnr_settings.yml` selects those jobs.

{{< code lang=text filename="Source selector grammar" >}}
<source_type>/<source_tool>[@<source_flow>]/<target>/<design>/<configuration>[@<frequency>MHz]
{{< /code >}}

| Field | Values |
|-------|--------|
| `<source_type>` | `fmax_synthesis` or `custom_freq_synthesis` |
| `<source_tool>` | The eda tool that ran the synthesis, optionally `@<flow>` |
| `<target>` | The device or technology it was synthesized for |
| `<design>` / `<configuration>` | As in an architecture selector |
| `@<frequency>MHz` | Fixed-frequency sources (`custom_freq_synthesis`) only: which frequency point |

`*` is accepted at every level.

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
sources:
  - custom_freq_synthesis/design_compiler/AMS_c35_1V8/Example_ALU_sv/08bits@100MHz
  - fmax_synthesis/genus/AMS_c35_1V8/Example_Counter_sv/*
  - custom_freq_synthesis/*/*/*/*      # everything that can be implemented
{{< /code >}}

The file `odatix init` writes takes every completed synthesis
(`custom_freq_synthesis/*/*/*/*` and `fmax_synthesis/*/*/*/*`). A selection
that matches no completed synthesis stops the run with the list of the sources
there are.

> [!IMPORTANT]
> A synthesis job can only be a source if its flow wrote the handoff files
> `result/netlist.v`, `result/design.sdc` and `result/design.sdf`. A flow that
> never writes them cannot be a source, whatever its status says.

The command line narrows the same selection without editing the file, with
`--from-type`, `--from-tool` and `--from-flow` (settings `from_type`,
`from_tool` and `from_flow` of a run started from Python; a source flow needs
its source tool). See
[Place & route](/docs/features/pnr/).

## `clean_settings.yml`

Read by `odatix clean`. One key, one list of glob patterns removed from the
workspace — the junk EDA tools leave in the current directory.

| Key | Type | Description |
|-----|------|-------------|
| `remove_list` | list of globs | Files and directories `odatix clean` deletes. |

{{< code lang=yaml filename="odatix_userconfig/clean_settings.yml" >}}
remove_list:
  # Design Compiler
  - alib-*
  - command.log
  - default.svf
  - "*.syn"
  # Vivado
  - .Xil
  - "*.jou"
  - vivado*.log
  # Odatix
  - odatix_error.log
{{< /code >}}

> [!WARNING]
> `remove_list` entries are deleted without confirmation. Keep the patterns
> narrow, and never point one at a source directory.

## In the GUI

**Run jobs** builds these files for you: choosing a job type, a tool, targets and
designs and pressing **Run** writes the corresponding settings file before
enqueueing the jobs. Everything you set there is the same YAML documented here.
See [The Odatix GUI](/docs/gui/app/).

## See also

- [Commands reference](/docs/commands/#common-runtime-options) — the CLI option matching each key.
- [Parameter domains](/docs/configurations/param_domains/) — where the `+` syntax comes from.
- [Workspace settings](/docs/reference/workspace/) — moving these files elsewhere.
