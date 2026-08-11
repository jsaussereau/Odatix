---
title: "Add unsupported tools"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 2
description: "Wrap any synthesis script or EDA tool into Odatix in a few files, and get parallel runs, targets, metrics and charts for free."
categories: ["Tutorial", "EDA Tools"]
tags: ["tools", "custom", "yaml"]
featured_image: "/images/tutorials/add-tools.svg"
---

{{< toc >}}

Odatix has no list of supported tools in its code: a tool is a **directory
containing a `tool.yml`**. So adding the one you use — an open source flow, a
tool under NDA, a shell script somebody wrote in 2014 — is adding a directory.
Nothing to install, nothing to patch, nothing to recompile.

In this tutorial you wrap a synthesis script into a tool called `mysynth`, run it
on a design space, and see its numbers in Odatix Explorer.

> [!TIP]
> Odatix ships a tool named **`dummy`** that simulates a full synthesis, place &
> route and bitstream flow without any licence. It is the best possible starting
> point: on the **EDA Tools** page, **Duplicate** it into your workspace and
> replace its scripts one by one with the real ones. Everything below then
> already works while you do it.

## Step 1 — Create the tool

{{< tabs >}}
{{% tab name="With the GUI" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

Open **EDA Tools** → **Create New Tool**, and name it `mysynth`. Odatix creates
`odatix_userconfig/tools/mysynth/` with a minimal `tool.yml`, and the tool is
already discovered — it just does not run anything yet.
{{% /tab %}}
{{% tab name="By hand" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/tools/mysynth/tcl
{{< /code >}}
{{% /tab %}}
{{< /tabs >}}

## Step 2 — Say what it runs

{{< code lang=yaml filename="odatix_userconfig/tools/mysynth/tool.yml" >}}
label: "My Synth"
description: "In-house synthesis script"

process_group: True
default_metrics_file: "$tool_path/metrics.yml"
default_flow: standard

unix:
  # How Odatix checks the tool is installed. Must fail when it is not.
  tool_test_command: yosys -V

  # Run by "odatix synth": synthesize at one given frequency.
  custom_freq_synthesis_command:
    - cd $work_path;
    - bash $script_path/synth.sh

flows:
  standard:
    label: "Standard"
    description: "Yosys synthesis at a fixed frequency"
{{< /code >}}

Three things matter here:

- **`$script_path`, `$work_path`, `$log_path`** are expanded by Odatix. Commands
  do not start in a guaranteed directory, so either `cd $work_path;` first or use
  absolute paths;
- **`tool_test_command`** is mandatory. It is what tells you *"tool not
  installed"* instead of letting hundreds of jobs fail one by one;
- you declare only `custom_freq_synthesis_command`, so `mysynth` shows up for
  `odatix synth` and nowhere else. Add `fmax_synthesis_command` when your script
  can search for a maximum frequency, `analysis_command` for lint, `pnr_command`
  for place & route.

In the GUI, this same page is **Settings** on the tool's card: *Tool Metadata*,
*Behaviour*, then a **Flows** section where each job type is *Not supported*,
*Command* or *Steps*.

## Step 3 — Write the script

Everything in `tcl/` is copied into each job's `scripts/` directory, whatever the
language. Your script reads what the job is from `settings.yml`, at the root of
the job directory:

{{< code lang=bash filename="odatix_userconfig/tools/mysynth/tcl/synth.sh" >}}
#!/usr/bin/env bash
set -e

# What Odatix prepared for this job
TOP=$(grep '^top_level_module:' settings.yml | cut -d' ' -f2)
FREQ=$(grep '^target_frequency:' settings.yml | cut -d' ' -f2)

mkdir -p report result log

echo "In progress: 10%" > log/synth_status.log

yosys -p "read_verilog rtl/*.v; synth -top $TOP; \
          tee -o report/area.rep stat; \
          write_verilog result/netlist.v" \
      | tee log/synthesis.log

echo "Synthesized at $FREQ MHz"
echo "Done: 100%" > log/synth_status.log
{{< /code >}}

What Odatix put in the job directory for you:

| Path | Content |
|------|---------|
| `rtl/` | The design sources, **with this configuration's parameters already substituted**. |
| `settings.yml` | Top level, clock, target, frequency, bounds, library… as YAML. |
| `scripts/settings.tcl` | The same, as Tcl `set` statements, if your tool speaks Tcl. |
| `report/`, `result/`, `log/` | Yours to fill. |

Writing `log/synth_status.log` is optional — it is what draws the progress bar in
the Job Monitor. Success is decided by your command's exit code, not by parsing
your log.

## Step 4 — Say what to measure

{{< code lang=yaml filename="odatix_userconfig/tools/mysynth/metrics.yml" >}}
custom_freq_synthesis_metrics:
  Frequency:
    type: regex
    settings:
      file: log/synthesis.log
      pattern: "Synthesized at ([0-9]+) MHz"
      group_id: 1
    format: "%.0f"
    unit: MHz

metrics:
  Cells:
    type: regex
    error_if_missing: No
    settings:
      file: report/area.rep
      pattern: "Number of cells:\\s+([0-9]+)"
      group_id: 1
    format: "%.0f"
{{< /code >}}

Paths are relative to the job directory. Beyond `regex`, metrics can be read from
CSV, YAML, JSON and XML reports, or computed from other metrics — see
[Metrics](/docs/results/metrics/). The **Metrics** button on the tool's card edits this
same file graphically.

## Step 5 — Declare your targets

Targets are not in `tool.yml`; each tool has its own target file, named after it:

{{< code lang=yaml filename="odatix_userconfig/targets/target_mysynth.yml" >}}
constraint_file: "constraints.txt"
tool_install_path: "/usr/local"

targets:
  - sky130
  - gf180
{{< /code >}}

The target name reaches your script through `settings.yml`; mapping it to a PDK
or a library is your script's job.

## Step 6 — Run it

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool mysynth
{{< /code >}}

That is all. `mysynth` is now a first-class tool: it appears in `--tool`, on the
GUI's **Select an EDA Tool** page, in the daemon sessions and the Job Monitor,
and it runs every configuration of your design space in parallel with the rest.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results
$ odatix-explorer
{{< /code >}}

## Going further

**Make it resumable.** Split the job into steps and each one becomes stoppable
and restartable — screen a design space with synthesis only, then carry the good
part through place & route:

{{< code lang=yaml filename="tool.yml" >}}
unix:
  custom_freq_synthesis_steps:
    - name: synthesis
      default: true
      command: cd $work_path; bash $script_path/step_synthesis.sh
    - name: pnr
      command: cd $work_path; bash $script_path/step_pnr.sh
{{< /code >}}

Each step is its own process, so it must hand its state over through a file. Then
`odatix synth -t mysynth --until pnr` runs both, and a later run only does what is
left.

**Chain it with another tool.** Write `result/netlist.v`, `result/design.sdc` and
`result/design.sdf` at the end of a synthesis and any tool declaring `pnr_steps`
can place & route your netlist with `odatix pnr --from-tool mysynth`.

**Colorize its output.** A `format` section maps your log's markers to levels and
colors in the Job Monitor.

## Next steps

- The full reference: [Add non supported tools](/docs/tools/add_tools/)
- [Run your own flows and scripts](/docs/tools/add_flows/) — several ways to run the same tool
- Not a synthesis at all? [Workflows](/docs/features/workflows/) run arbitrary task graphs
