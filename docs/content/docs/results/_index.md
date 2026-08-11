---
title: "Results & Export"
description: "How Odatix collects metrics into result files, how to export them manually, and how to link results from different job types together."
weight: 10
---

# Results & Export

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
| `odatix results` | Synthesis, custom-frequency and place & route results, then derived metrics. |
| `odatix res_synth` | Synthesis, custom-frequency and place & route results only. |
| `odatix res_simulation` | Simulation results only. |
| `odatix res_workflow` | Workflow results only. |
| `odatix res_benchmark` | Benchmark (simulation) values only. |
| `odatix res_derived` | Recompute [derived metrics](/docs/results/derived_metrics/) over the result files already on disk. |

Each command exports the job types it owns, so a full post-processing pass after a mixed batch is explicit:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix res_synth       # synthesis and place & route
$ odatix res_simulation  # values defined in simulations/*/_metrics.yml
$ odatix res_workflow    # values defined in workflows/*/_metrics.yml
$ odatix res_derived     # join and compute cross-source metrics
{{< /code >}}

`odatix results` is the convenient shorthand after a synthesis run: it exports the synthesis and P&R results, then recomputes derived metrics using any simulation and workflow result files already present. It does *not* rebuild those files — use `res_simulation` and `res_workflow` for that.

Useful options for `odatix results`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results -u              # include benchmark values
$ odatix results -f csv          # format: csv, yml, or all
$ odatix results -t vivado -r results
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `-u` | Include benchmark values in the export. |
| `-f`, `--format` | Output format: `csv`, `yml` or `all`. |
| `-t`, `--tool` | Restrict the export to a given tool. |
| `-r` | Results directory to write to. |

## Metrics come with the tools

You do not have to declare anything to get results. Every EDA tool shipped with Odatix comes with its own `metrics.yml`, which already defines the values worth extracting from that tool's reports — LUT and register counts, BRAM and DSP usage, Fmax, area, static and dynamic power, and so on. Run a Vivado synthesis and you get the Vivado metrics; run Design Compiler and you get the Design Compiler ones.

Those definitions are just YAML, and they are not a closed list. You can **add your own metrics** to a tool, or define metrics for your own [workflows](/docs/reference/workflow/) and simulations in their `_metrics.yml` file, using `regex`, `csv`, `yaml`, `json`, `xml`, `benchmark` or `operation` rules. Anything your tool or your script writes to a file can become a metric.

{{< card title="Metrics" link="/docs/results/metrics/" >}}
How metrics are declared, the extraction rule types available, and how to add metrics to a tool, a workflow or a simulation.
{{< /card >}}

## Linking results from different sources

A metric extracted this way can only describe the job that produced it. But the interesting numbers often span job types: a *simulation* knows how many cycles a benchmark takes, a *synthesis* knows at what frequency the design closes timing — neither can state a runtime on its own.

**Derived metrics** close that gap. Declared once for the whole workspace in `odatix_userconfig/derived_metrics.yml`, they can import a metric from another result — matched on architecture, configuration, target, parameter domains — and compute new values from it. Cycles + Fmax gives runtime; runtime + power gives energy per operation.

Because they are recomputed from the existing result files, `odatix res_derived` applies them in seconds, without touching a single job.

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

Result files are small; the work directories they were extracted from are not. Once you are satisfied with the exported results, remove the work directories with a cleanup profile:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix clean
$ odatix clean -i odatix_userconfig/clean.yml
{{< /code >}}

The profile's `remove_list` (see [Configuration reference](/docs/reference/run_settings/#cleanyml)) lists the glob patterns to delete. Keep in mind that once the work directories are gone, re-exporting is no longer possible — only `res_derived`, which works from the result files themselves, still is.

## In this section

{{< doc-cards cols="3" >}}
{{< doc-card title="Metrics" link="/docs/results/metrics/" icon="gauge" accent="#db2777" >}}
Extract any value from a job's reports and outputs with `regex`, `csv`, `yaml`, `json`, `xml`, `benchmark` or `operation` rules.
{{< /doc-card >}}

{{< doc-card title="Derived metrics" link="/docs/results/derived_metrics/" icon="route" accent="#db2777" >}}
Link results of different job types together: import a metric from a matching result, and compute values across sources.
{{< /doc-card >}}

{{< doc-card title="Results file format" link="/docs/results/format/" icon="code" accent="#db2777" >}}
The YAML format results are stored in: schema, units, records, and the meaning of every `meta` field.
{{< /doc-card >}}
{{< /doc-cards >}}
