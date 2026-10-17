---
title: "Commands Reference"
description: "Every odatix and odatix-explorer command, with its options and examples."
weight: 100
---

# Commands Reference

Odatix provides two command-line tools:

- **`odatix`** — initialize workspaces, generate configurations, run jobs, monitor sessions and export results.
- **`odatix-explorer`** — visualize results in a web UI.

{{< toc >}}

## Getting help

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix -h
$ odatix <command> -h
$ odatix-explorer -h
{{< /code >}}

## Global options

| Option | Description |
|--------|-------------|
| `-h`, `--help` | List the commands, by group (Run, Results, Daemon, Utilities). `odatix <command> -h` gives the options of one. |
| `-v`, `--version` | Print the Odatix version and exit. |

The messages of a command are prefixed with the command (`[odatix fmax]`). An
unexpected error prints a one-line message and writes the full trace to
`odatix_error.log`, to attach to a bug report.

## Command map

| Category | Commands | Purpose |
|----------|----------|---------|
| Initialization | `odatix init` | Initialize workspace files. |
| Configuration | `odatix config` | Read and change the configuration of the workspace. |
| Generation | `odatix generate`, `odatix replace` | Generate parameter files and replace delimited sections. |
| Execution | `odatix fmax`, `odatix synth`, `odatix pnr`, `odatix analyze`, `odatix sim`, `odatix workflow` | Enqueue and run synthesis, place & route, RTL analysis, simulation and workflow jobs. |
| Daemon sessions | `odatix ls`, `odatix monitor`, `odatix stop` | Inspect, attach and stop daemon sessions. |
| Export | `odatix results [all\|synth\|sim\|workflow\|analysis\|derived]` | Export synthesis, simulation, workflow and analysis results, and apply derived metrics. |
| Maintenance | `odatix clean`, `odatix migrate` | Remove generated files from a clean profile, and rewrite settings files written in a former format. |
| Exploration | `odatix-explorer`, `odatix-gui` | Interactive visualization of results, and the full graphical interface. |

## Common runtime options

`fmax`, `synth`, `pnr`, `sim` and `workflow` share most runtime flags:

| Option | Meaning |
|--------|---------|
| `-o`, `--overwrite` | Overwrite existing results. |
| `-y`, `--noask` | Do not ask for confirmation before launch. |
| `-t`, `--tool` | The eda tool (`fmax`, `synth`, `pnr`, `analyze`). Default: `default_tool` of `odatix.yml`, else the only tool the workspace has a target file for. |
| `--target` | Run on this target only, out of those the target file of the tool enables. Repeatable. No short form: `-T` is `--trust`. (`fmax`, `synth`, `pnr`). |
| `-d`, `--detach` | Enqueue jobs and return immediately (no monitor). |
| `-S`, `--session` | Session name/selector for enqueue/attach/stop. |
| `-j`, `--jobs` | Maximum parallel jobs (`auto` = available CPUs − 1). |
| `-E`, `--exit` | Exit the monitor when all jobs complete. |
| `--logsize` | Per-job log history size in the monitor. |
| `-k`, `--keep` | Keep timestamped run directories (`fmax`, `synth`, `sim` and `workflow`). |
| `-D`, `--debug` | Verbose debug diagnostics. |
| `-c`, `--config` | Alternate workspace settings file (default `odatix.yml`). |
| `-Q`, `--nobanner` | Disable the Odatix banner. |

## Job-specific options

| Command | Additional options |
|---------|--------------------|
| `odatix fmax` | `-t/--tool`, `-f/--flow`, `--target`, `-u/--until`, `--rerun-from`, `--from`, `--to`, `--continue-on-error`, `-T/--trust`, `-e/--noexport` |
| `odatix synth` | `-t/--tool`, `-f/--flow`, `--target`, `-u/--until`, `--rerun-from`, `--from`, `--to`, `--step`, `--at` (repeatable), `-T/--trust`, `-e/--noexport` |
| `odatix analyze` | `-t/--tool` (repeatable), `-f/--flow` (repeatable), `-T/--trust`, `-e/--noexport` |
| `odatix pnr` | `-t/--tool`, `-f/--flow`, `--target`, `-u/--until`, `--rerun-from`, `--from-type`, `--from-tool`, `--from-flow`, `-i/--input`, `-w/--work`, `-T/--trust`, `-e/--noexport` |
| `odatix sim` | `-a/--archpath`, `-s/--simpath`, `-w/--work` |
| `odatix workflow` | `-p/--workflowpath`, `-w/--work`, `-r/--resume`, `-e/--noexport` |

### Former spellings

These still work for one more version, with a warning saying what to type
instead:

| Former | Now |
|--------|-----|
| `odatix --init` | `odatix init` |
| `odatix freq` | `odatix synth` |
| `odatix res_synth`, `res_simulation`, `res_workflow`, `res_analysis`, `res_derived` | `odatix results synth`, `sim`, `workflow`, `analysis`, `derived` |
| `odatix init -e` | `odatix init --examples` |
| `odatix generate -w` | `odatix generate -p/--workflowpath`, as `odatix workflow` |
| `odatix clean -f/--force` | `odatix clean -y/--yes`, as the other commands that skip a question |
| `odatix dse -T` | `odatix dse --target` |

Gone without a transition: `odatix synthesis` and `odatix explore` (use
`synth` and `dse`), the `--force` spelling of `--continue-on-error`, `clean -v`
(now `-V/--verbose`: `-v` is the version), and `odatix res_benchmark` with the
`-u/--use_benchmark`, `-B/--benchmark_file` and `-S/--sim_file` options of the
exports: a benchmark score is a [simulation metric](/docs/results/metrics/) now.

> [!WARNING]
> `odatix dse -c/--config` names the workspace settings file, as everywhere
> else. The exploration settings file is given with `-i/--input`; one given to
> `-c` is refused with that hint.

## Selecting a flow

A **flow** is a way of running an eda tool: a different script, different
options, sometimes a different binary. Vivado ships a timing oriented flow and a
power oriented one (automatic clock gating); Design Compiler ships a `dc_shell`
flow and a `dcnxt_shell` one.

The flows of a tool are declared in the `flows` section of its `tool.yml`. When
`-f/--flow` is not given, the tool's default flow is used (its `default_flow`
key).

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool vivado                     # default flow ("standard")
$ odatix synth --tool vivado --flow power_opt    # clock gating + power optimization
$ odatix fmax --tool design_compiler --flow dcnxt      # dcnxt_shell instead of dc_shell
{{< /code >}}

Flows of the same tool are alternatives meant to be compared, so each one runs in
its own work directory (`work/custom_freq_synthesis/vivado@power_opt/...`), while
all of them are exported into that tool's single results file.

`odatix analyze` runs several tools at once, so its `--flow` accepts several
values: a bare flow name applies to every selected tool, while `tool:flow` only
applies to that tool.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze --tool vivado verilator --flow vivado:implementation
{{< /code >}}

The flow a job ran with is recorded in the results file (`flow` meta key), so
Odatix Explorer can compare the same design run through different flows.

What a tool runs can also be split into ordered **steps** (synthesis, place &
route, bitstream...). Being stepped belongs to the tool, not to one dedicated
flow: every flow of Vivado can be stopped wherever, for a custom frequency
synthesis as well as for an fmax search. `-u/--until` stops a run at a given
step, and a later run resumes at the first step left to do rather than redoing
everything — see
[Splitting a job into steps](../reference/tools/#steps).

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado --until pnr                    # implement, no bitstream
$ odatix synth -t vivado                                # only runs the bitstream step
$ odatix synth -t vivado -f power_opt --until pnr       # same, on the power flow
$ odatix synth -t vivado --rerun-from pnr               # redo place & route onwards
$ odatix fmax -t vivado --until synthesis              # fmax from synthesis timing only
{{< /code >}}

In the GUI, everything is on the **Select an EDA Tool** page, laid out inside
each tool's card: its flows as buttons, and, for a flow split into steps, its
steps as "run up to here" buttons. Every one of them leads straight to the job
settings, so a run stays one click away whatever the tool offers.

## Usage by command

### Initialization

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix init                  # asks before writing, and whether to add the examples
$ odatix init -y               # asks nothing (what a script, or no terminal, gets)
$ odatix init -y --examples    # same, with the examples
{{< /code >}}

The `odatix.yml` it writes sets `default_tool: vivado`, the tool the run
commands use when `-t/--tool` names none.

### Configuration

`odatix config` reads and writes the configuration files of the workspace: the
same files documented in the [reference](/docs/reference/), through the same API
the graphical interface uses (see [Configuration
API](/docs/reference/python_api/) for the whole surface and its Python form).

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix config show                      # what the workspace holds
$ odatix config arch list
$ odatix config arch set MyCPU clock_signal=clk fmax_synthesis.lower_bound=50
$ odatix config target enable vivado xc7a100t-csg324-1
$ odatix config job show fmax_synthesis
{{< /code >}}

| Option | Description |
|--------|-------------|
| `-C`, `--directory` | Workspace directory (default: the current one). |

### Generation and replacement

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix generate
$ odatix generate -a odatix_userconfig/architectures
$ odatix generate -p odatix_userconfig/workflows

$ odatix replace -s "// <start>" -S "// </end>" -i input.v -r params.txt -o output.v
{{< /code >}}

### Synthesis and simulation

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax                              # default_tool of odatix.yml
$ odatix fmax --tool vivado
$ odatix fmax --tool vivado --target xc7a100t-csg324-1
$ odatix fmax --tool design_compiler --from 100 --to 900

$ odatix synth --tool openlane --at 50 --at 100 --at 150
$ odatix synth --tool vivado --from 100 --to 500 --step 50

$ odatix sim
{{< /code >}}

### Place & route

Place & route a netlist another tool synthesized — see [Place & route](/docs/features/pnr/).

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix pnr --tool innovus --from-tool design_compiler
$ odatix pnr --tool icc2 --from-type fmax_synthesis
$ odatix pnr --tool innovus --until route
{{< /code >}}

### RTL analysis

Elaborate every configuration with one or several tools and report its status — see [RTL analysis](/docs/features/analysis/).

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze
$ odatix analyze --tool vivado verilator genus
$ odatix analyze --tool vivado verilator --flow vivado:implementation
{{< /code >}}

### Workflows

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow
$ odatix workflow -d -S experiments
$ odatix workflow -r   # resume existing workflow directories
{{< /code >}}

### Daemon commands

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ls
$ odatix ls -S night

$ odatix monitor
$ odatix monitor -S nightly

$ odatix stop
$ odatix stop -S nightly
$ odatix stop --all
{{< /code >}}

### Results export

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results                          # everything: synth, sim and workflow, then derived
$ odatix results -t vivado -r results     # the same, synthesis results of one tool only

$ odatix results synth                    # synthesis and place & route
$ odatix results sim
$ odatix results workflow
$ odatix results analysis
$ odatix results derived                  # post-processing: apply derived metrics
{{< /code >}}

Without a type, `odatix results` exports every kind of result that was run (a
kind whose work directory does not exist is skipped), then applies the derived
metrics, which read what the others wrote. The options of a type come after it:
`odatix results sim -o sim.yml`.

### Cleanup

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix clean
$ odatix clean -y                # also remove the paths that look dangerous
$ odatix clean -V                # say what is removed
$ odatix clean -i odatix_userconfig/clean.yml
{{< /code >}}

### Migration

Odatix still reads the settings files written in a former format, and points at `odatix migrate` when it meets one. The command rewrites them in the current format, keeping their comments and layout, and keeps each former version next to it as `<file>.bak`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix migrate -n              # only say what would change
$ odatix migrate
$ odatix migrate --no-backup     # do not keep the .bak files
{{< /code >}}

It rewrites `generate_configurations` and `generate_configurations_settings` as `configurations` and `variables`, `fmax_lower_bound` and `fmax_upper_bound` as `fmax_synthesis` blocks, `disabled_targets` as commented-out entries of `targets`, and moves metrics written at the top level of a `_metrics.yml` file under `metrics`. Every job keeps running exactly as before. Former bounds set in some rules of `overrides` while other rules set `fmax_synthesis` are left alone, because which one wins depends on the job: the command reports them and exits with a non-zero status. The workspace settings page of the GUI offers the same migration.

### Explorer

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
$ odatix-explorer --network
$ odatix-explorer --port 8052 --input results
$ odatix-explorer --nobrowser --theme odatix_dark
{{< /code >}}

See [Odatix Explorer](/docs/gui/explorer/) for the full option list.

### Graphical interface

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
$ odatix-gui --network --port 8060
{{< /code >}}

See [The Odatix GUI](/docs/gui/app/) for what each page does.

## See also

- [The Odatix GUI](/docs/gui/app/) — the graphical equivalent of these commands
- [Daemon sessions & the Job Monitor](/docs/gui/monitor/)
- [Configuration reference](/docs/reference/)
- [Results & export](/docs/results/)
