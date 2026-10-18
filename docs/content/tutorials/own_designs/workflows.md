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

This tutorial takes a script you already have and turns it into an Odatix
**workflow**: Odatix runs it once per combination of its parameters, in
parallel, shows its progress in the job monitor, and collects what it measures
as metrics you can chart in the Explorer. Nothing in it has to be RTL.

As for an [architecture](/tutorials/own_designs/architecture/), everything can
be done three ways, which read and write the same files:

| | |
|---|---|
| **Graphical interface** | `odatix-gui`, form by form. |
| **YAML files** | One directory with a `_settings.yml` and a `_metrics.yml`. What the GUI writes. |
| **Python API** | `odatix.workspace` and `odatix.run`, for a workspace built by a script. |

Each step below has the three versions in tabs.

## What a workflow is

A workflow is a **directory** in `odatix_userconfig/workflows/`:

{{< code lang=text filename="A workflow directory" >}}
odatix_userconfig/workflows/sort_bench/
├── _settings.yml     # what is copied, what runs, what is swept
└── _metrics.yml      # what is measured
{{< /code >}}

Your script stays where it is. For each job, Odatix copies its directory into a
run directory of its own, `work/workflows/sort_bench/<combination>/`, and runs
the tasks of the workflow there:

{{< code lang=text filename="What a job does" >}}
your sources ──copy──► run directory ──run the tasks──► read the metrics
{{< /code >}}

## Prerequisites

- [Odatix installed](/install/) and available in your `PATH`.
- `python3` in your `PATH`: the example script is in Python. No EDA tool is
  needed.
- An Odatix workspace. Create one in the directory of your choice (answer `n`
  when it offers to add the examples):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/my_project && cd ~/my_project
$ odatix init
{{< /code >}}

Throughout, the example is this small benchmark, which times a sorting
algorithm on a number of values, both given on its command line. It writes
what it measured to `result.json`, and its progress to `progress.txt`. Save it
as `~/my_project/scripts/sort_bench/bench.py`:

{{< code lang=python filename="scripts/sort_bench/bench.py" linenos="true" >}}
import argparse
import json
import random
import time

parser = argparse.ArgumentParser(description="Time a sorting algorithm")
parser.add_argument("--size", type=int, required=True, help="number of values to sort")
parser.add_argument("--algo", choices=["insertion", "merge"], required=True)
args = parser.parse_args()

random.seed(0)
values = [random.random() for _ in range(args.size)]
comparisons = 0


def report_progress(percent):
    with open("progress.txt", "w") as f:
        f.write("Progress: %d\n" % percent)


def insertion_sort(values):
    global comparisons
    values = list(values)
    for i in range(1, len(values)):
        j = i
        while j > 0:
            comparisons += 1
            if values[j - 1] <= values[j]:
                break
            values[j - 1], values[j] = values[j], values[j - 1]
            j -= 1
        report_progress(100 * i // len(values))
    return values


def merge_sort(values):
    global comparisons
    if len(values) <= 1:
        return values
    middle = len(values) // 2
    left, right = merge_sort(values[:middle]), merge_sort(values[middle:])
    merged = []
    while left and right:
        comparisons += 1
        merged.append(left.pop(0) if left[0] <= right[0] else right.pop(0))
    return merged + left + right


start = time.time()
result = insertion_sort(values) if args.algo == "insertion" else merge_sort(values)
seconds = time.time() - start
assert result == sorted(values)

with open("result.json", "w") as f:
    json.dump({"seconds": seconds, "comparisons": comparisons}, f)
report_progress(100)
print(args.algo, args.size, "values:", comparisons, "comparisons in", round(seconds, 4), "s")
{{< /code >}}

Check that it runs on its own first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ cd scripts/sort_bench && python3 bench.py --size 2000 --algo merge && cd -
merge 2000 values: 19419 comparisons in 0.0075 s
{{< /code >}}

## Step 1 — Create the workflow

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Start the GUI from your workspace:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

Open **Workflows** from the home page, then click the **Create new workflow**
card. You land on the workflow editor: type `sort_bench` as its name, in the
title at the top. This name is how the workflow is selected in every run
afterwards.

{{% /tab %}}
{{% tab name="YAML files" %}}

Create the directory and its settings file:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/workflows/sort_bench
$ touch odatix_userconfig/workflows/sort_bench/_settings.yml
{{< /code >}}

The directory name, `sort_bench`, is how the workflow is selected in every run
afterwards.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()                        # the workspace of the current directory
workflow = ws.workflows.create("sort_bench")
{{< /code >}}

The steps below complete this script; `workflow.save()` writes the settings
file at the end of it.

{{% /tab %}}
{{< /tabs >}}

## Step 2 — Say what is copied and how progress is read

| Setting | What it is |
|---------|------------|
| `sources.path` | The directory copied into every run directory. Relative to the workspace. |
| `use_parameters` | `No` here: the parameters reach the script on its command line, not by replacing a block of one of its files. |
| `progress.file`, `progress.regex` | The file the script writes its progress to, and the regex reading a percentage out of it. Optional: without them, the monitor shows no progress until the job ends. |

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the editor:

| Tile | Field | Value |
|------|-------|-------|
| Workflow sources | Source path | `scripts/sort_bench` |
| Parameters replacement | Enable parameter replacement | off |
| Progress tracking | Progress file | `progress.txt` |
| Progress tracking | Progress regex | `Progress: ([0-9]+)` |

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="workflows/sort_bench/_settings.yml" >}}
# What is copied into every run directory
sources:
  path: scripts/sort_bench

# The script reads its parameters on its command line, no file to replace
use_parameters: No

# What the job monitor reads its progress from
progress:
  file: progress.txt
  regex: "Progress: ([0-9]+)"
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
settings = workflow.settings
settings.sources.path = "scripts/sort_bench"
settings.use_parameters = False
settings.progress.file = "progress.txt"
settings.progress.regex = "Progress: ([0-9]+)"
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

## Step 3 — Write the task

A workflow runs **tasks**, and starts with the one named `main`. One task is
enough here: it runs the script with `${size}` and `${algo}` where the values
go. Odatix replaces them for each job, with the variables of the next step.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

The **Task definition** section already holds the `main` card. Type in its
**Commands (one per line)** field:

{{< code lang=text >}}
python3 bench.py --size ${size} --algo ${algo}
{{< /code >}}

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="workflows/sort_bench/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 bench.py --size ${size} --algo ${algo}
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
settings.tasks = [
    {"name": "main", "commands": ["python3 bench.py --size ${size} --algo ${algo}"]},
]
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

The commands run from the run directory, where `bench.py` was copied. A task
can also depend on others (`dependencies`), run from a directory of its own
(`path`), or have a fallback (`on_failure_commands`): see
[Workflow settings](/docs/reference/workflow/#tasks--the-pipeline).

## Step 4 — Declare what is swept

`size` and `algo` are **variables**: each one lists its values, and Odatix runs
one job per combination, 3 × 2 = 6 jobs here.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the **Variable definition** section, click **Add new variable** twice. On
the first card, replace the name `var1` with `size`, keep the type **List**,
and type `500, 1000, 2000` in **List**. On the second one, `algo`, with
`insertion, merge`.

Then click **Save all** in the header. The button turns to a warning colour
whenever something is unsaved.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="workflows/sort_bench/_settings.yml" >}}
variables:
  size:
    type: list
    settings:
      list: [500, 1000, 2000]
  algo:
    type: list
    settings:
      list: [insertion, merge]
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
settings.set_variable("size", "list", {"list": [500, 1000, 2000]})
settings.set_variable("algo", "list", {"list": ["insertion", "merge"]})
workflow.save()
print(workflow.count_combinations(), "combinations")   # 6
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

A list is one of several ways of giving values: ranges, powers of two and
functions of other variables are on [Variables](/docs/configurations/variables/).
In a file, `unit: kmh` makes the values read `35kmh`, and variables sharing a
`group` are paired instead of crossed.

## Step 5 — Say what is measured

`_metrics.yml` says which values to read in the run directory once a job ends.
`bench.py` wrote two of them to `result.json`, read with the `json` type. A
third one, of type `operation`, is computed from the other two.

| Metric | Type | Read from |
|--------|------|-----------|
| `seconds` | `json` | key `seconds` of `result.json`, written with 4 decimals |
| `comparisons` | `json` | key `comparisons` of `result.json` |
| `comparisons_per_second` | `operation` | `comparisons / seconds` |

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the workflow editor, click **Edit metrics**. In the **Metrics** section,
click **Add new metric** once per metric, and fill in each card: its name, its
type (**JSON** or **Operation**), then **File** and **Key** for a JSON one, or
**Operation** for the last one. **Unit** and **Format** are behind the
**Show/hide extra fields** button of the card: give `seconds` the unit `s` and
the format `%.4f`.

Click **Save all**.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="workflows/sort_bench/_metrics.yml" >}}
metrics:
  seconds:
    type: json
    settings:
      file: result.json
      key: seconds
    unit: s
    format: "%.4f"
  comparisons:
    type: json
    settings:
      file: result.json
      key: comparisons
  comparisons_per_second:
    type: operation
    settings:
      op: "comparisons / seconds"
    format: "%.0f"
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
metrics = workflow.metrics
metrics.set("seconds", {
    "type": "json", "settings": {"file": "result.json", "key": "seconds"},
    "unit": "s", "format": "%.4f",
})
metrics.set("comparisons", {"type": "json", "settings": {"file": "result.json", "key": "comparisons"}})
metrics.set("comparisons_per_second", {
    "type": "operation", "settings": {"op": "comparisons / seconds"}, "format": "%.0f",
})
metrics.save()
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

An operation computes on the values as they were read: the `format` of
`seconds` rounds what is written, not what `comparisons / seconds` divides by.
Regexes, CSV, YAML and XML files can be read too, and a run can produce several
records: see [Metrics files](/docs/reference/metrics/).

## Step 6 — Run it

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

From the home page, open **Run jobs**, then **Run workflow**. Switch
`sort_bench` on: its two variables are listed with their values, and the
preview lists the 6 combinations, all checked. The **Default configuration**,
the workflow without any value, is offered but not checked: its command would
get empty values.

Click **Run jobs**. The window that opens lists the jobs about to run; click
**Start**.

{{% /tab %}}
{{% tab name="YAML files" %}}

Open `odatix_userconfig/workflow_settings.yml`. Keep the settings at its top as
`odatix init` wrote them (each of them is required), and select the workflow:

{{< code lang=yaml filename="odatix_userconfig/workflow_settings.yml" >}}
workflows:
  - sort_bench                     # every combination of its variables
{{< /code >}}

`sort_bench + size/500 + algo/*` would run some of them only. Then:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow
{{< /code >}}

`odatix workflow -W sort_bench` runs it without touching the file.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="run.py" >}}
from odatix.workspace import Workspace
from odatix.run import Run

ws = Workspace.open()
run = Run(ws, "workflow", workflows=["sort_bench"])
plan = run.check()                   # what is going to run
print(plan.names(colored=False))
run.start()                          # hands the jobs to a session, and returns
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

Odatix checks the run first, then lists the jobs:

{{< code lang=text >}}
New workflows:
  - sort_bench [size:500, algo:insertion]
  - sort_bench [size:500, algo:merge]
  - sort_bench [size:1000, algo:insertion]
  - sort_bench [size:1000, algo:merge]
  - sort_bench [size:2000, algo:insertion]
  - sort_bench [size:2000, algo:merge]
{{< /code >}}

Each job runs in its own directory, for instance
`work/workflows/sort_bench/sort_bench+size_500+algo_merge/`, which holds the
copy of `bench.py`, what it wrote, and `workflow_done` once the job succeeded.
The [job monitor](/docs/sessions/terminal_monitor/) shows the progress the
script writes; the GUI one is in **Monitor jobs**.

Run the same selection again and nothing runs: a job that already succeeded is
listed under **Existing results** and skipped. `-o/--overwrite` (or
**Overwrite existing result** in the GUI) runs it again.

## Step 7 — Look at the results

Each job's metrics were exported as it ended, to
`results/results_workflow.yml`:

{{< code lang=yaml filename="results/results_workflow.yml" >}}
- meta:
    type: workflow
    workflow: sort_bench
    configuration: size/500+algo/merge
    size: '500'
    algo: merge
  metrics:
    seconds: 0.0016
    comparisons: 3854
    comparisons_per_second: 2411944
{{< /code >}}

Open them in the Explorer:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Each variable is a dimension: plot `seconds` against `size`, one line per
`algo`, to see insertion sort grow with the square of the size. Changed
`_metrics.yml` afterwards? Export again without running anything:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results workflow
{{< /code >}}

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Cannot find key "overwrite"` | `workflow_settings.yml` lost the settings at its top: they are all required. Copy them back from [Run settings files](/docs/reference/run_settings/). |
| A warning says a placeholder matches nothing | A `${name}` of the command is not a variable (a typo in `variables`, or in the command). The shell would replace it with nothing. |
| The job fails at once | Run the command by hand in its run directory, under `work/workflows/sort_bench/`. The job log in the monitor shows what it printed. |
| No metric in the results | The file a metric reads was not written, or its key is wrong. A workflow without `_metrics.yml` exports nothing, which is not an error. |
| The progress stays at 0 % | `progress.regex` does not match what the script writes to `progress.file`. |
| Nothing runs | Every job already succeeded: add `-o`. |

## Going further

- **Configurations.** A workflow can also have configuration files, like an
  architecture: `fast.txt` and `slow.txt` next to `_settings.yml`, selected as
  `sort_bench/fast`. Their content is `${sort_bench}` in the commands, or
  replaces a block of a source file with `use_parameters: Yes`. See the
  [`cli_profile`](/docs/examples/workflows/cli_profile/) and
  [`basic`](/docs/examples/workflows/basic/) examples.
- **Parameter domains.** Directories of configurations crossed with each
  other, as for an architecture. See [Parameter domains](/docs/configurations/param_domains/).
- **A task run once.** A task named after the file it produces, with
  `phony: No`, is skipped once the file exists: an environment to install, a
  dataset to download. See
  [A task that produces a file](/docs/reference/workflow/#a-task-that-produces-a-file).
- **Too many combinations.** Search them instead of running them all: see
  [Exploring a workflow](/docs/reference/dse/#exploring-a-workflow).

## See also

- [Workflow settings](/docs/reference/workflow/) — every key of `_settings.yml`.
- [Metrics files](/docs/reference/metrics/) — every key of `_metrics.yml`.
- [Run a workflow](/tutorials/run_examples/workflows/) — the examples Odatix ships.
- [Workflows](/docs/features/workflows/) — what workflows are for.
