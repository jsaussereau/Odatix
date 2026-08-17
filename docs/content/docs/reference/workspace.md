---
title: "Workspace Settings (odatix.yml)"
description: "Every key of odatix.yml: where an Odatix workspace keeps its designs, its work directories, its results and its settings files."
weight: 1
---

# `odatix.yml`

`odatix.yml` sits at the root of a workspace and answers one question: **where
does everything live**. Every key is optional — a workspace whose `odatix.yml`
is empty uses the defaults below, which is what `odatix init` produces.

Use `-c/--config` on any command to read a different file, which is how several
workspace layouts can share one directory.

{{< toc >}}

## Work directories

Jobs run in `<work_path>/<job type path>/<tool>/<target>/<design>/<config>/`.
The per-job-type keys are **relative to `work_path`**.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `work_path` | path | `work` | Root of every generated working directory. |
| `fmax_synthesis_work_path` | path | `fmax_synthesis` | Work directory of `odatix fmax`. |
| `custom_freq_synthesis_work_path` | path | `custom_freq_synthesis` | Work directory of `odatix synth`. |
| `pnr_work_path` | path | `pnr` | Work directory of `odatix pnr`. |
| `analysis_work_path` | path | `analysis` | Work directory of `odatix analyze`. |
| `simulation_work_path` | path | `simulations` | Work directory of `odatix sim`. |
| `workflow_work_path` | path | `workflows` | Work directory of `odatix workflow`. |

> [!NOTE]
> `sim_work_path`, `fmax_work_path` and `custom_freq_work_path` are **no longer
> supported**. Odatix warns and points at the current names.

## Definition directories

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `arch_path` | path | `odatix_userconfig/architectures` | Where [designs](/docs/reference/architecture/) are defined. |
| `sim_path` | path | `odatix_userconfig/simulations` | Where [simulations](/docs/reference/simulation/) are defined. |
| `workflow_path` | path | `odatix_userconfig/workflows` | Where [workflows](/docs/reference/workflow/) are defined. |
| `target_path` | path | `odatix_userconfig/targets` | Where [`target_<tool>.yml`](/docs/reference/targets/) files are looked up. |
| `tools_path` | path | `odatix_userconfig/tools` | Where workspace [eda tool definitions](/docs/reference/tools/) live. |

> [!NOTE]
> A `target_<tool>.yml` not found in `target_path` is also looked up directly in
> `odatix_userconfig/`, so workspaces created before `target_path` defaulted to
> `odatix_userconfig/targets` keep working unchanged.

## Settings files

Each run command reads one settings file; these keys say which.

| Key | Type | Default | Read by |
|-----|------|---------|---------|
| `fmax_synthesis_settings_file` | path | `odatix_userconfig/fmax_synthesis_settings.yml` | `odatix fmax` |
| `custom_freq_synthesis_settings_file` | path | `odatix_userconfig/custom_freq_synthesis_settings.yml` | `odatix synth` |
| `analysis_settings_file` | path | `odatix_userconfig/analysis_settings.yml` | `odatix analyze` |
| `simulation_settings_file` | path | `odatix_userconfig/simulations_settings.yml` | `odatix sim` |
| `workflow_settings_file` | path | `odatix_userconfig/workflow_settings.yml` | `odatix workflow` |
| `pnr_settings_file` | path | `odatix_userconfig/pnr_settings.yml` | `odatix pnr` |
| `clean_settings_file` | path | `odatix_userconfig/clean.yml` | `odatix clean` |
| `derived_metrics_file` | path | `odatix_userconfig/derived_metrics.yml` | `odatix res_derived` and every export |

Every one of them is also overridable per run with `-i/--input` (`--config` for
the workspace file itself).

## Results and export

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `result_path` | path | `results` | Where exported result files are written. |
| `use_benchmark` | bool | `false` | Include benchmark values in synthesis exports. |
| `benchmark_file` | path | `results/benchmark.yml` | Benchmark data read when `use_benchmark` is on. |

See [Results & export](/docs/results/) for what lands there.

## Example

{{< code lang=yaml filename="odatix.yml" >}}
# Keep the sources of the workspace in a shared directory, and the (large)
# work directories on a fast local disk.
arch_path:   ../shared/architectures
target_path: ../shared/targets
work_path:   /scratch/odatix_work
result_path: results

use_benchmark: Yes
{{< /code >}}

## In the GUI

**Workspace Settings** (`/workspace`) edits this file directly — every key
above has a field, and saving writes `odatix.yml`. See
[The Odatix GUI](/docs/gui/app/).

## See also

- [Run settings files](/docs/reference/run_settings/) — what each command actually runs.
- [Commands reference](/docs/commands/) — `-c/--config` and the other path options.
