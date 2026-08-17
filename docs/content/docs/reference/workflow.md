---
title: "Workflow Settings"
description: "Every key of workflows/<name>/_settings.yml — sources, task graph, dependencies, platforms, progress tracking and inline variables."
weight: 5
---

# `workflows/<name>/_settings.yml`

A **workflow** is a directory under `workflow_path` (default
`odatix_userconfig/workflows/`) describing a pipeline of tasks and what to
measure from it. Odatix copies its sources into one work directory per
configuration, runs the tasks there, and extracts the metrics.

{{< code lang=text filename="A workflow directory" >}}
odatix_userconfig/workflows/cli_profile/
├── _settings.yml    # this page
├── _metrics.yml     # what to extract
├── default.txt      # a configuration (parameter file)
└── aggressive.txt   # another one
{{< /code >}}

{{< toc >}}

## `sources` — what gets copied

**Required.** The directory copied into every run directory.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `sources.path` | path | Yes | Directory copied into each run directory. |
| `sources.whitelist` | list of globs | No | Copy only what matches. |
| `sources.blacklist` | list of globs | No | Exclude what matches. |

{{< code lang=yaml filename="_settings.yml" >}}
sources:
  path: examples/workflow_param_domains_cli
  blacklist:
    - "*.log"
{{< /code >}}

## `tasks` — the pipeline

**Required.** A list of tasks forming a dependency graph, resolved like a
makefile: execution starts at the task named **`main`**, its dependencies run
first, and independent branches run concurrently.

### Task entries

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | string | Yes | Task identifier, referenced by other tasks' `dependencies`. |
| `commands` | list of strings | No | Shell commands, run in order. |
| `dependencies` | list of strings | No | Task names that must complete first. |
| `path` | path | No | Working directory of this task — absolute, or relative to the run directory. |
| `platforms` | string or list | No | Platforms this implementation applies to (`linux`, `darwin`, `win32`). |

{{< code lang=yaml filename="_settings.yml" >}}
tasks:
  - name: main
    dependencies:
      - generate_config
    commands:
      - echo 'step 1/2 done'
      - "echo 'Progress: 60' > progress.txt"
      - echo 'step 2/2 done'
      - "echo 'Progress: 100' > progress.txt"

  - name: generate_config
    commands:
      - echo 'Generating config...'
      - touch config.txt
{{< /code >}}

### Several implementations of the same task

Entries may **share a `name`** with different `platforms`. The one matching the
current platform is selected; if none matches, the entry declaring no
`platforms` at all is used as the default. If nothing can be selected, the
workflow stops with an error.

{{< code lang=yaml filename="_settings.yml" >}}
tasks:
  - name: build
    platforms: [linux, darwin]
    commands:
      - ./configure && make

  - name: build
    platforms: win32
    commands:
      - build.bat

  - name: build                    # fallback for anything else
    commands:
      - make
{{< /code >}}

> [!NOTE]
> `platform` (singular) is the legacy spelling of `platforms`. Declaring both on
> the same entry is an error.

### Placeholders in commands and paths

`${name}` placeholders in `commands` and `path` are substituted from the
resolved configuration:

| Placeholder | Value |
|-------------|-------|
| `${<workflow_name>}` | The workflow's own configuration value (its parameter file's content). |
| `${<domain>}` | One per [parameter domain](/docs/configurations/param_domains/) of the workflow. |
| `${<variable>}` | One per inline [variable](/docs/configurations/virtual_param_domains/). |
| `${workflow}` | Name of this workflow. |
| `${configuration}` | Configuration being run. |
| `${workflow_full}` | Full name of the variant, domains included. |
| `${work_path}` | The workflow's work directory. |
| `${log_path}` | Directory logs are expected in. |
| `${workflow_path}` | This workflow's definition directory. |
| `${source_path}` | Directory the workflow's sources are copied from. |
| `${odatix_path}` | Odatix installation directory. |

A parameter domain or a variable named like a built-in placeholder wins over it,
so declaring one never silently changes what a command already did.

A placeholder that resolves to nothing is left unchanged, so environment
variables still reach the shell. Environment tokens (`$env(VAR)`, `$VAR`,
`${VAR}`) are expanded in paths.

## `progress` — feeding the monitor

| Key | Type | Description |
|-----|------|-------------|
| `progress.file` | path | File the tasks write progress to, relative to the run directory. |
| `progress.regex` | regex | Pattern the percentage is read from. |

{{< code lang=yaml filename="_settings.yml" >}}
progress:
  file: progress.txt
  regex: "Progress:\\s*([0-9]+)"
{{< /code >}}

Whenever a task writes `Progress: 60` to that file, the
[Job Monitor](/docs/gui/monitor/) shows 60 %.

## Parameters

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `use_parameters` | bool | `true` | Replace a delimited block of a source file with the configuration's parameter file. |
| `param_target_file` | path | — | File the replacement is applied to. Required when `use_parameters` is true. |
| `start_delimiter` / `stop_delimiter` | string | — | Markers of the replaced block. Required when `use_parameters` is true. |

{{< code lang=yaml filename="_settings.yml" >}}
use_parameters:    Yes
param_target_file: "main.py"
start_delimiter:   'AWESOME_STRING = "'
stop_delimiter:    '"'
{{< /code >}}

Set `use_parameters: No` when parameters are passed on the command line instead
— then use variables, below.

## `variables` — inline variables

Declares variables swept without any parameter file, substituted into commands
as `${name}`. Odatix runs the **cross-product** of every variable.

| Key | Type | Description |
|-----|------|-------------|
| `variables` | mapping | One entry per variable, at the root of the file. |
| `variables.<name>.type` | string | Generation method: `list`, `range`, `power_of_two`, `multiples`, `function`, set operations. |
| `variables.<name>.settings` | mapping | Type-specific settings (`list`, `from`/`to`, `op`…). |
| `variables.<name>.unit` | string | Optional unit appended to the generated value's name. |
| `variables.<name>.group` | string | Optional pairing group: variables sharing it are zipped instead of crossed. |

> [!NOTE]
> `variables` used to be declared inside `generate_configurations_settings`. It is still
> read there when the root key is absent, and moved to the root the next time Odatix
> writes the file.

{{< code lang=yaml filename="_settings.yml" >}}
use_parameters: No

tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed} --num_vehicles ${num_vehicles}

variables:
  max_speed:
    type: list
    unit: kmh
    settings:
      list: [35, 45, 55]
  num_vehicles:
    type: list
    settings:
      list: [100, 300]
{{< /code >}}

Every variable type and option is documented on
[Variables](/docs/configurations/variables/); the
mechanism itself on
[Virtual parameter domains](/docs/configurations/virtual_param_domains/).

## `_metrics.yml`

What the workflow exports, in the format documented on
[Metrics files](/docs/reference/metrics/). Results land in
`results/results_workflow.yml` and are re-exportable with `odatix res_workflow`.

{{< code lang=yaml filename="workflows/<name>/_metrics.yml" >}}
metrics:
  best_val_accuracy:
    type: json
    settings:
      file: workflow_results.json
      key: best_val_accuracy
    format: "%.6f"
{{< /code >}}

A run producing a *curve* rather than one number expands into one record per
point with `multiple: true` and a `metadata` section — see
[Base metrics](/docs/results/metrics/#expanding-one-run-into-several-records).

## In the GUI

**Workflows** (`/workflows`) edits this file: tasks and their dependencies as
cards, variables in the shared variable editor, and the metrics editor for
`_metrics.yml`. See [The Odatix GUI](/docs/gui/app/).

## See also

- Feature: [Custom workflows](/docs/features/workflows/) — what this file is for.
- Tutorial: [Run your own workflow](/tutorials/own_designs/workflows/).
- [Simulation settings](/docs/reference/simulation/) — the same task engine, applied to testbenches.
- [Run settings files](/docs/reference/run_settings/#workflows--workflows-and-their-parameters) — selecting workflows for a run.
