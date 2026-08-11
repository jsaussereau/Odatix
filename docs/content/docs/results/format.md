---
title: "Results file format"
description: "The YAML format Odatix results are stored in: schema version, units, records, and the meaning of every meta field."
weight: 3
---

# Results file format

Exported results are plain YAML. Nothing about them is opaque: you can open a result file in an editor, diff two of them in Git, or read them from your own script with any YAML library.

{{< toc >}}

## Files and naming

Result files live in the results directory (`results/` by default) and are named after the source that produced them:

| File | Contents |
|------|----------|
| `results_<tool>.yml` | Synthesis, custom-frequency and place & route results of one EDA tool (`results_vivado.yml`, `results_design_compiler.yml`, …). |
| `results_simulation.yml` | Simulation results. |
| `results_workflow.yml` | Workflow results. |

One file per source keeps things separable — you can delete, regenerate or share a single tool's results without touching the others. [Odatix Explorer](/docs/gui/explorer/) reads every result file it finds in the directory and presents them together, and [derived metrics](/docs/results/derived_metrics/) are exactly the mechanism that connects records across those files.


## Structure of a file

A result file has three top-level keys:

{{< code lang=yaml filename="results/results_vivado.yml" >}}
schema: 2

units:
  Frequency: MHz
  Total_Power: W

results:
  - meta:
      type: custom_freq_synthesis
      target: xc7a100t-csg324-1
      architecture: Example_ALU_sv
      configuration: 04bits
      tool: vivado
      frequency: 30
      main: 04bits
      timestamp: 2026-07-21_09-44-35
    metrics:
      Frequency: 30
      LUT_count: 28
      Reg_count: 16
      Total_Power: 0.092
{{< /code >}}

| Key | Meaning |
|-----|---------|
| `schema` | Version of the format. The current version is `2`. |
| `units` | Maps a metric name to its unit, taken from the `unit` field of the [metric definition](/docs/results/metrics/). Used for axis and column labels. |
| `results` | A **flat list of records**. Each record is one measured point. |

The list is flat on purpose: there is no nesting by target, then architecture, then configuration. Every record carries its own full identity, which makes the file easy to filter, concatenate and process without walking a tree.

## A record: `meta` and `metrics`

Each record has exactly two parts:

- **`meta`** — *what was measured*: the design, its configuration, the target, the tool, the kind of job. These are the dimensions you group and filter by.
- **`metrics`** — *the values measured*: the numbers extracted by the metric definitions.

### Reserved `meta` fields

These keys have a fixed meaning across all result files:

| Field | Meaning |
|-------|---------|
| `type` | Kind of job: `fmax_synthesis`, `custom_freq_synthesis`, `pnr`, `simulation` or `workflow`. |
| `tool` | EDA tool the job ran with (`vivado`, `design_compiler`, …). |
| `flow` | Flow of that tool the job ran with. |
| `step` | Last step of that flow the job reached. |
| `target` | Synthesis target (FPGA part, technology node, …). |
| `architecture` | The design. |
| `configuration` | Full configuration name, including any `+domain/value` segments. |
| `frequency` | Requested frequency, for `custom_freq_synthesis` and for a `pnr` derived from one. |
| `workflow` / `simulation` | Name of the workflow or simulation, for those record types. |
| `timestamp` | When the job ran. |
| `source_type`, `source_tool`, `source_flow` | Place & route records only: the synthesis run the job started from. The same design placed & routed from a Design Compiler netlist and from a Genus one are two distinct results, so these are part of what identifies the record. |

### Parameter domains

[Parameter domains](/docs/configurations/param_domains/) are **flattened into `meta`**: each domain becomes its own key, holding the value used for that record. The main domain appears as `main`.

{{< code lang=yaml filename="results/results_vivado.yml" >}}
meta:
  architecture: Example_ALU_sv
  configuration: 04bits+pipeline/2stage
  main: 04bits
  pipeline: 2stage
{{< /code >}}

That is what lets Explorer use a domain directly as an axis or a legend, and what derived metrics match on when importing a value from another result.

Any `meta` key that is not reserved and does not start with `_` is treated the same way: a free dimension.

### Informational keys

Keys prefixed with an underscore — `_run_dir`, for instance — are informational only. They are carried along for traceability but are never used as a dimension, never grouped by, and never offered as an axis.

## Reading a result file yourself

Since the format is a flat list, consuming it takes a few lines:

{{< code lang=python filename="read_results.py" >}}
import yaml

with open("results/results_vivado.yml") as f:
  data = yaml.safe_load(f)

for record in data["results"]:
  meta = record["meta"]
  metrics = record["metrics"]
  print(meta["architecture"], meta["configuration"], metrics.get("Fmax"))
{{< /code >}}

Inside Odatix, both the exporters and Odatix Explorer go through a single shared module, `odatix.lib.results_schema`, which is the source of truth for reading and writing this format.

## Older files

Result files produced by Odatix versions before 4.0 used a nested layout (target → architecture → configuration → metrics, with a `Param_Domains` block inside each metrics section). Odatix still **reads** those files and converts them to the current records on the fly, so old results keep working in Odatix Explorer 4.0+. New files are always written in schema 2 — re-exporting an old workspace is enough to migrate it.
