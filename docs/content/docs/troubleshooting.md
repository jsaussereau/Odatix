---
title: "Troubleshooting"
description: "Find and fix common Odatix installation, configuration, execution and export problems."
weight: 200
---

# Troubleshooting

This page is a first-response guide for common Odatix failures. Start from the
job directory and the exact command that failed: both preserve more information
than a summary alone.

{{< toc >}}

## Fast triage

1. Re-run the failing job command with `-D`/`--debug` when that option is
   available.
2. Read the affected job's `log/` and `report/` directories under `work/`.
3. Check the relevant YAML file for the architecture, simulation, workflow or
   tool named in the error.
4. Re-export rather than re-run when the job succeeded but only the metrics are
   missing.

Unexpected application exceptions are written to `odatix_error.log` in the
workspace root.

## Common symptoms

| Symptom | Likely cause | What to check |
|---------|--------------|---------------|
| `odatix: command not found` | Odatix is not installed in the active shell environment. | Activate the intended virtual environment, then run `python3 -m pip show odatix`. |
| The EDA tool check fails | The executable, module, licence or target setup is unavailable. | Run the tool's native version command in the same terminal; then check `PATH`, environment modules and `tool_install_path`. |
| No jobs are planned | The selected names do not match existing configurations, or the run settings list is empty. | Check `architectures`, `simulations` or `workflows` in the corresponding `*_settings.yml`. |
| A parameter block cannot be found | `start_delimiter` or `stop_delimiter` does not exactly match the copied source. | Use `odatix replace` to test the delimiters against one source/configuration pair. |
| A job is skipped unexpectedly | A matching work directory is already managed by an active daemon or contains a completed step. | Use `odatix ls`; use `--rerun-from` for a stepped flow or `-o` only when overwriting is intended. |
| Explorer has no new data | The relevant result file was not exported, or Explorer points to a different directory. | Re-export the job type and start Explorer with `--input <results-directory>`. |
| A derived metric is missing | Its source result is absent or no result matches its join criteria. | Export source job types first, inspect `derived_metrics.yml`, then run `odatix res_derived`. |

## Tool and environment checks

A failed preflight check is usually better than hundreds of failed jobs. Fix the
runtime environment first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ command -v verilator
$ verilator --version
$ odatix analyze --tool verilator -D
{{< /code >}}

`-T`/`--trust` skips Odatix's EDA-tool preflight check. Use it only when the
execution environment is already known to be correct — it does not repair a
missing executable, licence or PDK.

On a shared machine, load required modules before launching the session. See
[Environment modules](/tutorials/modules/).

## Configuration and parameter problems

A new design should be validated in small steps:

1. Confirm that `rtl_path`, `top_level_file`, `top_level_module`, clock and
   reset names in the architecture `_settings.yml` match the sources.
2. If parameters are enabled, run `odatix replace` with one parameter file and
   inspect the output.
3. If configuration generation is enabled, run `odatix generate -D` and verify
   the generated `.txt` files before a job run.
4. Run [RTL analysis](/docs/features/analysis/) on one configuration before launching a
   broad synthesis selection.

For generated RTL, `param_target_file` must point to the generator source,
because the HDL top level does not exist until after generation.

## Daemon and session problems

List sessions first; do not start a duplicate campaign to discover whether the
first one is still running.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ls
$ odatix ls -S nightly
$ odatix monitor -S nightly
$ odatix stop -S nightly
{{< /code >}}

Use a meaningful `-S`/`--session` name for detached runs. The [Job Monitor &
Sessions](/docs/gui/monitor/) page explains selectors, reattachment and the
scheduling policy.

## Export and metric problems

Successful jobs and successful exports are separate concerns. If the job
output exists but a chart is empty, re-run the smallest applicable exporter:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix res_synth
$ odatix res_simulation
$ odatix res_workflow
$ odatix res_derived
{{< /code >}}

Check the relevant `metrics.yml` or `_metrics.yml` paths and patterns against
the files in the job directory. Metrics are extracted during export, so fixing a
pattern normally does not require repeating the EDA run.

See [Results & export](/docs/results/) and [Base metrics](/docs/results/metrics/)
for the result formats and metric definitions.

## Remote access problems

Keep Explorer bound to the server's loopback interface and forward its port
through SSH when possible. This avoids opening a dashboard port on the network.
See [Hosting on a server](/docs/gui/host_server/) and the [SSH tutorial](/tutorials/ssh/).

## Reporting a problem

When asking for help, include:

- the Odatix version and platform;
- the exact command and its terminal output;
- the relevant `_settings.yml`, target or `tool.yml` excerpt, with secrets
  removed;
- the failed job's `log/` files and a short directory tree;
- `odatix_error.log` if Odatix reports an internal error.

> [!CAUTION]
> Do not include licence files, access tokens, private PDK data or confidential source code.
