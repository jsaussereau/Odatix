---
title: "Metrics"
description: "What Odatix measures: values extracted from each job's outputs, and values derived from other results."
weight: 10
---

# Metrics

A **metric** is a single value attached to a result — LUT count, Fmax, power, simulation cycles, a training loss. Metrics are what end up in the [exported results](/docs/results/), what you compare between configurations, and what you plot in [Odatix Explorer](/docs/gui/explorer/).

Odatix does not hard-code any metric. Everything is declared in plain YAML files, so you can measure whatever your tool or script happens to report.

{{< toc >}}

## Two ways a result gets a metric

| | Where the value comes from | Declared in |
|---|---|---|
| **[Base metrics](/docs/metrics/base/)** | The job's own output files — a report, a log, a CSV, a JSON your script wrote. | `metrics.yml` (per EDA tool), `_metrics.yml` (per workflow or simulation) |
| **[Derived metrics](/docs/metrics/derived/)** | *Another* result, or an expression over metrics the result already has. | `odatix_userconfig/derived_metrics.yml` (one file for the whole workspace) |

Base metrics are extracted at **export** time, from the files a single job produced. They can only describe that job.

Derived metrics exist because the interesting numbers often span job types. A simulation knows how many cycles a benchmark takes; a synthesis knows at what frequency the design closes timing. Neither can state a runtime in microseconds on its own. A derived metric imports the cycle count onto the synthesis result, then computes the runtime from both.

{{< card title="Base metrics" link="/docs/metrics/base/" >}}
Extract values from a job's outputs with `regex`, `csv`, `yaml`, `json`, `xml`, `benchmark` or `operation` rules — and expand a run that produced a curve into one record per point.
{{< /card >}}

{{< card title="Derived metrics" link="/docs/metrics/derived/" >}}
Link results of different kinds together: import a metric from a matching result, control how the two are joined, and compute values across simulation and synthesis.
{{< /card >}}

## Re-running extraction

Neither kind of metric is computed while a job runs, so you can fix a definition and re-export without re-running anything:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results          # export everything, then apply derived metrics
$ odatix res_workflow     # workflow results only
$ odatix res_simulation   # simulation results only
$ odatix res_derived      # re-apply derived metrics over existing results
{{< /code >}}

## See also

- [Results & export](/docs/results/) — where metrics end up.
- [Configuration reference](/docs/reference/metrics/) — the condensed schema.
- [Odatix Explorer](/docs/gui/explorer/) — plotting the metrics you defined.
