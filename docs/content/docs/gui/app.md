---
title: "The Odatix GUI"
description: "Configure your workspace, launch jobs and follow them from the browser — everything the CLI does, without editing a YAML file."
weight: 0
---

# The Odatix GUI

> [!IMPORTANT] Requires Odatix 4.0+

`odatix-gui` is a local web application that covers the whole workflow: describing your designs, adding EDA tools, launching jobs, watching them run, and exploring the results. Everything it does is written back into the same YAML files the command line reads. 

> [!NOTE] 
> the GUI is a dashboard for your runs and an editor for your workspace, not a separate way of storing it.

{{< toc >}}

## Launch it

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

It starts a local server and opens your browser on the home page. Nothing is uploaded anywhere: the server runs on your machine, on your workspace.

## The home page

Eight cards, matching the eight things you do with Odatix:

| Card | Goes to |
|------|---------|
| **Workflows** | Configure your workflows. |
| **RTL Architectures** | Configure your designs, their configurations and their simulations. |
| **EDA Tools** | Add and configure the EDA tools of the workspace. |
| **Run Jobs** | Launch workflows, RTL analysis, synthesis, place & route. |
| **Monitor Jobs** | Follow the jobs currently running. |
| **Explore Results** | Open Odatix Explorer on the exported results. |
| **Workspace Settings** | Paths, settings files, and the workspace layout. |
| **Documentation** | This documentation. |

The same destinations are always one hover away in the top bar, grouped under **Configure**, **Run**, **Monitor**, **Explorer** and **Settings**.

If you start the GUI in a directory that is not a workspace yet, it offers to create one — empty, or preloaded with the examples.

## Configuring a workspace

| Page | What it edits |
|------|---------------|
| **RTL Architectures** (`/architectures`) | Your designs: sources, top level, clock and reset, parameter delimiters, target-specific bounds. Each design lists its configurations, with an editor for each parameter file. |
| **Simulations** (`/architectures#simulations`) | The testbenches of the workspace and their `_settings.yml`. |
| **Workflows** (`/workflows`) | Workflow definitions: tasks, dependencies, variables, and the metrics they export. |
| **EDA Tools** (`/tools`) | The tools of the workspace and, apart, the built-in ones. Create, duplicate, edit flows and steps, edit metrics. |
| **Derived Metrics** (`/derived_metrics`) | The workspace `derived_metrics.yml` — groups and derived metric definitions. |
| **Workspace Settings** (`/workspace`) | Where everything lives: settings files, work and result directories. |

Two editors are worth knowing by name because they save real work:

- The **Configuration Generator** turns a rule into a whole set of parameter files — ranges, powers of two, lists, functions — instead of writing them one by one. See [Configuration generation](/docs/configurations/config_generation/).
- The **Metrics editors** build `metrics.yml` and `_metrics.yml` entries with the extraction type, file and pattern in a form. See [Base metrics](/docs/results/metrics/).

A **save** button in the header turns to a warning colour as soon as something is unsaved, so you always know whether what you see is on disk.

## Launching jobs

**Run Jobs** walks you through the same choices the command line takes as options:

{{< code lang=text filename="Run a job" >}}
 Job type ──► EDA tool ──► flow / step ──► targets ──► job settings ──► Run
{{< /code >}}

1. **Job type** — workflow, simulation, RTL analysis, fmax synthesis, custom frequency synthesis, or place & route.
2. **EDA tool** (synthesis, analysis and place & route only) — each tool's card shows its flows as buttons and, when a flow is split into steps, its steps as "run up to here" buttons. Every one of them leads straight to the job settings, so a run stays one click away whatever the tool offers.
3. **Targets** — the FPGA devices or technologies to run on.
4. **Job settings** — which designs and configurations to run, frequency range or list, parallel jobs, overwrite, session name. These are the same values as the settings files, and saving them writes those files.

Selection pages act immediately: clicking a tool, a flow or a step navigates on, there is no intermediate confirmation screen.

Launching enqueues the jobs into the daemon exactly like the CLI does, and drops you on the Monitor. A run started from the GUI can be followed from a terminal with `odatix monitor`, and vice versa — there is one daemon, not one per interface.

## Monitoring and exploring

- **Monitor** (`/monitor`) — the graphical Job Monitor: live progress, per-job logs, and the list of daemon sessions. See [Job Monitor & sessions](/docs/gui/monitor/).
- **Explorer** (`/explorer`) — the results dashboard, reachable from the same interface, with its chart pages listed in the top bar. See [Odatix Explorer](/docs/gui/explorer/).

## Options

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
$ odatix-gui --network                  # expose on the local network
$ odatix-gui --port 8060 --nobrowser
$ odatix-gui --theme odatix_dark
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `-i`, `--input` | Results directory read by the Explorer pages (default `results`). |
| `-n`, `--network` | Expose the server on the local network. |
| `-p`, `--port` | Preferred HTTP port (default 8052, the next free one otherwise). |
| `-B`, `--nobrowser` | Do not open the browser automatically. |
| `-T`, `--theme` | Force a specific app theme. |
| `-N`, `--normal_term_mode` | Do not switch terminal mode. |
| `--safe_mode` | Keep running on internal errors. |
| `-c`, `--config` | Alternate workspace settings file (default `odatix.yml`). |

Running it on a remote machine — a build server, a licence server — works the same way, see [Hosting on a server](/docs/gui/host_server/).

## See also

- [Job Monitor & sessions](/docs/gui/monitor/) — following jobs, from the GUI or the terminal.
- [Odatix Explorer](/docs/gui/explorer/) — the results dashboard.
- [Commands reference](/docs/commands/) — the CLI equivalent of every page here.
