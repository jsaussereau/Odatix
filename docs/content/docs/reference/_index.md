---
title: "Configuration File Reference"
description: "Every configuration file Odatix reads, and every key it accepts."
weight: 90
aliases:
  - /docs/settings/
---

# Configuration File Reference

This section is the exhaustive syntax reference: every configuration file of an
Odatix workspace, every key it accepts, its type, its default and what it does.

It is deliberately dry. If you are looking for *why* a file exists and *when* to
write one, read the [feature pages](/docs/features/) first; if you want to be
walked through writing one, follow a [tutorial](/tutorials/).

{{< toc >}}

## The files of a workspace

`odatix init` creates this layout. Every path below is a default, and every one
of them can be moved in [`odatix.yml`](/docs/reference/workspace/).

{{< code lang=text filename="An Odatix workspace" >}}
odatix.yml                                  # workspace settings: where everything lives
odatix_userconfig/
├── fmax_synthesis_settings.yml             # what "odatix fmax" runs
├── custom_freq_synthesis_settings.yml      # what "odatix synth" runs
├── analysis_settings.yml                   # what "odatix analyze" runs
├── simulations_settings.yml                # what "odatix sim" runs
├── workflow_settings.yml                   # what "odatix workflow" runs
├── pnr_settings.yml                        # what "odatix pnr" runs
├── derived_metrics.yml                     # metrics computed from other metrics
├── clean.yml                               # what "odatix clean" removes
├── architectures/<design>/_settings.yml    # a parametrizable design
│                        /<config>.txt      # one configuration of it
├── simulations/<sim>/_settings.yml         # a testbench and how it runs
│                   /_metrics.yml           # what it exports
├── workflows/<name>/_settings.yml          # a task pipeline
│                  /_metrics.yml            # what it exports
├── targets/target_<tool>.yml               # devices/technologies for one eda tool
└── tools/<tool>/tool.yml                   # an eda tool of your own
             /metrics.yml                   # what to extract from its reports
{{< /code >}}

## Reference pages

| Page | Files it documents |
|------|--------------------|
| [Workspace settings](/docs/reference/workspace/) | `odatix.yml` |
| [Run settings files](/docs/reference/run_settings/) | `fmax_synthesis_settings.yml`, `custom_freq_synthesis_settings.yml`, `analysis_settings.yml`, `simulations_settings.yml`, `workflow_settings.yml`, `pnr_settings.yml`, `clean.yml` |
| [Architecture settings](/docs/reference/architecture/) | `architectures/<design>/_settings.yml` and its parameter files |
| [Simulation settings](/docs/reference/simulation/) | `simulations/<sim>/_settings.yml` |
| [Workflow settings](/docs/reference/workflow/) | `workflows/<name>/_settings.yml` |
| [Target files](/docs/reference/targets/) | `targets/target_<tool>.yml` |
| [Tool definitions](/docs/reference/tools/) | `tools/<tool>/tool.yml`, flows and steps |
| [Metrics files](/docs/reference/metrics/) | `metrics.yml`, `_metrics.yml`, `derived_metrics.yml` |
| [Configuration API](/docs/reference/python_api/) | Reading and writing all of them from Python or with `odatix config` |

## How settings are resolved

Configuration is resolved in this order, highest priority first:

1. **Command-line options** — `--jobs`, `--overwrite`, `--tool`, `--config`…
2. **Run settings files** — `fmax_synthesis_settings.yml` and friends.
3. **Workspace settings** — `odatix.yml`.
4. **Internal defaults**.

Frequency bounds in an architecture's `_settings.yml` follow a second, nested
order — the most specific definition wins:

1. Target **and** configuration specific (`<target>` → `<config>` → `fmax_synthesis`).
2. Target specific (`<target>` → `fmax_synthesis`).
3. Global (`fmax_synthesis` at the root of the file).

## Conventions used on these pages

- **Required** means Odatix refuses to run without the key; *conditionally
  required* keys say what they depend on.
- Booleans accept YAML's `Yes`/`No`, `true`/`false`, `on`/`off`.
- Paths are relative to the workspace root unless stated otherwise.
- A key marked **deprecated** is still read, but will be removed.

## See also

- [Commands reference](/docs/commands/) — every option of every command, and which key it overrides.
- [Features](/docs/features/) — what each file is for, in prose.
- [Tutorials](/tutorials/) — writing these files step by step.
