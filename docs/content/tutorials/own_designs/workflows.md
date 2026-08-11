---
title: "Create your own workflow"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 3
description: "Turn a script you already have into parallel, monitored, parameter-swept jobs with exported metrics."
categories: ["Tutorial", "Workflows"]
tags: ["workflow", "own design"]
featured_image: "/images/tutorials/own-workflow.svg"
---

{{< toc >}}

This tutorial wraps a script you already have into an Odatix workflow, sweeps it
across a parameter space, and turns what it prints into charts — without
rewriting the script.

The example is a tiny Python program, but nothing here is Python specific: a
Makefile, an HLS run, a solver, a benchmark harness all fit the same shape.

> [!NOTE]
> Start with **one** configuration and `nb_jobs: 1`. Confirm the pipeline runs
> before expanding the sweep.

## The starting point

Say you have this, and you want to know how `--threads` affects the score:

{{< code lang=text filename="~/my-experiment/" >}}
run.py          # prints "score: 42" and "elapsed: 1.87"
data/           # inputs it reads
{{< /code >}}

## Step 1 — Initialize a workspace

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/my-experiment-odatix && cd ~/my-experiment-odatix
$ odatix init
$ mkdir -p odatix_userconfig/workflows/Experiment
{{< /code >}}

`odatix init` (without `--examples`) creates an empty workspace: `odatix.yml`
and the settings files, nothing else.

## Step 2 — Describe the workflow

Create `odatix_userconfig/workflows/Experiment/_settings.yml`. Three decisions:
**what to copy**, **what to run**, **how progress is reported**.

{{< code lang=yaml filename="workflows/Experiment/_settings.yml" >}}
sources:
  path: ~/my-experiment       # copied into every run directory
  blacklist:
    - "*.log"
    - "__pycache__"

use_parameters: No            # parameters go on the command line, not into a file

progress:
  file: progress.txt
  regex: "Progress: ([0-9]+)"

tasks:
  - name: main
    commands:
      - python3 run.py --threads ${threads} | tee run.log
{{< /code >}}

Two things to know:

- Everything under `sources.path` is copied into an **isolated work directory**
  per configuration, so runs never interfere with each other — and your original
  directory is never written to.
- Execution always starts at the task named **`main`**. Add more tasks and list
  them in `dependencies` when you need stages.

## Step 3 — Declare the parameter to sweep

`${threads}` has to come from somewhere. Declare it inline — no folders, no
parameter files:

{{< code lang=yaml filename="workflows/Experiment/_settings.yml (continued)" >}}
generate_configurations_settings:
  variables:
    threads:
      type: list
      settings:
        list: [1, 2, 4, 8]
{{< /code >}}

Odatix will run the workflow once per value. With a second variable, it runs the
**cross-product** of the two. Values that follow a rule can be generated instead
of listed — ranges, powers of two, computed functions: see
[Configuration generation](/docs/configurations/config_generation/).

## Step 4 — Say what to measure

Create `odatix_userconfig/workflows/Experiment/_metrics.yml`. Each entry names a
file, how to read it, and how to format the value:

{{< code lang=yaml filename="workflows/Experiment/_metrics.yml" >}}
metrics:
  score:
    type: regex
    settings:
      file: run.log
      pattern: "score: ([0-9.]+)"
      group_id: 1
    format: "%.0f"

  elapsed:
    type: regex
    settings:
      file: run.log
      pattern: "elapsed: ([0-9.]+)"
      group_id: 1
    format: "%.2f"
    unit: s
{{< /code >}}

Other extraction types read a CSV column, a JSON or YAML key, or an XML element —
see [Base metrics](/docs/metrics/base/).

## Step 5 — Run one configuration

Select a single value first:

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
nb_jobs: 1
ask_continue: Yes

workflows:
  - Experiment + threads/1
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow
{{< /code >}}

Watch the [Job Monitor](/docs/gui/monitor/). If something goes wrong, the job's
work directory under `work/workflows/` contains exactly what ran — go in, run the
command by hand, and fix the setting.

## Step 6 — Report progress (optional but worth it)

The monitor's progress bar is fed by whatever your script writes to the file
named in `progress`. One line is enough:

{{< code lang=python filename="run.py" >}}
def report(percent):
    with open("progress.txt", "w") as f:
        f.write("Progress: {}\n".format(percent))
{{< /code >}}

Without it, jobs still run — you just see "running" instead of a percentage.

## Step 7 — Sweep the whole space

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
nb_jobs: 4

workflows:
  - Experiment + threads/*
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -j auto
$ odatix-explorer
{{< /code >}}

`threads` is now a dimension in Explorer: plot `score` against it, or correlate
`score` with `elapsed` in a scatter chart. Edited a metric? Re-extract without
re-running:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix res_workflow
{{< /code >}}

## Variations you are likely to need

| You want to… | Do this |
|--------------|---------|
| Patch a value **inside** a source file instead of a command line | Set `use_parameters: Yes` with `param_target_file`, `start_delimiter`, `stop_delimiter`, and one `.txt` per configuration. |
| Run several stages | Add tasks and list them in `dependencies`; independent branches run in parallel. |
| Support Linux and Windows | Declare the same task name twice with different `platforms`. |
| Produce a curve, not one number | Use `multiple: true` and a `metadata` section — see [Base metrics](/docs/metrics/base/#expanding-one-run-into-several-records). |
| Set up an environment once | Make it a task the others depend on, like the shipped `tensorflow` example. |

## Doing it from the GUI

`odatix-gui` → **Workflows** creates and edits the same definition through
forms — tasks and dependencies as cards, variables in the variable editor,
metrics in the metrics editor. **Run Jobs** → **Workflow** launches it. The files
it writes are the ones above.

## Next steps

- **Feature** — [Custom workflows](/docs/features/workflows/).
- **Reference** — [Workflow settings](/docs/reference/workflow/) · [Metrics files](/docs/reference/metrics/) · [Run settings files](/docs/reference/run_settings/)
- **Guides** — [Define a workflow](/docs/reference/workflow/) · [Virtual parameter domains](/docs/configurations/virtual_param_domains/) · [Derived metrics](/docs/metrics/derived/)
- **Related tutorial** — [Run the workflow examples](/tutorials/run_examples/workflows/).
