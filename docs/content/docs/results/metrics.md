---
title: "Base metrics"
description: "Extract any value from a job's reports and outputs with regex, CSV, YAML, JSON or XML rules."
weight: 1
---

# Base metrics

A **base metric** is a value Odatix pulls out of a job's own output files — LUT count, Fmax, power, simulation cycles, a training loss. These metrics are what end up in the [exported results](/docs/results/) and what you plot in [Odatix Explorer](/docs/gui/explorer/).

Odatix does not hard-code any metric. Everything is declared in **metrics definition files**, so you can measure whatever your tool or script happens to report.

For values that come from *another* result rather than from the job's own files, see [Derived metrics](/docs/results/derived_metrics/).

{{< toc >}}

## Where metrics are defined

| Job type | File | Scope |
|----------|------|-------|
| Synthesis (`fmax`, `synth`) | `odatix_userconfig/tools/<tool>/metrics.yml` | Per EDA tool |
| Workflows (`workflow`) | `odatix_userconfig/workflows/<name>/_metrics.yml` | Per workflow |
| Simulations (`sim`) | `odatix_userconfig/simulations/<name>/_metrics.yml` | Per simulation |

A tool's `metrics.yml` is split into three sections:

| Section | Applied to |
|---------|-----------|
| `metrics` | Every synthesis run (area, resources, power…). |
| `fmax_synthesis_metrics` | `odatix fmax` runs only. |
| `custom_freq_synthesis_metrics` | `odatix synth` runs only. |

A workflow's `_metrics.yml` uses a single `metrics` section, plus an optional `metadata` section (see [Expanding one run into several records](#expanding-one-run-into-several-records)). A simulation's `_metrics.yml` is exactly the same file, in the simulation directory: its records carry both the simulation and the architecture configuration it ran on. A simulation without one exports nothing, which is fine for a testbench that only has to succeed.

## Anatomy of a metric

Each entry under `metrics` is named by its key — that name is the column you will see in the results and in Explorer.

{{< code lang=yaml filename="odatix_eda_tools/vivado/metrics.yml" >}}
metrics:
  LUT_count:
    type: regex
    settings:
      file: report/utilization.rep
      pattern: "\\| (Slice|CLB) LUTs \\s*\\|\\s*([0-9]+).*"
      group_id: 2
    format: "%.0f"
{{< /code >}}

| Key | Required | Description |
|-----|----------|-------------|
| `type` | Yes | Extraction method: `regex`, `csv`, `yaml`, `json`, `xml`, `benchmark` or `operation`. |
| `settings` | Yes | Type-specific settings (see below). |
| `format` | No | Numeric formatting string, e.g. `"%.2f"`. |
| `unit` | No | Unit label exported alongside the value, e.g. `MHz`. |
| `error_if_missing` | No | Default `true`. Set to `false` when a value may legitimately be absent. |
| `benchmark_only` | No | Synthesis only. Extract the metric only when benchmark export is enabled (`odatix results -u`). |
| `multiple` | No | Workflows only. Extract *every* match instead of the first — see [below](#expanding-one-run-into-several-records). |

All paths in `settings.file` are relative to the job's work directory.

## Extraction types

{{< tabs >}}
{{% tab name="regex" %}}
Match a pattern in a text file (a report, a log) and capture one group.

{{< code lang=yaml filename="metrics.yml" >}}
Fmax:
  type: regex
  settings:
    file: log/frequency_search.log
    pattern: "Highest frequency with timing constraints being met: ([0-9_]+) MHz"
    group_id: 1
  format: "%.0f"
  unit: MHz
{{< /code >}}

| Setting | Description |
|---------|-------------|
| `file` | File to search, relative to the work directory. |
| `pattern` | Python regular expression. Remember to escape backslashes in YAML (`\\|`, `\\s`). |
| `group_id` | 1-based index of the capture group holding the value. |
{{% /tab %}}

{{% tab name="csv" %}}
Read a named column from a CSV file.

{{< code lang=yaml filename="_metrics.yml" >}}
FER:
  type: csv
  settings:
    file: results.csv
    key: FER
{{< /code >}}

| Setting | Description |
|---------|-------------|
| `file` | CSV file, relative to the work directory. |
| `key` | Column header. Takes the first row, unless `multiple: true`. |
{{% /tab %}}

{{% tab name="yaml / json" %}}
Read a value from a structured file your task wrote.

{{< code lang=yaml filename="_metrics.yml" >}}
final_accuracy:
  type: json
  settings:
    file: workflow_results.json
    key: final_accuracy
  format: "%.6f"
{{< /code >}}

| Setting | Description |
|---------|-------------|
| `file` | YAML or JSON file, relative to the work directory. |
| `key` | Optional. Key to read; omit it to take the whole document's value. |

> [!NOTE]
> Writing a small `results.json` at the end of your script is usually the most robust way to expose metrics from a custom workflow — far less brittle than matching a regex against a log.
{{% /tab %}}

{{% tab name="xml" %}}
Read an element's text or attribute from an XML report.

{{< code lang=yaml filename="metrics.yml" >}}
Total_power:
  type: xml
  settings:
    file: report/power.xml
    key: "summary/power@total"
{{< /code >}}

| Setting | Description |
|---------|-------------|
| `file` | XML file, relative to the work directory. |
| `key` | ElementTree path to an element, relative to the root. Add a trailing `@attribute` to read an attribute instead of the element's text. Omit `key` to use the root element. |
{{% /tab %}}

{{% tab name="benchmark" %}}
Synthesis only. Pull a value from the benchmark file, so simulation figures can sit next to synthesis figures in the same record.

{{< code lang=yaml filename="metrics.yml" >}}
Cycles:
  type: benchmark
  settings:
    key: cycles
  benchmark_only: true
{{< /code >}}

Include these in the export with `odatix results -u`.
{{% /tab %}}

{{% tab name="operation" %}}
Compute a value from metrics already extracted — no file involved.

{{< code lang=yaml filename="metrics.yml" >}}
LUT+Reg_count:
  type: operation
  settings:
    op: LUT_count + Reg_count
  format: "%.0f"
{{< /code >}}

The `op` expression refers to other metrics **by name**. Only metrics extracted from files are available, so make sure the operands are defined in the same file.
{{% /tab %}}
{{< /tabs >}}

## Expanding one run into several records

Sometimes a single job produces a *curve* rather than one number — an error rate per SNR point, an accuracy per epoch. In a workflow, `multiple: true` extracts every matching row instead of just the first, and an optional `metadata` section labels each row.

`multiple: true` is supported by the `regex`, `csv` and `xml` types.

{{< code lang=yaml filename="workflows/ber_sweep/_metrics.yml" >}}
metrics:
  FER:
    type: csv
    settings:
      file: results.csv
      key: FER
    multiple: true
  BER:
    type: csv
    settings:
      file: results.csv
      key: BER
    multiple: true

# One extra dimension, extracted the same way, tagging each row
metadata:
  EBNO:
    type: csv
    settings:
      file: results.csv
      key: EBNO
    multiple: true
{{< /code >}}

Odatix expands that run into one exported record per row, each tagged with its own `EBNO` value — as if every point had been run as a separate configuration. In Explorer you can then use `EBNO` as an axis.

> [!IMPORTANT]
> All `multiple` fields of a run are aligned **by row index**, so they must yield the same number of rows. `metadata` is available for workflows and simulations.

## Iterating on your metrics

Metrics are extracted at **export** time, not during the run, so you can fix a pattern and re-export without re-running any job:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results          # re-export everything with the current definitions
$ odatix res_workflow     # workflow results only
$ odatix res_simulation   # simulation results only
{{< /code >}}

If a value cannot be found, Odatix reports an error naming the metric and the file — unless you set `error_if_missing: false`.

## See also

- [Derived metrics](/docs/results/derived_metrics/) — values a result gets from another result.
- [Results & export](/docs/results/) — where extracted metrics end up.
- [Define a workflow](/docs/reference/workflow/) — producing the outputs metrics read from.
- [Configuration reference](/docs/reference/metrics/) — the condensed schema.
- [Odatix Explorer](/docs/gui/explorer/) — plotting the metrics you defined.
