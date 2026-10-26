---
title: "Add targets"
date: 2026-05-15
# author: "Jonathan Saussereau"
weight: 3
description: "Add targets (FPGA circuit or ASIC technology) that Odatix can use to run your flows on."
categories: ["Tutorial", "EDA Tools"]
tags: ["tools", "targets", "yaml"]
featured_image: "/images/tutorials/add-tools.svg"
---

{{< toc >}}

A **target** is what a tool implements a design for: an FPGA part for Vivado or
Quartus, a technology for Design Compiler, Genus or LibreLane. This tutorial adds
a Zynq-7000 part to the targets of Vivado, chooses which targets a run uses,
and then sets up a target that needs a setup script of its own.

Everything can be done three ways, which read and write the same file:

| | |
|---|---|
| **Graphical interface** | `odatix-gui`, on the targets page of a tool. |
| **YAML files** | One file per tool, `odatix_userconfig/targets/target_<tool>.yml`. |
| **Python API** | `ws.targets["<tool>"]`, for a workspace built by a script. |

## What a target file is

Each tool has one target file in `odatix_userconfig/targets/`. It lists the
targets of the tool, and the settings of the tool that belong to your machine
(where it is installed) rather than to its definition:

{{< code lang=yaml filename="odatix_userconfig/targets/target_vivado.yml" >}}
constraint_file: constraints.xdc

tool_install_path: "" # Vivado should be in your $PATH

force_single_thread: No

script_copy_enable: No
script_copy_source: "/dev/null"

targets:
  # - xc7s25-csga225-1
  - xc7a100t-csg324-1
  # - xcku035-fbva676-2-e
{{< /code >}}

**Every run implements every enabled target**: one `odatix fmax` compares a
design across all the parts listed. A commented-out line is a disabled target:
kept in the file, not run.

The target name is handed to the tool's scripts as is (`target.txt` and
`settings.yml` in the job directory, `$target` in a command), and the scripts
make of it what the tool needs. For Vivado, it is the part name given to
`synth_design -part`: any part your Vivado installation supports is a valid
target, listed or not.

## Prerequisites

- A workspace with the examples, created by `odatix init --examples`.
- Vivado on your `PATH` for step 4. The steps before it run nothing.

## Step 1 — Add a target

Add the Zynq-7000 part `xc7z020-clg400-1` to Vivado.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Start `odatix-gui`, open **Run** → **Fixed-frequency synthesis**, and pick the
**Vivado** card. On the run page, **Choose targets** opens the targets of
Vivado, one card per target.

Click **Add new target**, rename the new card to `xc7z020-clg400-1`, and click
**Save all**.

{{% /tab %}}
{{% tab name="YAML files" %}}

Add one line to the `targets` list:

{{< code lang=yaml filename="odatix_userconfig/targets/target_vivado.yml" >}}
targets:
  # - xc7s25-csga225-1
  - xc7a100t-csg324-1
  - xc7z020-clg400-1
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="targets.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()
targets = ws.targets["vivado"]
targets.add("xc7z020-clg400-1")
print(targets.enabled_names())
{{< /code >}}

`add()` writes the file back at once, its comments and its other keys
untouched. The new target goes at the end of the list, after the commented-out
ones (the YAML tab lets you put it where you want). It refuses a target the file already has, disabled or not: use
`enable()` for those.

{{% /tab %}}
{{< /tabs >}}

## Step 2 — Choose the targets a run uses

A run implements every enabled target. Disable the ones you do not want to run
for now, or pick some for a single run.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

On the targets page, turn off the **Enable** switch of `xc7a100t-csg324-1` and
click **Save all**. The card is dimmed, and the line is commented out in the
file.

{{% /tab %}}
{{% tab name="YAML files" %}}

Comment the line out:

{{< code lang=yaml filename="odatix_userconfig/targets/target_vivado.yml" >}}
targets:
  # - xc7a100t-csg324-1
  - xc7z020-clg400-1
{{< /code >}}

For a single run, `--target` picks among the enabled targets, without changing
the file:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado --target xc7z020-clg400-1
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="targets.py" >}}
targets.disable("xc7a100t-csg324-1")     # commented out in the file
print(targets.enabled_names())            # ['xc7z020-clg400-1']
{{< /code >}}

For a single run, the `targets` option of a run picks among the enabled ones:
`Run(ws, "custom_freq_synthesis", tool="vivado", targets=["xc7z020-clg400-1"])`.

{{% /tab %}}
{{< /tabs >}}

## Step 3 — Set up the tool

The other keys of the file say how to run the tool on your machine. They are
all optional:

| Key | Default | When to set it |
|-----|---------|----------------|
| `tool_install_path` | empty: on your `PATH` | The tool is installed elsewhere. Commands get it as `$tool_install_path`; the built-in Quartus, LibreLane and OpenLane use it, the other built-in tools expect to be on your `PATH`. |
| `force_single_thread` | `No` | Many jobs run at once and the tool takes every core. |
| `constraint_file` | `constraints.sdc` | The tool scripts expect another name for the clock constraint of a job. |

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

The **Tool settings** panel, above the target cards, edits these three keys.
**Save all** writes them.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="odatix_userconfig/targets/target_quartus.yml" >}}
tool_install_path: "/opt/altera/altera_pro/26.1.1"
force_single_thread: Yes
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="targets.py" >}}
ws.targets["quartus"].update(tool_install_path="/opt/altera/altera_pro/26.1.1",
                             force_single_thread=True)
print(ws.targets["quartus"].tool_install_path)
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

Before a fixed-frequency synthesis, Odatix writes the constraint file in the job
directory as an SDC clock constraint; the scripts of the built-in tools rewrite
it in their own format. A tool of your own can read it, or ignore it.

## Step 4 — Run on the new target

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Back on the run page of Vivado, select `Example_Counter_verilog` and, in its **Preview**, untick every configuration
but `08bits`. Turn on **Override frequencies**, type `100` in **Target
frequencies (MHz)**, click **Run jobs**, then **Start** in the popup once the
check is done.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado -a Example_Counter_verilog/08bits --at 100 --until synthesis
{{< /code >}}

`--until synthesis` stops after synthesis, which is enough to check a target:
the place & route comes on the next run, without synthesizing again.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="run.py" >}}
from odatix.run import Run

run = Run(ws, "custom_freq_synthesis", tool="vivado",
          architectures=["Example_Counter_verilog/08bits"], frequencies=[100], until="synthesis")
run.start()
for job in run.wait():
    print(job["name"], job["status"])
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

The results carry the target as a dimension (`target: xc7z020-clg400-1`): in
Odatix Explorer, a filter on **Target** compares the same design on two parts.
A part name Vivado does not know fails the job at its first step: its log,
under `log/` in the job directory, says so.

## Targets that need a setup script

An ASIC technology is more than a name: the tool needs its libraries. The tools
for ASIC that Odatix ships read a setup script per technology, which the target
file copies into the scripts of each job:

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

On the targets page of Design Compiler, the more button of a target card unfolds
its **Script copy** settings: turn on **Enable script copy**, and give the
script in `script_copy_source`. **Save all** writes them under
`target_settings`.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="odatix_userconfig/targets/target_design_compiler.yml" >}}
targets:
  - AMS_c35_1V8
  - my_tech

target_settings:
  AMS_c35_1V8:
    script_copy_enable: Yes
    script_copy_source: $eda_tools_path/design_compiler/technology/AMS_c35_1V8/synopsys_dc_setup.tcl
  my_tech:
    script_copy_enable: Yes
    script_copy_source: techno/my_tech/synopsys_dc_setup.tcl
{{< /code >}}

A relative `script_copy_source` is relative to the workspace;
`$eda_tools_path` is the directory of the built-in tools.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="targets.py" >}}
ws.targets["design_compiler"].add(
    "my_tech", script_copy_enable=True, script_copy_source="techno/my_tech/synopsys_dc_setup.tcl",
)
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

The setup script lands in the `scripts/` directory of every job on that target.
What it must define depends on the tool: the built-in Design Compiler, Genus
and Innovus ship examples in their `technology/` directory. A tool of your own
reads `$target` or `target.txt` and does what it needs.

## Common mistakes

| Symptom | Cause |
|---------|-------|
| `Target file ... does not exist` | The tool has no target file yet: add a target (step 1). |
| A target never runs | Its line is commented out, or `--target` names another one. |
| `--target` is refused | It only picks among the **enabled** targets of the file. |
| The tool check fails | The tool is not on your `PATH`. Add it there, or set `tool_install_path` to its installation directory. |
| `Target 'x' already exists` from the API | The file has it, maybe disabled: `enable("x")`. |

## Next steps

- [Add unsupported tools](/tutorials/own_flows/add_tools/) — a tool, its
  metrics and its first target.
- [Add flows](/tutorials/own_flows/add_flows/) — compare two ways of running a
  tool on the same target.

## Related resources

- **Reference** — [Target files](/docs/reference/targets/): every key, the
  variables usable in paths, where the file is looked up.
- **Reference** — [Tool definitions](/docs/reference/tools/): `target_file`, to
  share one target file between two tools.
