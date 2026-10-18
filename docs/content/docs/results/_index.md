---
title: "Results & export"
description: "How Odatix collects metrics into result files, how to export them manually, and how to link results from different job types together."
weight: 10
---

# Results & export

A job leaves behind a work directory full of tool reports, logs and outputs. Odatix turns that into **results**: a list of records, each tying a *design + configuration + target* to the **metrics** measured for it — area, timing, Fmax, power, simulation cycles, whatever your workflow reports.

Results are written to the `results/` directory as plain YAML files. Those files are the input of [Odatix Explorer](/docs/gui/explorer/), and they are readable and diffable on their own.

{{< toc >}}

## Export happens automatically

You normally never have to think about exporting. Every run command exports its results when its jobs complete:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado      # runs the jobs, then exports the results
{{< /code >}}

Pass `-e`/`--noexport` when you want the jobs only — for instance because you plan to launch several batches and export once at the end:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -e   # run only, no export
{{< /code >}}

Nothing is lost by skipping the export: metrics are **extracted from the work directories at export time**, not while the job runs. As long as the work directories are still there, you can export whenever you want, as many times as you want.

## Exporting manually

That same property is what makes manual export useful: if a metric was missing or wrong, fix its definition and re-export — no job has to be re-run.

| Command | Exports |
|---------|---------|
| `odatix results` | Everything that was run: synthesis, fixed-frequency and place & route results, simulation and workflow results, then derived metrics. |
| `odatix results synth` | Synthesis, fixed-frequency and place & route results, and the RTL analyses. |
| `odatix results sim` | Simulation results only. |
| `odatix results workflow` | Workflow results only. |
| `odatix results analysis` | RTL analysis results, with their report. |
| `odatix results derived` | Recompute [derived metrics](/docs/results/derived_metrics/) over the result files already on disk. |

`odatix results` alone skips a kind of job whose work directory does not exist,
and applies the derived metrics last, since they read what the others wrote.
Every export that writes a results file again (`synth`, `sim`, `workflow`) also
applies the derived metrics right after, so re-exporting never drops them.
A type asked for explicitly whose work directory does not exist is an error; one
whose work directory holds no run has nothing to export. In both cases nothing is
written, so no empty results file shows up in Explorer.
One type at a time is for a single kind of result:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results synth      # synthesis and place & route
$ odatix results sim        # values defined in simulations/*/_metrics.yml
$ odatix results workflow   # values defined in workflows/*/_metrics.yml
$ odatix results derived    # join and compute cross-source metrics
{{< /code >}}

Useful options for `odatix results` (they are those of `odatix results all`,
see `odatix results all -h`; the options of a type come after it, see
`odatix results <type> -h`):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results -t vivado -r results
$ odatix results derived -d my_derived_metrics.yml
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `-t`, `--tool` | Restrict the synthesis and place & route export to a given tool. |
| `-w`, `--work` | Work directory to read. |
| `-r`, `--respath` | Results directory to write to. |
| `-m`, `--metrics` | Metrics definition file to use instead of the `metrics.yml` of each tool. |
| `-c`, `--config` | Workspace settings file (default `odatix.yml`). |
| `-d`, `--derived` | `odatix results derived` only: derived metrics file (default: the one of the workspace). |

A job that did not finish is skipped with a warning. A value a metric cannot read
(a missing report, a pattern that matches nothing) is an error naming the job, the
metric and the file, once per job; the export goes on with the rest.

### Exit status

`odatix results` exits with `1` as soon as an error was reported, even if everything
else was exported, and its last line says how many: a metric definition to fix must
not go unnoticed in a script or a CI job. Warnings (an unfinished job, a derived
metric with no source) do not change the exit status.

### From a script

{{< code lang=python filename="export.py" >}}
from odatix.workspace import Workspace
from odatix.run import export_results

ws = Workspace.open()
report = export_results(ws, "derived")      # or "all", "synth", "sim", ...
print(report.summary())                     # Derived metrics updated in 1 results file
if not report:
    print(report.errors())
{{< /code >}}

The GUI page **Derived metrics** applies them when it saves, and on its
**Apply to results** button.

## Metrics come with the tools

You do not have to declare anything to get results. Every EDA tool shipped with Odatix comes with its own `metrics.yml`, which already defines the values worth extracting from that tool's reports — LUT and register counts, BRAM and DSP usage, Fmax, area, static and dynamic power, and so on. Run a Vivado synthesis and you get the Vivado metrics; run Design Compiler and you get the Design Compiler ones.

Those definitions are just YAML, and they are not a closed list. You can **add your own metrics** to a tool, or define metrics for your own [workflows](/docs/reference/workflow/) and simulations in their `_metrics.yml` file, using `regex`, `csv`, `yaml`, `json`, `xml` or `operation` rules. Anything your tool or your script writes to a file can become a metric.

{{< card title="Metrics" link="/docs/results/metrics/" >}}
How metrics are declared, the extraction rule types available, and how to add metrics to a tool, a workflow or a simulation.
{{< /card >}}

## Linking results from different sources

A metric extracted this way can only describe the job that produced it. But the interesting numbers often span job types: a *simulation* knows how many cycles a benchmark takes, a *synthesis* knows at what frequency the design closes timing — neither can state a runtime on its own.

**Derived metrics** close that gap. Declared once for the whole workspace in `odatix_userconfig/derived_metrics.yml`, they can import a metric from another result — matched on architecture, configuration, target, parameter domains — and compute new values from it. Cycles + Fmax gives runtime; runtime + power gives energy per operation.

They are recomputed from the existing result files once every job of a run is done, and by every `odatix results` (all types) and `odatix results derived`, in seconds, without touching a single job.

{{< card title="Derived metrics" link="/docs/results/derived_metrics/" >}}
Import a metric from a matching result, control how the two are joined, and compute values across simulation, synthesis and workflows.
{{< /card >}}

## Explore the results

Point Odatix Explorer at the results directory (the default is `results/`):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
$ odatix-explorer --input results
{{< /code >}}

From there you can compare configurations, correlate metrics and export figures — see [Odatix Explorer](/docs/gui/explorer/).

## Cleaning up

`odatix clean` removes what a clean profile lists. The default profile only lists the
files eda tools leave at the workspace root (`.Xil`, `*.jou`, `vivado*.log`, ...): it
**keeps the work directories**. Result files are small, the work directories are not;
to remove them once you are satisfied with the exported results, add `work/` to the
profile's `remove_list` (see [Configuration reference](/docs/reference/run_settings/#clean_settingsyml)):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix clean                 # what the profile lists; "Nothing to clean" otherwise
$ odatix clean -i my_clean.yml # another profile
{{< /code >}} Keep in mind that once the work directories are gone, re-exporting is no longer possible — only `odatix results derived`, which works from the result files themselves, still is.

## In this section

{{< doc-cards cols="3" >}}
{{< doc-card title="Metrics" link="/docs/results/metrics/" icon="gauge" accent="#db2777" >}}
Extract any value from a job's reports and outputs with `regex`, `csv`, `yaml`, `json`, `xml` or `operation` rules.
{{< /doc-card >}}

{{< doc-card title="Derived metrics" link="/docs/results/derived_metrics/" icon="route" accent="#db2777" >}}
Link results of different job types together: import a metric from a matching result, and compute values across sources.
{{< /doc-card >}}

{{< doc-card title="Results file format" link="/docs/results/format/" icon="code" accent="#db2777" >}}
The YAML format results are stored in: schema, units, records, and the meaning of every `meta` field.
{{< /doc-card >}}
{{< /doc-cards >}}
