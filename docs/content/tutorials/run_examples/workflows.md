---
title: "Run a Workflow"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 6
description: "Run the built-in task-pipeline examples, sweep them across parameters, extract custom metrics and chart the result."
categories: ["Tutorial", "Workflows"]
tags: ["workflows", "examples"]
featured_image: "/images/features/workflows.svg"
---

{{< toc >}}

A **workflow** runs an arbitrary pipeline of commands once per configuration, in
parallel, with progress tracking and metric extraction — the same machinery
Odatix uses for synthesis, applied to anything that runs from a shell.

| Workflow | What it demonstrates |
|----------|----------------------|
| `basic` | Tasks, dependencies, progress tracking, parameter replacement in a source file. |
| `cli_profile` | Passing a configuration's value into a command instead of a file. |
| `crossplatform` | One task declared per platform. |
| `param_domains_cli` | Sweeping parameters passed on the command line. |
| `metric_sweep` | One run producing several data points. |
| `tensorflow` | A real experiment: training a model per configuration. |


## Prerequisites

For this tutorial, you need **at least one** of the following tools installed and available in your `PATH`:
- [Verilator](https://www.veripool.org/verilator/)
- [GHDL](https://github.com/ghdl/ghdl)

Make sure you have [Odatix installed](/install/) and available in your `PATH`. For example, if you installed Odatix in a virtual environment, activate it first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source odatix_venv/bin/activate
{{< /code >}}

## Steps

### Step 1 — Initialize an example workspace

Create a new directory for the demonstration and move into it. For example:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/odatix_examples && cd ~/odatix_examples
{{< /code >}}

Create a new Odatix workspace and copy the built-in examples into it:

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix init --examples

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝

<font color="#555753">[settings.py]</font> <font color="#8AE234">Your directory can now be used by Odatix!</font>
<font color="#555753">[settings.py]</font> Run <b>odatix -h</b> to get a list of useful commands
{{< /code >}}

### Step 2 — Look at what a workflow is

Open `odatix_userconfig/workflows/basic/_settings.yml`. Three things matter:

{{< code lang=yaml filename="workflows/basic/_settings.yml" >}}
sources:
  path: examples/workflow_simple      # copied into every run directory

progress:
  file: progress.txt                  # what the Job Monitor reads
  regex: ".*Progress: ([0-9]+)*"

tasks:
  - name: main                        # execution always starts here
    dependencies:
      - generate_config               # ... which runs first
    commands:
      - echo 'step 1/2 done'
      - "echo 'Progress: 60' > progress.txt"

  - name: generate_config
    commands:
      - echo 'Generating config...'
      - touch config.txt
{{< /code >}}

And next to it, `_metrics.yml` — what to keep from the files those tasks wrote:

{{< code lang=yaml filename="workflows/basic/_metrics.yml" >}}
metrics:
  letters:
    type: regex
    settings:
      file: output.txt
      pattern: "letters: ([0-9]+)"
      group_id: 1
    format: "%.0f"
{{< /code >}}

`default.txt` and `hehe.txt` in the same directory are its two
**configurations**: each is spliced into the source file named by
`param_target_file`.

### Step 3 — Choose what to run

Open `odatix_userconfig/workflow_settings.yml` and keep it small for a first run:

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
nb_jobs: 4

workflows:
  - basic/default
  - basic/hehe
{{< /code >}}

### Step 4 — Run it

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow
{{< /code >}}

Odatix copies the sources into one work directory per configuration under
`work/workflows/`, runs the task graph there, and attaches the
[Job Monitor](/docs/gui/monitor/) — where the progress bar moves as the tasks
write to `progress.txt`, and each job's log is one keystroke away.

To free your terminal instead, run detached and re-attach later:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -d -S experiments
$ odatix ls                       # list sessions
$ odatix monitor -S experiments   # re-attach
{{< /code >}}

### Step 5 — Sweep a parameter space

The interesting part is running the *same* workflow across many values. Replace
the selection with one that sweeps command-line parameters:

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
workflows:
  - param_domains_cli_variables + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*
{{< /code >}}

That workflow declares its variables inline, with no folders and no parameter
files:

{{< code lang=yaml filename="workflows/param_domains_cli_variables/_settings.yml" >}}
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

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -j auto
{{< /code >}}

Odatix expands the **cross-product** of every variable, substitutes each `${...}`
into the command, and runs one job per combination.

### Step 6 — Chart the results

Metrics were exported as the jobs finished. Open the dashboard:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Each variable is a dimension you can plot against, so a line chart of a metric
versus `max_speed`, grouped by `num_vehicles`, takes a few clicks. If you edit
`_metrics.yml` afterwards, re-export without re-running anything:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix res_workflow
{{< /code >}}

### Step 7 — The same thing from the GUI

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

**Workflows** shows the same definitions as editable cards — tasks,
dependencies, variables, metrics — and **Run Jobs** → **Workflow** selects what
to launch. It writes the same YAML files, so you can move between the two freely.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Progress bar stays at 0 % | `progress.file` or `progress.regex` does not match what the tasks write. |
| A `${var}` reaches the shell literally | The name matches no variable, domain or workflow value — check the spelling in `generate_configurations_settings`. |
| No results in Explorer | The workflow has no `_metrics.yml`, or the file the metric reads was never written. |
| Jobs are skipped | They already have results; add `-o/--overwrite`, or `-r/--resume` to reuse the work directories. |

## Related resources

- **Your own workflow** — [Create your own workflow](/tutorials/own_designs/workflows/).
- **Feature** — [Custom workflows](/docs/features/workflows/).
- **Reference** — [Workflow settings](/docs/reference/workflow/) · [Run settings files](/docs/reference/run_settings/) · [Metrics files](/docs/reference/metrics/)
- **Guides** — [Define a workflow](/docs/reference/workflow/) · [Virtual parameter domains](/docs/configurations/virtual_param_domains/)
