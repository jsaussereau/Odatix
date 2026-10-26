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

The examples run Python scripts: `python3` must be in your `PATH`. No EDA tool
is needed. The `tensorflow` example also installs TensorFlow, which takes a
while and needs a Python version TensorFlow supports.

Make sure you have [Odatix installed](/install/) and available in your `PATH`. For example, if you installed Odatix in a virtual environment, activate it first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source odatix_venv/bin/activate
{{< /code >}}

## Steps

### Step 1 — Initialize an example workspace

Create a new directory for the demonstration and move into it. For example:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p ~/odatix_examples && cd ~/odatix_examples
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

<font color="#555753">[odatix init]</font> <font color="#34E2E2">note: This command will create all the configuration files needed by Odatix in the current directory.</font>
<font color="#555753">[odatix init]</font> Would you like to continue? (Y/n) y
<font color="#555753">[odatix init]</font> <font color="#8AE234">Your directory can now be used by Odatix!</font>
<font color="#555753">[odatix init]</font> Try a first run (with your tool in place of vivado): <b>odatix synth --tool vivado -a "Example_Counter_verilog/*" --at 50</b>
<font color="#555753">[odatix init]</font> Run <b>odatix -h</b> to get a list of useful commands
<font color="#555753">[odatix init]</font> New to Odatix? Follow https://odatix.readthedocs.io/en/latest/docs/getting-started/
{{< /code >}}

### Step 2 — Look at what a workflow is

Open `odatix_userconfig/workflows/basic/_settings.yml`. Three things matter:

{{< code lang=yaml filename="workflows/basic/_settings.yml" >}}
sources:
  path: examples/workflow_simple      # copied into every run directory

progress:
  file: progress.txt                  # what the Job Monitor reads
  regex: ".*Progress: ([0-9]+)*"

use_parameters: Yes
param_target_file: "main.py"          # where a configuration is written
start_delimiter: 'AWESOME_STRING = "'
stop_delimiter: '"'

tasks:
  - name: main                        # execution always starts here
    dependencies:
      - generate_config               # ... which runs first
    commands:
      - echo 'step 1/3 done'
      - "echo 'Progress: 60' > progress.txt"
      - python3 main.py               # writes output.txt

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
**configurations**: each is written into `main.py`, the file named by
`param_target_file`, between the two delimiters. `main.py` then writes the
string and its length to `output.txt`, where `_metrics.yml` reads them.

### Step 3 — Choose what to run

Open `odatix_userconfig/workflow_settings.yml`. Keep the settings at the top
of the file as `odatix init` wrote them (each of them is required), and only
make the `workflows` list small for a first run:

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
overwrite:        No
ask_continue:     Yes
exit_when_done:   No
log_size_limit:   300
nb_jobs:          4

workflows:
  - basic/default
  - basic/hehe
{{< /code >}}

The command line can also name the workflows to run, without touching the
file: `odatix workflow -W "basic/*"`.

### Step 4 — Run it

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow
{{< /code >}}

Odatix copies the sources into one work directory per configuration under
`work/workflows/`, runs the task graph there, and attaches the
[Job Monitor](/docs/sessions/terminal_monitor/) — where the progress bar moves as the tasks
write to `progress.txt`, and each job's log is one keystroke away.

To free your terminal instead, run detached and re-attach later:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -d -S experiments
$ odatix ps                       # list sessions
$ odatix monitor -S experiments   # re-attach
{{< /code >}}

Run `odatix workflow` again and nothing runs: a job whose workflow ran to its
end is skipped, as **Existing results**. `-o/--overwrite` runs it again.

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
      - python3 simulate_traffic.py --max_speed ${max_speed} --num_vehicles ${num_vehicles} --signal_timing ${signal_timing} --road_length ${road_length}

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
  signal_timing:
    type: list
    unit: s
    settings:
      list: [15, 45]
  road_length:
    type: list
    unit: km
    settings:
      list: [1, 5]
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -j auto
{{< /code >}}

Odatix expands the **cross-product** of every variable (3 × 2 × 2 × 2 = 24
jobs), substitutes each `${...}` into the command, and runs one job per
combination. The `unit` of a variable ends the name of its values:
`max_speed/35kmh`.

### Step 6 — Chart the results

Metrics were exported as the jobs finished. Open the dashboard:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Each variable is a dimension you can plot against, so a line chart of a metric
versus `max_speed`, grouped by `num_vehicles`, takes a few clicks. If you edit
`_metrics.yml` afterwards, re-export without re-running anything:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results workflow
{{< /code >}}

### Step 7 — The same thing from the GUI

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

**Workflows** shows the same definitions as editable cards — tasks,
dependencies, variables, metrics — and **Run jobs** → **Workflow** selects what
to launch. **Save all** writes the same YAML files (**Start** alone does not
write `workflow_settings.yml`), so you can move between the two freely.

### Step 8 — When there are too many configurations to run them all

The knobs of a workflow are arguments on a command line, so nothing stops five
of them from describing a hundred thousand runs. `image_codec`, the codec
example, already describes 3150 of them — which is why
`workflow_settings.yml` does not select it.

A [design space exploration](/docs/reference/dse/#exploring-a-workflow) searches
those instead of running them: it evaluates a batch, looks at what came out and
chooses the next batch from there.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix dse -p image_codec_rate_quality
{{< /code >}}

It runs sixty encoders out of the 3150 and comes back with the rate/quality
curve none of them is beaten on. The campaign that says so is
`odatix_userconfig/dse_campaigns/image_codec_rate_quality.yml`, and the only
thing that makes it a workflow campaign rather than a synthesis one is
`run: workflow` at the top of it.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Progress bar stays at 0 % | `progress.file` or `progress.regex` does not match what the tasks write. |
| A warning says a placeholder matches nothing | The `${var}` names no variable, selected domain or configuration, and the shell will expand it, usually to nothing. Check the spelling in `variables`, or add the domain to the selection (`+ signal_timing/*`). |
| No results in Explorer | The workflow has no `_metrics.yml`, or the file the metric reads was never written. |
| Jobs are skipped | Their workflow already ran to its end; add `-o/--overwrite` to run them again. |

## Related resources

- **Your own workflow** — [Create your own workflow](/tutorials/own_designs/workflows/).
- **Feature** — [Custom workflows](/docs/features/workflows/).
- **Reference** — [Workflow settings](/docs/reference/workflow/) · [Run settings files](/docs/reference/run_settings/) · [Metrics files](/docs/reference/metrics/)
- **Guides** — [Define a workflow](/docs/reference/workflow/) · [Virtual parameter domains](/docs/configurations/virtual_param_domains/)
- **Too many configurations** — [Exploring a workflow](/docs/reference/dse/#exploring-a-workflow)
