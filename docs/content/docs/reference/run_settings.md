---
title: "Run Settings Files"
description: "The six files that say what each odatix run command executes — plus the selector grammars they use and clean.yml."
weight: 2
---

# Run settings files

Every run command reads one settings file that answers two questions: **how** to
run (parallelism, confirmation, overwrite) and **what** to run (which designs,
simulations, workflows or synthesis results).

| Command | Settings file | Selection key |
|---------|---------------|---------------|
| `odatix fmax` | `odatix_userconfig/fmax_synthesis_settings.yml` | `architectures` |
| `odatix synth` | `odatix_userconfig/custom_freq_synthesis_settings.yml` | `architectures` |
| `odatix analyze` | `odatix_userconfig/analysis_settings.yml` | `architectures` + `tools` |
| `odatix sim` | `odatix_userconfig/simulations_settings.yml` | `simulations` |
| `odatix workflow` | `odatix_userconfig/workflow_settings.yml` | `workflows` |
| `odatix pnr` | `odatix_userconfig/pnr_settings.yml` | `sources` |

Each path is a default and can be changed in
[`odatix.yml`](/docs/reference/workspace/) or, for one run, with `-i/--input`.

{{< toc >}}

## Keys common to every run settings file

| Key | Type | Default | Overridden by | Description |
|-----|------|---------|---------------|-------------|
| `overwrite` | bool | `No` | `-o`, `--overwrite` | Re-run jobs that already have a result instead of skipping them. |
| `ask_continue` | bool | `Yes` | `-y`, `--noask` | Prompt `Continue? (Y/n)` after the pre-run checklist. |
| `exit_when_done` | bool | `No` | `-E`, `--exit` | Close the Job Monitor when the last job finishes. |
| `log_size_limit` | int | `300` | `--logsize` | Lines of log history kept per job in the monitor. |
| `nb_jobs` | int or `auto` | `8` | `-j`, `--jobs` | Maximum jobs running at once. `auto` means available CPUs − 1. |

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

{{< code lang=yaml filename="odatix_userconfig/fmax_synthesis_settings.yml" >}}
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
  - Example_Counter_Chisel_CLI                 # every value of every variable
  - Example_Counter_Chisel_CLI + width/16bits  # just one
{{< /code >}}

The same selectors are accepted by `-a/--architectures` on the command line.

## `tools` — analysis only

`analysis_settings.yml` additionally lists the eda tools to elaborate with, since
`odatix analyze` runs several at once. `-t/--tool` overrides the list.

{{< code lang=yaml filename="odatix_userconfig/analysis_settings.yml" >}}
tools:
  - vivado
  - verilator

architectures:
  - Example_Counter_sv/*
{{< /code >}}

## `simulations` — testbench to configurations

`simulations_settings.yml` maps each [simulation](/docs/reference/simulation/) to
the architecture selectors it runs on. The selectors are the ones above.

{{< code lang=yaml filename="odatix_userconfig/simulations_settings.yml" >}}
simulations:
  - TB_Example_Counter_GHDL:
    - Example_Counter_vhdl/04bits
    - Example_Counter_vhdl/08bits

  - TB_Example_Counter_Verilator:
    - Example_Counter_sv/*
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
  - param_domains_cli + max_speed/* + num_vehicles/* + road_length/*
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
| `@<frequency>MHz` | Custom-frequency sources only: which frequency point |

`*` is accepted at every level.

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
sources:
  - custom_freq_synthesis/design_compiler/gf22/Example_ALU_sv/08bits@100MHz
  - fmax_synthesis/genus/gf22/Example_Counter_sv/*
  - custom_freq_synthesis/*/*/*/*      # everything that can be implemented
{{< /code >}}

> [!IMPORTANT]
> A synthesis job can only be a source if its flow wrote the handoff files
> `result/netlist.v`, `result/design.sdc` and `result/design.sdf`. A flow that
> never writes them cannot be a source, whatever its status says.

The command line narrows the same selection without editing the file, with
`--from-type`, `--from-tool` and `--from-flow`. See
[Place & route](/docs/features/pnr/).

## `clean.yml`

Read by `odatix clean`. One key, one list of glob patterns removed from the
workspace — the junk EDA tools leave in the current directory.

| Key | Type | Description |
|-----|------|-------------|
| `remove_list` | list of globs | Files and directories `odatix clean` deletes. |

{{< code lang=yaml filename="odatix_userconfig/clean.yml" >}}
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

**Run Jobs** builds these files for you: choosing a job type, a tool, targets and
designs and pressing **Run** writes the corresponding settings file before
enqueueing the jobs. Everything you set there is the same YAML documented here.
See [The Odatix GUI](/docs/gui/app/).

## See also

- [Commands reference](/docs/commands/#common-runtime-options) — the CLI option matching each key.
- [Parameter domains](/docs/configurations/param_domains/) — where the `+` syntax comes from.
- [Workspace settings](/docs/reference/workspace/) — moving these files elsewhere.
