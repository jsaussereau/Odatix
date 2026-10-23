---
title: "Target Files"
description: "Every key of targets/target_<tool>.yml — the devices or technologies an eda tool implements for, their constraints and their setup scripts."
weight: 6
---

# `targets/target_<tool>.yml`

One file per eda tool, in `target_path` (default
`odatix_userconfig/targets/`), listing the **targets** that tool implements for:
FPGA devices for Vivado or Quartus, technology nodes for Design Compiler or OpenLane.

Every run implements **every** target of the list, so a single `odatix fmax`
compares a design across several devices.

{{< code lang=text filename="Target files of a workspace" >}}
odatix_userconfig/targets/
├── target_vivado.yml
├── target_quartus.yml
├── target_design_compiler.yml
├── target_genus.yml
├── target_openlane.yml
├── target_innovus.yml
└── target_icc2.yml
{{< /code >}}

{{< toc >}}

## Keys

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `targets` | list of strings | Yes | The devices or technologies to implement for. Their names are the ones the tool's scripts expect. |
| `constraint_file` | filename | No (default `constraints.sdc`) | File of the job directory holding the clock constraint at the target frequency (`constraints.xdc`, `constraints.sdc`…). Odatix writes it as SDC before a fixed-frequency synthesis runs; the scripts of the built-in tools rewrite it in their own format. |
| `tool_install_path` | path | No | Where the tool is installed, for any tool (`~` is expanded). Its `bin` directory and the directory itself are put first on the `PATH` of the tool's commands, and the path is exposed to them as `$tool_install_path`. It wins over a tool of the same name found on your `PATH`. For most tools, point it to the installation directory holding `bin` (Vivado: `/opt/Xilinx/Vivado/2024.2`). Some tools expect a specific directory: **Quartus**, the directory holding `qinit.sh` (`/opt/altera/altera_pro/26.1.1`); **LibreLane**, the LibreLane git checkout (holding `shell.nix`); **OpenLane**, its installation directory. A path that does not exist stops the run. Leave empty, or leave out, when the tool is on your `PATH`. |
| `force_single_thread` | bool | No (default `No`) | Make each job of this tool run on a single thread (Vivado: `maxThreads 1`, LibreLane: `-j 1`). Jobs still run in parallel (`-j`): this helps when many parallel jobs, each taking several threads, oversubscribe the processor. |
| `script_copy_enable` | bool | No | Copy an extra script into each job's script directory. |
| `script_copy_source` | path | If enabled | The script to copy. Ignored with a note if the file does not exist. |
| `target_settings` | mapping | No | Per-target overrides, keyed by target name. |

{{< code lang=yaml filename="odatix_userconfig/targets/target_vivado.yml" >}}
constraint_file: constraints.xdc

tool_install_path: ""       # Vivado is on the PATH
force_single_thread: No

script_copy_enable: No
script_copy_source: "/dev/null"

targets:
  - xc7s25-csga225-1
  - xc7a100t-csg324-1
  - xcku035-fbva676-3-e
{{< /code >}}

## Disabling a target

A target is switched off by commenting out its line: it stays in the file, and
the GUI lists it, unchecked. Checking it in the GUI uncomments the line.

{{< code lang=yaml >}}
targets:
  - xc7a100t-csg324-1
  # - xc7k70t-fbg676-2      # disabled
{{< /code >}}

> [!NOTE]
> Former target files kept the disabled targets in a `disabled_targets` list
> instead. It is still read, and never run; `odatix migrate` turns its entries
> into commented-out lines of `targets`.

## Per-target overrides

`target_settings` overrides the script copy for one target — the usual case
being a technology setup script that differs per node.

{{< code lang=yaml filename="odatix_userconfig/targets/target_design_compiler.yml" >}}
constraint_file: constraints.sdc

script_copy_enable: Yes
script_copy_source: "techno/default_setup.tcl"

targets:
  - gf22
  - tsmc65

target_settings:
  gf22:
    script_copy_enable: Yes
    script_copy_source: "techno/gf22_setup.tcl"
  tsmc65:
    script_copy_enable: Yes
    script_copy_source: "techno/tsmc65_setup.tcl"
{{< /code >}}

## Variables usable in paths

The following tokens are substituted in copied script paths and in the commands
of a [tool definition](/docs/reference/tools/):

| Token | Value |
|-------|-------|
| `$odatix_path` | Odatix installation directory. |
| `$eda_tools_path` | Directory holding the eda tool definitions. |
| `$work_path` | The job's work directory. |
| `$tool_install_path` | The `tool_install_path` of this file. |
| `$script_path` | The job's script directory. |
| `$log_path` | The job's log directory. |
| `$rtl_path` | The job's RTL directory, holding the copied sources. |
| `$report_path` | The job's report directory. |
| `$result_path` | The job's result directory. |
| `$architecture` | Design being run, configuration included: `Counter/08bits`. |
| `$target` | Target this job runs on. |
| `$tool` | Name of this tool. |
| `$clock_signal` | Clock signal of the design being run. |
| `$top_level_module` | Its top level. |
| `$lib_name` | Library name used by the flow. |

## Where the file is looked up

`target_<tool>.yml` is searched in `target_path` first, then directly in
`odatix_userconfig/`. That fallback keeps workspaces created before
`target_path` defaulted to `odatix_userconfig/targets` working unchanged. See
[Workspace settings](/docs/reference/workspace/).

## A new target file

A target file written by Odatix — by the GUI or by the
[Python API](/docs/python_api/) for a tool that has none yet — spells its
settings out, with their defaults, so that it runs as it is:

{{< code lang=yaml filename="odatix_userconfig/targets/target_mytool.yml" >}}
constraint_file: constraints.sdc

tool_install_path: "" # empty: the tool is on your PATH

force_single_thread: No

script_copy_enable: No
script_copy_source: "/dev/null"

targets:
  - generic
{{< /code >}}

From the API, `ws.targets["mytool"]` is the target file of a tool: `add()`,
`enable()`, `disable()`, `rename()` and `remove()` change its targets, and
`update(constraint_file=..., tool_install_path=..., force_single_thread=...)`
its settings.

## In the GUI

On the run page of a synthesis or a place & route (**Run**, then a job type and
a tool), **Choose targets** opens the targets of the selected tool: one card per
target, with an **Enable** switch, and **Add new target** to add one. The
**Tool settings** panel above them edits `constraint_file`, `tool_install_path`
(with what to put there for the tools that expect a specific directory)
and `force_single_thread`. **Add new target**, **Duplicate** and **Remove**
only change the page: nothing is written before **Save all**, which writes the file. See
[The Odatix GUI](/docs/gui/app/).

## See also

- [Tool definitions](/docs/reference/tools/) — the `tool.yml` these targets belong to.
- [Install EDA tools](/install/eda_tools/) — which tools Odatix ships definitions for.
- Feature: [Automated RTL synthesis](/docs/features/rtl_synthesis/).
