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
| **RTL architectures** | Configure your designs, their configurations and their simulations. |
| **Tools** | Add and configure the EDA tools of the workspace. |
| **Run jobs** | Launch workflows, RTL analysis, synthesis, design space explorations, place & route. |
| **Monitor Jobs** | Follow the jobs currently running. |
| **Explore Results** | Open Odatix Explorer on the exported results. |
| **Workspace Settings** | Paths, settings files, and the workspace layout. |
| **Documentation** | This documentation. |

The same destinations are always one hover away in the top bar, grouped under **Configure**, **Run**, **Monitor**, **Explorer** and **Workspace** (clean, derived metrics, settings).

If you start the GUI in a directory that is not a workspace yet, it offers to create one — empty, or preloaded with the examples.

## Configuring a workspace

| Page | What it edits |
|------|---------------|
| **RTL architectures** (`/architectures`) | Your designs: sources, top level, clock and reset, parameter delimiters, per-tool/target/configuration overrides, and the combinations of its parameter domains left out of its design space ([exclusions](/docs/configurations/exclusions/#in-the-graphical-interface)). Each design lists its configurations, with an editor for each parameter file, and the rules its parameter domains describe them with. |
| **Simulations** (`/architectures#simulations`) | The testbenches of the workspace and their `_settings.yml`. |
| **Workflows** (`/workflows`) | Workflow definitions: tasks, dependencies, variables, and the metrics they export. |
| **Tools** (`/tools`) | The tools of the workspace and, apart, the built-in ones. Create, duplicate, edit flows and steps, edit metrics. |
| **Derived Metrics** (`/derived_metrics`) | The workspace `derived_metrics.yml` — groups and derived metric definitions. |
| **Workspace Settings** (`/workspace`) | Where everything lives: settings files, work and result directories. |
| **Clean** (`/clean`) | What `odatix clean` removes from the workspace, and the button that runs it. |

Two editors are worth knowing by name because they save real work:

- The **Configuration rules** panel of each parameter domain describes a whole set of configurations with a rule — ranges, powers of two, lists, functions — instead of writing them one by one. What the rule produces appears straight away among the configurations of the domain, without anything being written to disk. See [Configuration generation](/docs/configurations/config_generation/).
- The **Metrics editors** build `metrics.yml` and `_metrics.yml` entries with the extraction type, file and pattern in a form. See [Base metrics](/docs/results/metrics/).

A **save** button in the header turns to a warning colour as soon as something is unsaved, so you always know whether what you see is on disk.

## Launching jobs

**Run jobs** walks you through the same choices the command line takes as options:

{{< code lang=text filename="Run a job" >}}
 Job type ──► EDA tool ──► flow / step ──► targets ──► job settings ──► Run
{{< /code >}}

1. **Job type** — workflow, simulation, RTL analysis, fmax synthesis, fixed-frequency synthesis, design space exploration (see [below](#design-space-exploration)), or place & route.
2. **EDA tool** (synthesis, analysis and place & route only) — each tool's card shows its flows as buttons and, when a flow is split into steps, its steps as "run up to here" buttons. Every one of them leads straight to the job settings, so a run stays one click away whatever the tool offers. For an RTL analysis, the flow clicked is the one of that tool; the job settings then let you tick more tools, which run their default flow.
3. **Targets** — the FPGA devices or technologies to run on.
4. **Job settings** — which designs and configurations to run, frequency range or list, parallel jobs, overwrite. These are the same values as the settings files, and **Save all** writes only what you changed to those files. The strip under the title sums up the run: job type, tool, flow, the step it stops at, the number of designs and configurations selected. Turning a design on selects all its configurations, its default configuration only when it has no other. **Override frequencies** off means each architecture keeps its own frequencies: the note under the switch says what the fields below are used for. For a flow split into steps, **Re-run from** picks the first step to do again, with the ones after it, even where the jobs have already done it (`--rerun-from`): what this one run does, so it is not saved.
5. **Session** — the list in the header offers **New session...** and the sessions of this workspace, by name and uptime.

Selection pages act immediately: clicking a tool, a flow or a step navigates on, there is no intermediate confirmation screen.

**Run jobs** runs what the page shows, saved or not, from a temporary copy of the settings. Its window first shows **Checking settings...**, then **Ready to run**, **Nothing to run** or **Cannot run**, under a line that says what the run uses: tool, flow, last step, targets and work directory. The plan lists the jobs that will run and the ones that won't, with the reason on each card; **Start** is only available when there is something to run. The back arrow next to the title returns to the tool choice (or the job type choice).

Launching enqueues the jobs into the daemon exactly like the CLI does, and drops you on the Monitor. A run started from the GUI can be followed from a terminal with `odatix monitor`, and vice versa — there is one daemon, not one per interface.

### Design space exploration

**Run jobs → Design space exploration** (`/dse`) is `odatix dse` in a page. It lists the campaigns of the workspace as cards: the switch on a card selects it for the next exploration, **Edit** opens it, and **New campaign** writes a new one. The exploration settings above the cards are `dse_settings.yml`. **Explore** checks the selected campaigns, shows what each one will spend, and starts on **Start** in the session chosen in the header; **New session...** starts a new one every time.

The campaign editor (`/dse_campaign?campaign=<name>`) edits one file of `dse_campaigns/`: what runs a design, its frequencies, the objectives and the constraints, the search, and the architectures. See [Design space exploration](/docs/reference/dse/#from-the-gui).

## Monitoring and exploring

- **Monitor** (`/monitor`) — the graphical Job Monitor: live progress, per-job logs, and the list of daemon sessions. See [Job Monitor & sessions](/docs/sessions/).
- **Explorer** (`/explorer`) — the results dashboard, reachable from the same interface, with its chart pages listed in the top bar, the RTL analysis dashboard (`/explorer/analysis`) and the follow-up of the design space explorations (`/explorer/dse`). See [Odatix Explorer](/docs/gui/explorer/).

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
| `-p`, `--port` | HTTP port. A port given with `-p` must be free: if it is taken, the GUI stops with an error instead of moving elsewhere. Without `-p`, it takes 8052, or the next free port, and prints the address it took. |
| `-B`, `--nobrowser` | Do not open the browser automatically. |
| `-T`, `--theme` | Default theme for browsers without a saved choice; a theme picked in the GUI is kept by that browser. |
| `-N`, `--normal_term_mode` | Do not switch terminal mode. |
| `--safe_mode` | Keep running on internal errors. |
| `-c`, `--config` | Alternate workspace settings file (default `odatix.yml`). |

### Open a given page

A page name after `odatix-gui` opens that page instead of the home page, with
its own options (`odatix-gui -h` lists them all, `odatix-gui <page> -h` the
options of one):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui monitor -S my_session
$ odatix-gui run_jobs --type custom_freq_synthesis --tool vivado
$ odatix-gui tool_editor --tool vivado
$ odatix-gui derived_metrics
{{< /code >}}

The pages are `home`, `monitor`, `jobs`, `run_jobs`, `eda_tool`,
`select_targets`, `architectures`, `arch_editor`, `config_editor`, `workflows`,
`workflow_editor`, `tools`, `tool_editor`, `sim_editor`, `metric_editor`,
`derived_metrics`, `clean` and `workspace`. Global options go before the page
name.

Running it on a remote machine — a build server, a licence server — works the same way, see [Hosting on a server](/docs/gui/host_server/).

## See also

- [Job Monitor & sessions](/docs/sessions/) — following jobs, from the GUI or the terminal.
- [Odatix Explorer](/docs/gui/explorer/) — the results dashboard.
- [Commands reference](/docs/commands/) — the CLI equivalent of every page here.
