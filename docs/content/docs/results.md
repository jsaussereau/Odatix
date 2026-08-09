---
title: "Results & Export"
description: "How Odatix stores results, how to export them, and how Odatix Explorer consumes them."
weight: 11
---

# Results & Export

After jobs finish, Odatix collects the metrics from each work directory and writes them into the `results/` directory. Those files are what [Odatix Explorer](/docs/gui/explorer/) reads.

{{< toc >}}

## When export happens

By default, run commands export results automatically when their jobs complete. You can opt out with `-e`/`--noexport` and export later, or re-export at any time with the dedicated commands.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado          # runs and exports
$ odatix fmax --tool vivado -e       # runs without exporting
$ odatix results                     # export afterwards
{{< /code >}}

## Export commands

| Command | Exports |
|---------|---------|
| `odatix results` | Fmax, custom-frequency and place & route results; optionally benchmark values; then derived metrics. |
| `odatix res_synth` | Fmax, custom-frequency and place & route results only. |
| `odatix res_benchmark` | Benchmark (simulation) results only. |
| `odatix res_workflow` | Workflow results only. |
| `odatix res_simulation` | Simulation results only (from the simulations' `_metrics.yml`). |
| `odatix res_derived` | Recompute metrics that import or combine values from other result files. |

Useful options for `odatix results`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results -u              # include benchmark values
$ odatix results -f csv          # format: csv, yml, or all
$ odatix results -t vivado -r results
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `-u` | Include benchmark values in the export. |
| `-f`, `--format` | Output format: `csv`, `yml`, or `all`. |
| `-t`, `--tool` | Restrict export to a given tool. |
| `-r` | Results directory to write to. |

## Exporting several job types together

Simulation and workflow records are exported by their dedicated commands, so a
complete post-processing pass after several kinds of jobs is explicit:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix res_synth       # synthesis and place & route
$ odatix res_simulation  # values defined in simulations/*/_metrics.yml
$ odatix res_workflow    # values defined in workflows/*/_metrics.yml
$ odatix res_derived     # join and compute cross-flow metrics
{{< /code >}}

`odatix results` is a convenient shorthand after a synthesis run: it exports
the synthesis/P&R results and recomputes derived metrics using any simulation
and workflow result files already present on disk. It does not replace
`res_simulation` or `res_workflow` when those files need to be rebuilt.

## What gets exported

Export produces machine-readable result files (YAML and/or CSV) under the results directory, one dataset per tool/flow. Each record ties a **design + configuration + target** to the **metrics** extracted for it — area, resources, timing, Fmax, power, benchmark figures, and any [custom workflow metrics](/docs/reference/workflow/) you defined.

Which metrics are extracted is governed by the [metrics definition files](/docs/metrics/base/): per-tool `metrics.yml` for synthesis, and `_metrics.yml` for simulations and workflows. Because extraction happens at export time, you can adjust those files and re-export without re-running any job.

To combine results from different job types, define a [derived metric](/docs/metrics/derived/) and run `odatix res_derived` after the source result files exist. This is the path from simulated cycles and synthesized Fmax to runtime, or from runtime and power to energy.

## Explore the results

Point Odatix Explorer at the results directory (the default is `results/`):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
$ odatix-explorer --input results
{{< /code >}}

From there you can compare configurations, correlate metrics, and export figures — see [Odatix Explorer](/docs/gui/explorer/).

## Cleaning up

Generated work directories can be large. Remove them with a cleanup profile:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix clean
$ odatix clean -i odatix_userconfig/clean.yml
{{< /code >}}

The profile's `remove_list` (see [Configuration reference](/docs/reference/run_settings/#cleanyml)) lists the glob patterns to delete.

## See also

- [Metrics](/docs/metrics/) — defining what gets extracted
- [Odatix Explorer](/docs/gui/explorer/)
- [Configuration reference](/docs/reference/)
- [Commands reference](/docs/commands/)
