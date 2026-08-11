---
title: "Target Files"
description: "Every key of targets/target_<tool>.yml — the devices or technologies an eda tool implements for, their constraints and their setup scripts."
weight: 6
---

# `targets/target_<tool>.yml`

One file per eda tool, in `target_path` (default
`odatix_userconfig/targets/`), listing the **targets** that tool implements for:
FPGA devices for Vivado, technology nodes for Design Compiler or OpenLane.

Every run implements **every** target of the list, so a single `odatix fmax`
compares a design across several devices.

{{< code lang=text filename="Target files of a workspace" >}}
odatix_userconfig/targets/
├── target_vivado.yml
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
| `constraint_file` | filename | Yes | Constraint file copied into every job's context (`constraints.xdc`, `constraints.sdc`…). |
| `tool_install_path` | path | No | Root of the tool installation, exposed to the scripts as `$tool_install_path`. Leave empty when the tool is on your `PATH`. |
| `force_single_thread` | bool | No (default `No`) | Run the jobs of this file one at a time. Can help when many parallel jobs saturate memory or licences. |
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
| `$clock_signal` | Clock signal of the design being run. |
| `$top_level_module` | Its top level. |
| `$lib_name` | Library name used by the flow. |

## Where the file is looked up

`target_<tool>.yml` is searched in `target_path` first, then directly in
`odatix_userconfig/`. That fallback keeps workspaces created before
`target_path` defaulted to `odatix_userconfig/targets` working unchanged. See
[Workspace settings](/docs/reference/workspace/).

## In the GUI

**Run Jobs** → **Targets** lists the targets of the selected tool with a
checkbox each, and writes the selection back to this file. See
[The Odatix GUI](/docs/gui/app/).

## See also

- [Tool definitions](/docs/reference/tools/) — the `tool.yml` these targets belong to.
- [Install EDA tools](/install/eda_tools/) — which tools Odatix ships definitions for.
- Feature: [Automated RTL synthesis](/docs/features/rtl_synthesis/).
