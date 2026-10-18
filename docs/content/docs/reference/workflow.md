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
makefile: execution starts at the task named **`main`**, and its dependencies
run first.

### Task entries

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | string | Yes | Task identifier, referenced by other tasks' `dependencies`. |
| `commands` | list of strings | No | Shell commands, run in order. |
| `on_failure_commands` | list of strings | No | Fallback commands, run in order when one of `commands` fails. The task then succeeds if they do. |
| `dependencies` | list of strings | No | Task names that must complete first. |
| `path` | path | No | Directory the commands of this task run from — absolute, or relative to the run directory. It applies to this task only. |
| `phony` | bool | No | `Yes` (default): the task always runs. `No`: the task stands for the file it is named after, and is skipped when that file exists — see [below](#a-task-that-produces-a-file). |
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

### A fallback when a task fails

`on_failure_commands` is a second way of doing what a task does, tried when the
first one fails: the task runs as `(commands) || (on_failure_commands)`. A
dependency task that installs something is the typical use, as in the
[TensorFlow example](/docs/examples/workflows/tensorflow/):

{{< code lang=yaml filename="_settings.yml" >}}
tasks:
  - name: env
    commands:
      - python3 -m venv env
      - env/bin/python3 -m pip install tensorflow
    on_failure_commands:          # tensorflow not available for that python
      - python3.10 -m venv --clear env
      - env/bin/python3 -m pip install tensorflow
{{< /code >}}

### A task that produces a file

By default a task is *phony*: it runs every time its job runs. With
`phony: No`, a task is named after a file it produces instead, and is skipped
when that file already exists (relative to the task's `path`, or absolute), as
long as none of its dependencies has to run. A dependency that builds an
environment once for every job is the typical use, as in the
[TensorFlow example](/docs/examples/workflows/tensorflow/):

{{< code lang=yaml filename="_settings.yml" >}}
tasks:
  - name: main
    dependencies:
      - /tmp/odatix_tensorflow_example_env/ready
    commands:
      - /tmp/odatix_tensorflow_example_env/bin/python3 train.py

  - name: /tmp/odatix_tensorflow_example_env/ready
    phony: No
    commands:
      - python3 setup_env.py python3      # builds the environment, then writes "ready"
{{< /code >}}

Whether the file exists is decided when the jobs are prepared, before any of
them runs. The jobs of a run that all need the file therefore all run the task:
when they run at the same time, the task has to take a lock and check again
(`setup_env.py` does it with `fcntl.flock`). The next runs skip it.

### Placeholders in commands and paths

`${name}` placeholders in `commands`, `on_failure_commands` and `path` are substituted from the
resolved configuration:

| Placeholder | Value |
|-------------|-------|
| `${<workflow_name>}` | The content of the selected configuration's file (`cli_profile/aggressive` → `aggressive.txt`), whether `use_parameters` is on or off. |
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

A placeholder Odatix does not know is left unchanged, so environment variables
still reach the shell. A `${name}` that is not an environment variable either
gets a warning when the run is checked: the shell would expand it, most of the
time to nothing — a parameter domain left out of the selection, or a workflow
selected without a configuration, does that. Environment tokens (`$env(VAR)`,
`$VAR`, `${VAR}`) are expanded in paths.

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
[Job Monitor](/docs/sessions/gui_monitor/) shows 60 %. Each workflow is read
with its own regex, including when one run mixes several workflows.

## Jobs that already ran

A job writes `workflow_done` into its run directory once its task `main`
succeeded. The next run skips the jobs that have it (**Existing results**),
unless it overwrites them (`overwrite: Yes` in `workflow_settings.yml`, or
`-o/--overwrite`). A job without it — failed or stopped — runs again from an
empty run directory, or from the one it left with `-r/--resume`.

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
`results/results_workflow.yml` and are re-exportable with `odatix results workflow`.

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
- Tutorial: [Create your own workflow](/tutorials/own_designs/workflows/).
- [Simulation settings](/docs/reference/simulation/) — the same task engine, applied to testbenches.
- [Run settings files](/docs/reference/run_settings/#workflows--workflows-and-their-parameters) — selecting workflows for a run.
