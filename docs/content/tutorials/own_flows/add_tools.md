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

This tutorial adds to an Odatix workspace a tool Odatix does not ship:
[Yosys](https://yosyshq.net/yosys/), the open source synthesis suite. At the end,
`odatix synth -t yosys` synthesizes any architecture of the workspace at the
frequencies you ask for, in parallel, and its cell count and logic depth show up
in Odatix Explorer next to the results of the other tools.

Nothing here is specific to Yosys. The same four files wrap an in-house script,
a commercial tool Odatix has no definition for, or a Makefile.

Everything can be done three ways, which read and write the same files:

| | |
|---|---|
| **Graphical interface** | `odatix-gui`, form by form. |
| **YAML files** | One directory and three short files. What the GUI writes. |
| **Python API** | `odatix.workspace`, for a workspace built by a script. |

## What a tool is

A tool is a **directory** of `odatix_userconfig/tools/` holding a `tool.yml`.
Nothing is registered anywhere else: the directory is the tool.

{{< code lang=text filename="The tool of this tutorial" >}}
odatix_userconfig/
├── tools/
│   └── yosys/
│       ├── tool.yml          # what to run
│       ├── metrics.yml       # what to measure, and where
│       └── tcl/
│           └── yosys_synth.py  # copied into every job directory
└── targets/
    └── target_yosys.yml      # what it runs on
{{< /code >}}

For each job, Odatix builds a job directory (the design sources, the scripts of
the tool, the settings of the job), runs the command of `tool.yml` in it, and
reads the metrics from what the command left behind. The command decides
whether the job succeeded: it exits `0`, or it does not.

## Prerequisites

- [Odatix installed](/install/), and a workspace with the examples:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/my_project && cd ~/my_project
$ odatix init --examples
{{< /code >}}

- Yosys on your `PATH`, and `python3`. Check it:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ yosys -V
Yosys 0.69 (git sha1 9f75ca1f9, ...)
{{< /code >}}

The design synthesized below is `Example_Counter_verilog`, one of the examples.

## Step 1 — The script

A tool runs a command. Here, a short Python script synthesizes the sources of
the job with Yosys and writes two reports. It runs from the job directory, where
Odatix has copied the design into `rtl/`:

{{< code lang=python filename="yosys_synth.py" linenos="true" >}}
#!/usr/bin/env python3
"""Synthesize the design of an Odatix job with Yosys. Run from the job directory."""
import glob
import os
import subprocess
import sys

top, log = sys.argv[1], os.path.relpath(sys.argv[2])
options = sys.argv[3:]

sources = sorted(glob.glob("rtl/**/*.v", recursive=True) + glob.glob("rtl/**/*.sv", recursive=True))
os.makedirs("report", exist_ok=True)
os.makedirs("result", exist_ok=True)

script = "; ".join([
    "read_verilog -sv " + " ".join(sources),
    "synth -top " + top + " " + " ".join(options),
    "tee -q -o report/stat.txt stat",
    "tee -q -o report/ltp.txt ltp -noff",
    "write_verilog -noattr result/netlist.v",
])
sys.exit(subprocess.call(["yosys", "-q", "-l", log, "-p", script]))
{{< /code >}}

The top level module, the log file and the synthesis options come from the
command line: the command of the tool passes them, from the variables Odatix
expands (step 2). The exit code of Yosys is the exit code of the job.

Keep this file at hand: it goes in the `tcl/` directory of the tool. Whatever
that directory holds is copied into the `scripts/` directory of every job,
whatever its language.

## Step 2 — Describe the tool

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Start the GUI from the workspace with `odatix-gui`, then open **Configure** →
**Tools** and click **Add new tool**. The **Tool Editor** opens on a new tool:

1. In the title, name it `yosys`. The name is how the tool is selected in every
   run (`-t yosys`).
2. **Tool metadata**: **Display Name** `Yosys`, **Description**
   `Open source synthesis with Yosys`. Both are shown on the tool's card.
3. **Behaviour**: leave **Default Metrics File** as it is,
   `$tool_path/metrics.yml`: the metrics of step 4 go there.
4. **Flows**: the tool has one flow to start with. Rename it from `default` to
   `standard`, then:
   - **Parameters** → **+ Add parameter**: name `synth_options`, type **List**,
     value `-flatten`.
   - **Unix / Linux** → **Tool test** → **Command**: `yosys -V`. Odatix runs it
     before a run, to check the tool is there.
   - **Unix / Linux** → **Fixed-frequency synthesis** → **Command**, one
     fragment per line:

{{< code lang=text filename="Fixed-frequency synthesis command" >}}
cd $work_path;
python3 $script_path/yosys_synth.py
$top_level_module
$log_path/synthesis.log
$synth_options
{{< /code >}}

5. Click **Save all**. The tool's directory and its `tool.yml` are created.

Back on **Tools**, the folder button of the new card opens the tool directory:
create a `tcl/` directory there and put `yosys_synth.py` in it.

{{% /tab %}}
{{% tab name="YAML files" %}}

Create the directory, with the script of step 1 in its `tcl/` directory:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/tools/yosys/tcl
$ cp yosys_synth.py odatix_userconfig/tools/yosys/tcl/
{{< /code >}}

Then write its `tool.yml`:

{{< code lang=yaml filename="odatix_userconfig/tools/yosys/tool.yml" linenos="true" >}}
label: "Yosys"
description: "Open source synthesis with Yosys"
default_metrics_file: "$tool_path/metrics.yml"
default_flow: standard

# Parameters of the default flow, given to the command as $synth_options
parameters:
  synth_options: [-flatten]

unix:
  tool_test_command: yosys -V

  custom_freq_synthesis_command:
    - cd $work_path;
    - python3 $script_path/yosys_synth.py
    - $top_level_module
    - $log_path/synthesis.log
    - $synth_options

flows:
  standard:
    label: "Standard"
    description: "synth -flatten"
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="add_yosys.py" linenos="true" >}}
import os
import shutil

from odatix.workspace import Workspace

ws = Workspace.open()

tool = ws.tools.create("yosys", label="Yosys", description="Open source synthesis with Yosys")
flow = tool.settings.default_flow
flow.name = "standard"
flow.label = "Standard"
flow.parameters = {"synth_options": ["-flatten"]}
flow.set_command("tool_test", "yosys -V")
flow.set_command("custom_freq_synthesis", [
    "cd $work_path;",
    "python3 $script_path/yosys_synth.py",
    "$top_level_module",
    "$log_path/synthesis.log",
    "$synth_options",
])
tool.save()

# The script, copied into every job directory
os.makedirs(os.path.join(tool.path, "tcl"), exist_ok=True)
shutil.copy("yosys_synth.py", os.path.join(tool.path, "tcl"))
{{< /code >}}

`create()` writes a `tool.yml` whose metrics file is `$tool_path/metrics.yml`.
The job types `set_command()` takes are `tool_test`, `fmax_synthesis`,
`custom_freq_synthesis`, `pnr` and `analysis`.

{{% /tab %}}
{{< /tabs >}}

What this says:

- **`tool_test_command`** is required: a tool without one is not available on
  that platform. It must exit non-zero when the tool is missing.
- **`custom_freq_synthesis_command`** is what `odatix synth` runs. A tool runs
  only the job types it declares: this one is not offered for an fmax search.
- **`$work_path`, `$script_path`, `$log_path`, `$top_level_module`** are
  expanded for each job. Commands run from the job directory; the
  `cd $work_path;` that starts this one keeps it right when you run it by hand.
- **`$synth_options`** is a parameter of the flow: a list is joined with spaces.
  [Add flows](/tutorials/own_flows/add_flows/) uses it to compare two ways of
  running the same tool.

## Step 3 — Give it a target

Every run implements each enabled target of the tool's target file. Yosys maps
to its own generic cells here, so one target is enough: `generic`.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Open **Run** → **Fixed-frequency synthesis**, pick the **Yosys** card, then
**Choose targets**. Click **Add new target**, rename the new card to `generic`,
and **Save all**.

The **Tool settings** panel above the cards holds the rest of the file: the
constraint file, and the install path of the tool, empty when it is on your
`PATH`. The defaults suit this tool.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="odatix_userconfig/targets/target_yosys.yml" >}}
targets:
  - generic
{{< /code >}}

That is a complete target file: its other keys are optional. See
[Target files](/docs/reference/targets/).

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="add_yosys.py" >}}
ws.targets["yosys"].add("generic")
{{< /code >}}

A new target file spells its optional settings out, with their defaults.

{{% /tab %}}
{{< /tabs >}}

The target name is written into each job directory (`target.txt`, and
`settings.yml`): mapping it to a device or a cell library is the script's job.
[Add targets](/tutorials/own_flows/add_targets/) goes further.

## Step 4 — Say what to measure

Odatix reads metrics from the files the job leaves behind, with paths relative
to the job directory. Two come from the reports of the script. The third,
`frequency.txt`, Odatix writes itself in every fixed-frequency job directory,
with the constraint file of the target file (an SDC clock constraint), before
the job runs.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

On the tool's card in **Configure** → **Tools**, click **Metrics** (or **Edit
metrics** in the Tool Editor). The metrics editor has one section per job type,
plus **Common metrics** for every job type.

- Under **Fixed-frequency synthesis metrics**, **Add new metric**: name
  `Frequency`, type **Regex**, file `frequency.txt`, pattern `([0-9.]+) MHz`,
  group `1`.
- Under **Common metrics**, **Add new metric** twice:
  - `Cells`: file `report/stat.txt`, pattern `^ +([0-9]+) +cells$`, group `1`;
  - `Logic_depth`: file `report/ltp.txt`, pattern
    `Longest topological path in \S+ \(length=([0-9]+)\)`, group `1`.

The more button of a card unfolds the unit and the display format. Click
**Save all**.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="odatix_userconfig/tools/yosys/metrics.yml" linenos="true" >}}
custom_freq_synthesis_metrics:
  Frequency:
    type: regex
    settings:
      file: frequency.txt
      pattern: "([0-9.]+) MHz"
      group_id: 1
    format: "%.0f"
    unit: MHz

metrics:
  Cells:
    type: regex
    settings:
      file: report/stat.txt
      pattern: "^ +([0-9]+) +cells$"
      group_id: 1
    format: "%.0f"
  Logic_depth:
    type: regex
    settings:
      file: report/ltp.txt
      pattern: "Longest topological path in \\S+ \\(length=([0-9]+)\\)"
      group_id: 1
    format: "%.0f"
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="add_yosys.py" >}}
metrics = tool.metrics
metrics.set("Frequency", {
    "type": "regex",
    "settings": {"file": "frequency.txt", "pattern": "([0-9.]+) MHz", "group_id": 1},
    "format": "%.0f", "unit": "MHz",
}, section_key="custom_freq_synthesis_metrics")
metrics.set("Cells", {
    "type": "regex",
    "settings": {"file": "report/stat.txt", "pattern": "^ +([0-9]+) +cells$", "group_id": 1},
    "format": "%.0f",
})
metrics.set("Logic_depth", {
    "type": "regex",
    "settings": {"file": "report/ltp.txt",
                 "pattern": "Longest topological path in \\S+ \\(length=([0-9]+)\\)", "group_id": 1},
    "format": "%.0f",
})
metrics.save()
{{< /code >}}

Keep the object `tool.metrics` returns: each access reads the file again.

{{% /tab %}}
{{< /tabs >}}

`regex` is one of several extractors (`csv`, `yaml`, `json`, `xml`, and computed
`operation`s): see [Metrics](/docs/results/metrics/).

## Step 5 — Run it

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Open **Run** → **Fixed-frequency synthesis** and pick the **Yosys** card. Then
select `Example_Counter_verilog` and, in its **Preview**, untick every configuration
but `08bits`. Turn on **Override frequencies**, type `100` in **Target
frequencies (MHz)**, click **Run jobs**, then **Start** in the popup once the
check is done. The jobs appear in the **Monitor**.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t yosys -a Example_Counter_verilog/08bits --at 100
{{< /code >}}

`-a` and `--at` replace the architectures and the frequencies of
`synth_settings.yml` for this run.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="run_yosys.py" >}}
from odatix.workspace import Workspace
from odatix.run import Run

ws = Workspace.open()
run = Run(ws, "custom_freq_synthesis", tool="yosys",
          architectures=["Example_Counter_verilog/08bits"], frequencies=[100])
print(run.check().counts())     # what would run, having touched nothing
run.start()
for job in run.wait():
    print(job["name"], job["status"])
run.session.stop()  # the session stays open otherwise ("odatix ps" lists it)
{{< /code >}}

Run it from the workspace directory.

{{% /tab %}}
{{< /tabs >}}

When a job ends, its metrics are exported to `results/results_yosys.yml`:

{{< code lang=yaml filename="results/results_yosys.yml" >}}
results:
- meta:
    type: custom_freq_synthesis
    target: generic
    architecture: Example_Counter_verilog
    configuration: 08bits
    tool: yosys
    flow: standard
    frequency: 100
  metrics:
    Frequency: 100
    Cells: 43
    Logic_depth: 13
{{< /code >}}

Start `odatix-explorer` to see them: **Yosys** is a source like any other, and
`Cells` and `Logic_depth` are metrics of its own.

## What the job directory holds

A job that went wrong is understood from its directory,
`work/custom_freq_synthesis/yosys/generic/Example_Counter_verilog/08bits/100MHz/`:

{{< code lang=text filename="A job directory" >}}
├── rtl/               # the design, its parameters replaced
├── scripts/           # the scripts of the tool (yosys_synth.py), and the common
│                      # ones Odatix copies into every job (settings.tcl, analysis.yml...)
├── log/               # synthesis.log, console.log (what the command printed)
├── report/            # stat.txt, ltp.txt
├── result/            # netlist.v
├── settings.yml       # the design: top level, clock, target frequency...
├── architecture.txt   # Example_Counter_verilog/08bits
├── target.txt         # generic
├── flow.txt           # the flow the job ran
├── param_domains.yml  # the values of its parameter domains
├── frequency.txt      # 100 MHz
└── constraints.sdc    # create_clock -period 10 [get_ports clock]
{{< /code >}}

`log/synth_status.log` ends with `Done: 100%`. The script did not write it:
Odatix does, when the command exits `0` without having written it, so that
`odatix results synth` exports the job again later. A script can also write
`In progress: <n>%` lines there, for the progress bar of the monitor.

## Common mistakes

| Symptom | Cause |
|---------|-------|
| `The selected EDA tool "yosys" is not supported on unix (tool_test_command is missing)` | `tool.yml` has no `tool_test_command` in its `unix` section. |
| `Fixed-frequency synthesis is not supported with the selected EDA tool` | The tool declares no `custom_freq_synthesis_command` (or `_steps`). |
| The tool check fails | `tool_test_command` exits non-zero: the tool is not on your `PATH`, or the target file names a wrong `tool_install_path`. `-T` skips the check. |
| The job fails at once | The script is not in the tool's `tcl/` directory, or the tool is not on the `PATH` of the session. Read `log/console.log`. |
| A metric is empty | Its file or its pattern does not match what the job wrote. Paths are relative to the job directory. |
| No results file | `default_metrics_file` names no existing file. |

## Next steps

- [Add flows](/tutorials/own_flows/add_flows/) — a second way of running this
  tool, compared with the first.
- [Add targets](/tutorials/own_flows/add_targets/) — the devices and
  technologies a tool runs on.
- An fmax search: declare `fmax_synthesis_command`. The search is the tool's
  job: Odatix's binary search is in the tcl scripts of the built-in tools.

## Related resources

- **Reference** — [Add non supported tools](/docs/tools/add_tools/): every key of
  `tool.yml`, the job directory, progress, handing a netlist to `odatix pnr`.
- **Reference** — [Tool definitions](/docs/reference/tools/) and
  [Target files](/docs/reference/targets/).
- **Reference** — [Metrics](/docs/results/metrics/).
- **Guide** — [Python API](/docs/python_api/).
