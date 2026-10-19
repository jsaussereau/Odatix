---
title: "Workspace Settings (odatix.yml)"
description: "Every key of odatix.yml: where an Odatix workspace keeps its designs, its work directories, its results and its settings files."
weight: 1
---

# `odatix.yml`

`odatix.yml` sits at the root of a workspace and answers one question: **where
does everything live**. Every key is optional — a workspace whose `odatix.yml`
is empty uses the defaults below. `odatix init` writes every key commented out
at its default, plus `workspace: odatix` and `default_tool: vivado`.

Use `-c/--config` on any command to read a different file, which is how several
workspace layouts can share one directory.

{{< toc >}}

## Workspace

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `workspace` | string | `odatix` | Marks the directory as an Odatix workspace. `odatix init` writes it; nothing else reads its value. |

## Default tool

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_tool` | string | *(none)* | The eda tool `odatix fmax`, `odatix synth` and `odatix analyze` run when `-t/--tool` names none. `odatix init` sets it to `vivado`. |

Without it, a workspace that has a target file for a single tool runs that
tool; any other is told to name one, with the list of the tools it has a target
file for. An analysis whose settings file lists `tools` runs those instead.

## Work directories

Jobs run in `<work_path>/<job type path>/<tool>[@<flow>]/<target>/<design>/<config>[/<freq>MHz]/`:
`@<flow>` is added for a flow other than the tool's default one, and
`<freq>MHz` for a fixed-frequency synthesis.
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
| `gui_theme_path` | path | `odatix_userconfig/themes/gui` | Where workspace [GUI themes](/docs/gui/themes/) live. |

> [!NOTE]
> A `target_<tool>.yml` not found in `target_path` is also looked up directly in
> `odatix_userconfig/`, so workspaces created before `target_path` defaulted to
> `odatix_userconfig/targets` keep working unchanged.

## Settings files

Each run command reads one settings file; these keys say which.

| Key | Type | Default | Read by |
|-----|------|---------|---------|
| `fmax_settings_file` | path | `odatix_userconfig/fmax_settings.yml` | `odatix fmax` |
| `synth_settings_file` | path | `odatix_userconfig/synth_settings.yml` | `odatix synth` |
| `analyze_settings_file` | path | `odatix_userconfig/analyze_settings.yml` | `odatix analyze` |
| `sim_settings_file` | path | `odatix_userconfig/sim_settings.yml` | `odatix sim` |
| `workflow_settings_file` | path | `odatix_userconfig/workflow_settings.yml` | `odatix workflow` |
| `pnr_settings_file` | path | `odatix_userconfig/pnr_settings.yml` | `odatix pnr` |
| `clean_settings_file` | path | `odatix_userconfig/clean_settings.yml` | `odatix clean` |
| `dse_settings_file` | path | `odatix_userconfig/dse_settings.yml` | `odatix dse` |
| `derived_metrics_file` | path | `odatix_userconfig/derived_metrics.yml` | The end of every run, `odatix results` and `odatix results derived` |

Every one of them is also overridable per run with `-i/--input` (`--config` for
the workspace file itself).

> [!NOTE]
> A settings file is named after the command that reads it. The former names
> are still read for one version: the keys `fmax_synthesis_settings_file`,
> `custom_freq_synthesis_settings_file`, `simulation_settings_file` and
> `analysis_settings_file` (with a warning), and the files
> `fmax_synthesis_settings.yml`, `custom_freq_synthesis_settings.yml`,
> `simulations_settings.yml`, `analysis_settings.yml` and `clean.yml` when the
> file of the current name does not exist. `odatix migrate` rewrites the keys
> and renames the files.

## Results and export

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `result_path` | path | `results` | Where exported result files are written. |
| `dse_campaign_path` | path | `odatix_userconfig/dse_campaigns` | Where the [exploration campaigns](/docs/reference/dse/) are kept. |

`use_benchmark` and `benchmark_file` are no longer read: a benchmark score is a
[simulation metric](/docs/results/metrics/).

See [Results & export](/docs/results/) for what lands there.

## Resource guard

While jobs run, Odatix watches the load of the machine, every 2 seconds. When
the CPU or memory usage stays at its limit for two samples in a row, it pauses
the most recently started job, and goes on pausing one job at a time while the
overload lasts. It resumes the jobs it paused, one at a time, once the usage has
stayed 5 points below the limit for three samples in a row, and never less than
30 seconds after pausing them: resuming sooner would hand the machine back the
very load that got them paused. The log of the job says what happened
(`Job paused by resource guard: system CPU usage too high (99% CPU, 40% mem)`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `resource_guard` | bool | `true` | Pause running jobs while the machine is overloaded. |
| `cpu_limit` | number | `98` | CPU usage (%) at which a job is paused. |
| `mem_limit` | number | `98` | Memory usage (%) at which a job is paused. |

These values apply to every run started afterwards, from the command line, the
GUI or the [Python API](/docs/python_api/), including runs that add jobs to a
running session with `-S`. To switch the guard on a running session, use the **Auto-pause** switch of the [web monitor](/docs/sessions/gui_monitor/)
or the `a` key of the [terminal monitor](/docs/sessions/terminal_monitor/): turning it off resumes
the jobs it had paused right away.

> [!NOTE]
> The guard relies on `psutil`, installed with Odatix, and does nothing on
> Windows. Both monitors say so when it cannot run.

## Sessions

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `session_access` | `user`, `group` or `other` | `user` | Who may use the sessions started in this workspace besides their owner. |

A session is private to the user who starts it. With `group`, the members of
the group of the workspace directory may use it too, and with `other`, every
user of the machine: they monitor it, add, pause or kill its jobs, and stop it.
Using a session is running commands as its owner, so share it only with people
you trust. `--session-access` on a run command overrides this key for the
session that run starts. See
[sessions of other users](/docs/sessions/#sessions-of-other-users).

## WSL (Windows)

On Windows, an EDA tool or a simulator installed in
[WSL](https://learn.microsoft.com/en-us/windows/wsl/install), the Windows
Subsystem for Linux, runs there: Genus, Innovus or Quartus installed in a Linux
distribution, a Verilator simulation, which needs `make` and a C++ compiler.

**What runs where.** Only the command of a job runs in WSL: the tool, or the
simulation. Odatix itself always runs on Windows: it prepares the jobs, runs the
session and the monitor, generates the RTL a job needs, and reads and exports
the results, from the work directory of Windows the job wrote them in.

**Who decides.** The workspace, with these keys. A name in `wsl_tools` or
`windows_tools` is that of an EDA tool, of a simulation, or of the
[template](/docs/reference/simulation/#templates) a simulation starts from
(`verilator` covers every simulation starting from that template, and the
Verilator of RTL analysis).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `wsl` | `auto` or `never` | `auto` | Whether Odatix may run anything in WSL. `never`: nothing runs there. |
| `wsl_distribution` | string | the default distribution | The distribution tools and simulators run in, as `wsl -l` names it. |
| `wsl_tools` | list of names | `[]` | Tools and simulations that always run in WSL. |
| `windows_tools` | list of names | `[]` | Tools and simulations that always run on Windows, never in WSL. |

For what neither list names, `wsl: auto` lets Odatix choose, when WSL is
installed:

- an EDA tool runs in WSL when its [`tool.yml`](/docs/reference/tools/) only
  has Linux commands (a `unix` section, no `windows` one);
- a simulation runs in WSL when its simulator (the program of its
  `test_command`) is not installed on Windows but is in WSL.

**Said before anything runs.** When a run is checked, Odatix says where each
tool and each simulation runs:

{{< code lang=text filename="Terminal" >}}
[odatix sim] note: "TB_Example_Cordic_Verilator" runs in WSL (Ubuntu)
[odatix sim] note: "TB_Example_Cordic_GHDL" runs on Windows
{{< /code >}}

The **Tools** page of the GUI says it on the badge of each tool and simulator
("installed in WSL (Ubuntu)").

**What a command run in WSL is given.** The paths of the job as WSL sees them
(`/mnt/c/...`): `$work_path`, `$script_path` and the other
[variables](/docs/reference/tools/) of `tool.yml`, `${work_path}` and the other
[placeholders](/docs/reference/simulation/#what-odatix-tells-the-simulation) of
a simulation, and the paths Odatix writes in the scripts of the job. `$python`
and `${python}` are the `python3` of the distribution. A simulation runs the
implementation of its tasks for `linux` (see `platforms`). The command runs in
a login shell, so it finds the tools the profile of the user puts in the `PATH`
(`~/.bashrc`, `~/.profile`).

> [!NOTE]
> The simulation templates of Odatix run a Python script, which needs PyYAML in
> the distribution: `sudo apt install python3-yaml`, or
> `sudo dnf install python3-pyyaml`. A run checks it, and says so when it is
> missing.

These keys have no effect on Linux and macOS.

{{< code lang=yaml filename="odatix.yml" >}}
# Genus, Innovus and Verilator are installed in the "Ubuntu" distribution, and
# so is a Vivado: run it there rather than the one of Windows. GHDL is
# installed on both: keep it on Windows.
wsl_distribution: Ubuntu
wsl_tools: [vivado]
windows_tools: [ghdl]
{{< /code >}}

## Example

{{< code lang=yaml filename="odatix.yml" >}}
# Keep the sources of the workspace in a shared directory, and the (large)
# work directories on a fast local disk.
arch_path:   ../shared/architectures
target_path: ../shared/targets
work_path:   /scratch/odatix_work
result_path: results

default_tool: genus
{{< /code >}}

## In the GUI

**Workspace Settings** (`/workspace`) edits this file directly — every key
above has a field (except the `workspace` marker), grouped as in the file:
Tools, Main paths, Settings files, Work directories, Results, Resource
guard, Sessions and WSL (Windows). A field left empty means the default shown in it; saving writes only
what changed in `odatix.yml`, and a key emptied is removed from it. See
[The Odatix GUI](/docs/gui/app/).

## See also

- [Run settings files](/docs/reference/run_settings/) — what each command actually runs.
- [Commands reference](/docs/commands/) — `-c/--config` and the other path options.
