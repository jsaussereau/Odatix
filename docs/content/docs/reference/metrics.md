---
title: "Metrics Files"
description: "Where metric definitions live — metrics.yml, _metrics.yml and derived_metrics.yml — and the schema of an entry."
weight: 8
---

# Metrics files

A **metric** is one value Odatix extracts from what a run produced, and one
column you can chart in [Explorer](/docs/features/explorer/). Three kinds of
files declare them.

{{< toc >}}

## Which file declares what

| File | Declares | Applies to |
|------|----------|------------|
| `tools/<tool>/metrics.yml` | What to extract from an eda tool's reports. | Every synthesis, analysis and place & route run of that tool. |
| `simulations/<sim>/_metrics.yml` | What to extract from a testbench run. | That simulation. |
| `workflows/<name>/_metrics.yml` | What to extract from a workflow's outputs. | That workflow. |
| `odatix_userconfig/derived_metrics.yml` | Metrics **computed from** other metrics, possibly across result kinds. | The workspace. |

A tool's metrics file is named by `default_metrics_file` in its
[`tool.yml`](/docs/reference/tools/), or per flow by `flows.<name>.metrics_file`.
The workspace derived metrics file is named by `derived_metrics_file` in
[`odatix.yml`](/docs/reference/workspace/).

## Sections of a tool's `metrics.yml`

| Section | Applies to |
|---------|------------|
| `metrics` | Every synthesis run of the tool (area, resources, power…). |
| `fmax_synthesis_metrics` | `odatix fmax` runs only. |
| `custom_freq_synthesis_metrics` | `odatix synth` runs only. |

Simulation and workflow files use a single `metrics` section, plus an optional
`metadata` section.

## Schema of a metric entry

| Key | Required | Description |
|-----|----------|-------------|
| `type` | Yes | Extraction method: `regex`, `csv`, `yaml`, `json`, `xml`, `benchmark` or `operation`. |
| `settings` | Yes | Type-specific settings, below. |
| `format` | No | Numeric formatting string, e.g. `"%.2f"`. |
| `unit` | No | Unit label exported with the value, e.g. `MHz`. |
| `error_if_missing` | No | Default `true`. Set to `false` when a value may legitimately be absent. |
| `step` | No | Synthesis only. Name of the [flow step](/docs/tools/add_flows/) the metric is extracted from. `$step` in `settings.file` resolves to it, and the metric is left out of the record when the job did not reach that step. |
| `benchmark_only` | No | Synthesis only. Extract only when benchmark export is enabled. |
| `multiple` | No | Workflows and simulations only. Default `false`; `true` extracts every match and expands the run into one record per row. Supported by `regex`, `csv` and `xml`. |

### Type-specific `settings`

| `type` | Keys |
|--------|------|
| `regex` | `file`, `pattern`, `group_id` |
| `csv` | `file`, `key` (column header) |
| `yaml` | `file`, optional `key` |
| `json` | `file`, optional `key` |
| `xml` | `file`, optional `key` (ElementTree path, optional trailing `@attribute`) |
| `benchmark` | `key` |
| `operation` | `op` — an expression over metrics extracted earlier in the same file |

{{< code lang=yaml filename="workflows/<name>/_metrics.yml" >}}
metrics:
  letters:
    type: regex
    settings:
      file: output.txt
      pattern: "letters: ([0-9]+)"
      group_id: 1
    format: "%.0f"

  best_val_accuracy:
    type: json
    settings:
      file: workflow_results.json
      key: best_val_accuracy
    format: "%.6f"
{{< /code >}}

Every type, with worked examples and the `multiple`/`metadata` mechanism, is
documented on **[Base metrics](/docs/results/metrics/)**.

## `derived_metrics.yml`

Derived metrics compute a value from metrics a result already has, or import one
from a *different* kind of result — the canonical case being a simulation's
cycle count meeting a synthesis's Fmax to produce a runtime.

| Section | Content |
|---------|---------|
| `groups` | Named sets of designs, reusable in a metric's `for` key as `"@group"`. |
| `derived_metrics` | The metric definitions themselves. |

The two kinds are `import` (read a metric from a matching result of another
kind, keyed by `from`) and `operation` (evaluate an `op` expression). Every key
— `apply_to`, `for`, `where`, `source_where`, `on_multiple`, `match` and the
dimension-joining rules — is documented on
**[Derived metrics](/docs/results/derived_metrics/)**.

## In the GUI

The **Metrics editors** build these entries in a form — extraction type, file,
pattern — for a tool, a workflow or a simulation. **Derived Metrics**
(`/derived_metrics`) edits `derived_metrics.yml`. See
[The Odatix GUI](/docs/gui/app/).

## See also

- [Base metrics](/docs/results/metrics/) — every extraction type, in full.
- [Derived metrics](/docs/results/derived_metrics/) — combining results across job types.
- [Results & export](/docs/results/) — where extracted metrics end up.
- [Tool definitions](/docs/reference/tools/) — pointing a tool at its metrics file.
