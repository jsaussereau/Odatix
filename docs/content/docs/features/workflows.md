---
title: "Custom Workflows"
description: "Orchestrate arbitrary task pipelines — with dependencies, progress tracking and custom metrics — and sweep them across parameters, far beyond synthesis and simulation."
layout: "doc-features"
badge: "Automation"
badgeColor: "#ea580c"
cta: true
weight: 7
features:
  - title: "Arbitrary tasks"
    description: "Any command-line step becomes a task: build, generate, train, benchmark, measure."
  - title: "Dependencies"
    description: "Declare task dependencies; Odatix resolves the order and runs independent branches in parallel."
  - title: "Custom metrics"
    description: "Extract any value from your outputs with regex, CSV, JSON or XML rules and compare it in Explorer."
  - title: "Parameter sweeping"
    description: "Reuse parameter domains and configuration generation to sweep a workflow across configurations."
---

> [!IMPORTANT] Requires Odatix 4.0+

## Beyond synthesis and simulation

The `fmax`, `synth`, `pnr`, `analyze` and `sim` commands cover hardware
implementation and validation. **Workflows** generalize that engine to *anything
you can run on a command line*.

A workflow is a set of **tasks** with commands and dependencies. Odatix copies
your sources into an isolated work directory per configuration, runs the tasks in
parallel across configurations, tracks progress, and extracts the metrics you
define — all of which flow straight into
[Odatix Explorer](/docs/features/explorer/).

Everything Odatix does for synthesis, it does here for arbitrary tasks:
isolation, parallelism, progress tracking, metric extraction and parameter
sweeping.

{{< img src="/images/diagrams/workflow.svg" shadow="false">}}

## When you need it

- **Sweeping something that is not RTL.** A machine-learning training run per
  hyper-parameter, a compiler flag per build, a solver setting per instance —
  Odatix ships a TensorFlow example that explores a model exactly the way it
  explores a design.
- **Multi-stage validation.** A pipeline that generates a stimulus, builds a
  model, runs a simulation and compares outputs — more than a single testbench
  command can express.
- **Wrapping a home-grown flow.** A script you already have becomes parallel,
  monitored, cached and charted without being rewritten.
- **Cross-platform pipelines.** The same task declared once per platform, so one
  workflow runs on Linux, macOS and Windows.
- **Measuring anything.** If your tool prints it, writes it to a CSV or dumps it
  in a JSON, it can become a metric next to your area and timing figures.

## How it works

A workflow lives in `odatix_userconfig/workflows/<name>/` with two files:
`_settings.yml` (sources, progress, parameters and tasks) and `_metrics.yml`
(what to measure).

The task list is resolved like a makefile: execution starts at the task named
`main`, its dependencies run first, and independent branches run concurrently. A
task can declare a working `path`, and several entries can share a `name` with
different `platforms` — the one matching the current system wins, with a
platform-less entry as fallback.

Parameters reach a workflow in two ways:

- **File-based**, like a design: a delimited block of a source file is replaced
  with the configuration's parameter file.
- **Inline variables** — declared in `_settings.yml`, expanded as the
  cross-product of every variable, and substituted into commands as `${name}`.
  No folders, no parameter files. See
  [virtual parameter domains](/docs/configurations/virtual_param_domains/).

Progress comes from a file your tasks write to and a regex that reads a
percentage out of it, which is what fills the
[Job Monitor](/docs/gui/monitor/)'s progress bar.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | The same parameter domains and generation rules, applied to non-HDL work. |
| [Simulation](/docs/features/simulation/) | Simulations run on the very same task engine — a workflow is where to go when one testbench command is not enough. |
| [Explorer](/docs/features/explorer/) | Workflow metrics are ordinary records: chartable and correlatable against synthesis figures. |
| [Derived metrics](/docs/metrics/derived/) | Combine a workflow's numbers with a synthesis's, across job types. |
| [Job Monitor](/docs/gui/monitor/) | Progress, logs and session control, identical to a synthesis campaign. |

## Using it

### From the configuration files and the CLI

`_settings.yml` says what gets copied, what runs, and how progress is reported:

{{< code lang=yaml filename="workflows/basic/_settings.yml" >}}
sources:
  path: examples/workflow_simple
  blacklist:
    - "*.log"

progress:
  file: progress.txt
  regex: "Progress: ([0-9]+)"

use_parameters: Yes
param_target_file: "main.py"
start_delimiter: 'AWESOME_STRING = "'
stop_delimiter: '"'

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

`_metrics.yml` says what to keep from the files the tasks produced:

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

`workflow_settings.yml` says which workflows to run, and with which parameters:

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
nb_jobs: 8

workflows:
  - basic/default
  - tensorflow + epochs/*
  - param_domains_cli + max_speed/* + num_vehicles/*
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow
$ odatix workflow -d -S experiments   # detached, named session
$ odatix workflow -r                  # resume existing work directories
$ odatix res_workflow                 # re-export after editing _metrics.yml
{{< /code >}}

Every key is on the [workflow settings reference](/docs/reference/workflow/) and
the [metrics files reference](/docs/reference/metrics/); every option on the
[commands reference](/docs/commands/).

### From the GUI

`odatix-gui` → **Workflows** (`/workflows`) edits the definition: tasks and their
dependencies as cards, the sources and progress settings as fields, the inline
variables in the shared variable editor, and the metrics editor for
`_metrics.yml` — with the extraction type, file and pattern in a form. **Run
Jobs** → **Workflow** then selects which workflows and which parameter values to
launch, and enqueues them into the same daemon as the CLI.

## Where to go next

- **Tutorials** — [Run the workflow examples](/tutorials/run_examples/workflows/) · [Create your own workflow](/tutorials/own_designs/workflows/)
- **Reference** — [Workflow settings](/docs/reference/workflow/) · [Run settings files](/docs/reference/run_settings/#workflows--workflows-and-their-parameters) · [Metrics files](/docs/reference/metrics/)
- **Guides** — [Define a workflow](/docs/reference/workflow/) · [Virtual parameter domains](/docs/configurations/virtual_param_domains/) · [Base metrics](/docs/metrics/base/)
- **Related feature** — [Results exploration](/docs/features/explorer/), where a workflow's metrics end up.
