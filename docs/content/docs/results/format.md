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
| `results_<tool>.yml` | Synthesis, fixed-frequency and place & route results of one EDA tool (`results_vivado.yml`, `results_design_compiler.yml`, …). |
| `results_simulation.yml` | Simulation results. |
| `results_workflow.yml` | Workflow results. |
| `results_analysis_<tool>.yml` | RTL analysis results of one tool: one record per design and configuration, with its verdict and its warning and error counts. Shown by the **RTL Analysis** page of Explorer rather than by the charts. |

One file per source keeps things separable — you can delete, regenerate or share a single tool's results without touching the others. [Odatix Explorer](/docs/gui/explorer/) reads every result file it finds in the directory and presents them together, and [derived metrics](/docs/results/derived_metrics/) are exactly the mechanism that connects records across those files.


## Structure of a file

A result file has three top-level keys:

{{< code lang=yaml filename="results/results_vivado.yml" >}}
schema: 2

units:
  Worst_Slack: ns
  Total_Power: W

results:
  # ... the "elaboration" and "synthesis" records of the same job come first
  - meta:
      type: custom_freq_synthesis
      target: xc7a100t-csg324-1
      architecture: Example_Counter_verilog
      configuration: 08bits
      tool: vivado
      flow: standard
      frequency: 100
      step: pnr
      _step_index: 2
      _last_step: true
      main: 08bits
      timestamp: 2026-10-18_15-07-53
    metrics:
      LUT_count: 9
      Reg_count: 8
      Worst_Slack: 7.53
      Total_Power: 0.094
{{< /code >}}

This is one record of `odatix synth --tool vivado --at 100 -a Example_Counter_verilog/08bits`.
The frequency the job ran at is a dimension of the record (`meta.frequency`), not a
metric. Vivado runs in three steps, so the job wrote three records; this one is its
last step (`_last_step: true`).

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
| `type` | Kind of job: `fmax_synthesis`, `custom_freq_synthesis`, `pnr`, `simulation`, `workflow` or `analysis`. |
| `tool` | EDA tool the job ran with (`vivado`, `design_compiler`, …). |
| `flow` | Flow of that tool the job ran with. |
| `step` | Step of the flow this record was exported at. A flow split into steps writes one record **per step** (`synthesis`, `pnr`...), each with its own metrics; the informational key `_last_step: true` marks the furthest step the job reached, and `_step_index` its position in the flow. Absent for a job whose flow has no steps. |
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

Keys prefixed with an underscore — `_run_dir`, for instance — are informational only. They are carried along for traceability but are never used as a dimension, never grouped by, and never offered as an axis. Among them:

| Field | Meaning |
|-------|---------|
| `_step_index`, `_last_step` | Position of the step in the flow, and whether it is the furthest step the job reached. Explorer turns `_last_step` into the **Step scope** dimension (`last` / `intermediate`); by default its filters only show `last`. |
| `_status`, `_log_file` | Analysis records only: the verdict (`PASSED`, `WARNING`, `FAILED`...) and the log it was read from. |
| `_derived` | The metrics of the record that [derived metrics](/docs/results/derived_metrics/) wrote, so that they can be recomputed. |

## Reading a result file yourself

Since the format is a flat list, consuming it takes a few lines. A job split into
steps has one record per step: keep the last one to get the finished result.

{{< code lang=python filename="read_results.py" >}}
import yaml

with open("results/results_vivado.yml") as f:
  data = yaml.safe_load(f)

for record in data["results"]:
  meta = record["meta"]
  metrics = record["metrics"]
  if not meta.get("_last_step", True):  # an intermediate step of the job
    continue
  print(meta["architecture"], meta["configuration"], meta.get("frequency"), metrics.get("LUT_count"))
{{< /code >}}

`Fmax` is a metric of `odatix fmax` results only: a fixed-frequency synthesis
(`odatix synth`) gives its frequency in `meta.frequency` instead.

Inside Odatix, both the exporters and Odatix Explorer go through a single shared module, `odatix.lib.results_schema`, which is the source of truth for reading and writing this format.

## Older files

Result files produced by Odatix versions before 4.0 used a nested layout (target → architecture → configuration → metrics, with a `Param_Domains` block inside each metrics section). Odatix still **reads** those files and converts them to the current records on the fly, so old results keep working in Odatix Explorer 4.0+. New files are always written in schema 2 — re-exporting an old workspace is enough to migrate it.
