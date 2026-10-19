---
title: "odatix.run"
description: "Every class, method and setting of odatix.run: checking, preparing and starting a run."
weight: 110
---
<!--
  This page is generated from the source code by docs/tools/gen_api_reference.py.
  Do not edit it by hand: edit the docstrings of odatix.run, then run
  `make api-docs`.
-->

# `odatix.run`

> [!IMPORTANT] Requires Odatix 4.0+

Every public name of **`odatix.run`**, what it does and what it takes: checking
what a run needs, preparing it, and starting it. What is run is what a
[`Workspace`](/docs/python_api/workspace/) describes, so that page is the one
that documents the configuration this one executes.

The module re-exports everything worth using, so nothing below needs to be
imported from a submodule:

{{< code lang=python filename="imports.py" >}}
from odatix.run import Run, RunError
{{< /code >}}

Running what a workspace holds.

`odatix.workspace` says what a workspace is configured to do; this is where
it gets done. A run goes through three steps, and stopping after any of them is
a normal thing to do:

```python
from odatix.workspace import Workspace
from odatix.run import Run

run = Run(Workspace.open(), "fmax_synthesis", tool="vivado")

plan = run.check()          # what would be run, and what is already done
print(plan.counts())        # {"new": 4, "cached": 2, ...}
print(plan.names("new", colored=False))

run.prepare()               # every work directory written, nothing started
run.start()                 # handed over to a session

for job in run.wait():      # back once every job of the run is over
    print(job["name"], job["status"])
```

The jobs run in a session, a background process that outlives the script:
`sessions()` lists those of the workspace, as `odatix ps` does, and a
`Session` is followed or stopped the way `odatix monitor` and
`odatix stop` do it.

Nothing here exits the interpreter: what a run cannot do raises
`RunError` (`NothingToRun`
when every job is already done or already running in a session), and what a
user should be told about comes back as messages. The command line turns both
into what it prints and into its exit code.

## `Run`

`Run(workspace, mode, options=None, reporter=None, cancel_event=None, quiet=False, **overrides)`

A run of one of the commands of a workspace.

It goes through three steps, and stopping after any of them is a normal
thing to do:

```python
run = Run(Workspace.open(), "fmax_synthesis", tool="vivado")

plan = run.check()      # what it would do, having touched nothing
run.prepare()           # every work directory written, nothing started
run.start()             # handed over to the daemon
```

Each step needs the one before it, and does it when it has not been done.

Once started, the jobs run in a session of their own, which outlives the
script: `session`, `status()` and `wait()` follow them:

```python
run.start()
jobs = run.wait()       # every job of the run over, however it ended
failed = [job["name"] for job in jobs if job["status"] != "success"]
```

**Args:**

- `workspace` *(Workspace)* — the workspace the run belongs to.
- `mode` *(str)* — what to run, one of `odatix.workspace.JOB_MODES`.
- `options` *(RunOptions)* — what this run does differently from what its settings file says. Built from the keyword arguments when not given.
- `reporter` *(Reporter)* — where what the run says is collected.
- `quiet` *(bool)* — print nothing (the control list, the progress bars): what the run says is only collected, in a `CollectingReporter`. Ignored when `reporter` is given.
- `cancel_event` *(threading.Event)* — asking the run to stop. Checking and preparing look at it between jobs, and raise `RunCancelled`.
- `**overrides` — any `RunOptions` setting, e.g. `overwrite=True`.

**Raises:**

- `TypeError` — an option is not a `RunOptions` setting. A misspelled option would otherwise be ignored, and the run would do what its settings file says instead.

| Attribute | What it is |
|---|---|
| `config` *(property)* | The run settings file of this run, as the workspace API sees it. |
| `settings_file` *(property)* | The run settings file this run reads (`options.settings_file`, or the workspace's). |
| `work_path` *(property)* | The directory the jobs of this run work in. |
| `result_path` *(property)* | Where the results go. Nothing is exported when there is none, which is what a run working outside of a workspace does. |
| `TOOL_MODES` | The runs that need an eda tool, and take the default one when not told which. |
| `was_checked` *(property)* | Whether checking has already been done, and its plan is in hand. |
| `plan` *(property)* | What the run would do (see `check()`). |
| `jobs` *(property)* | The jobs this run would run, as the objects its flow builds. |
| `session` *(property)* | The `Session` running the jobs, once `start()` handed them over. None before. |
| `followed` *(property)* | Whether `start()` followed the jobs until they were over: in the job monitor until it closed, or, when the terminal could not show it, by waiting for them ("exit_when_done"). False when the run was detached, or could not show the monitor and was not told to wait: the jobs may then still be running. |
| `tool_check_sink` | Eda tool checks handed over instead of being waited for. Left None so that the flows wait for them, which is what a run without a screen showing their progress wants. |

| Method | What it does |
|---|---|
| `path(name)` | Where one part of the workspace is, letting this run replace it. A run started from a script works on the workspace as it is configured; the command line lets a user point one of its parts elsewhere for a single run ("--archpath", "--work"), which is what the options hold. |
| `check()` | Read everything the run needs, and work out what it would do with each of its jobs, without touching anything. *Returns:* `JobPlan` — what would be run, what is already done, and what cannot be run at all. *Raises:* `RunError` — the run cannot be started at all.; `RunCancelled` — it was asked to stop. |
| `resolve_tool()` | Settle which eda tool the run uses: the one it was told, else the default tool of the workspace (see `Workspace.default_tool`), and refuse a tool Odatix does not know, saying which ones it does. |
| `checked()` | What checking produced, checking first when it has not been done. |
| `prepare()` | Write the work directory of every job: its sources, its parameters and the script that runs it. Nothing is started. *Returns:* `ParallelJobHandler` — the jobs, ready to be run. |
| `start(detach=None, session=None)` | Hand the prepared jobs over to a session, preparing them first when that has not been done. `session` is then the session that took them. *Args:* `detach` *(bool)* — return as soon as the jobs are enqueued, instead of attaching the monitor to them. A run started from a script does, unless it is told otherwise.; `session` *(str)* — the daemon session to enqueue into. |
| `status()` | Where the jobs of this run are, as its session reports them. *Returns:* `list` — one dict per job, as `Session.jobs()` gives them (`name`, `status`, `progress`...). *Raises:* `RunError` — the run has not been started.; `SessionError` — its session did not answer. |
| `wait(timeout=None, poll_interval=2.0)` | Wait until every job of this run is over, however it ends. *Args:* `timeout` *(float)* — give up after that many seconds. Forever when None.; `poll_interval` *(float)* — how often to ask the session, in seconds. *Returns:* `list` — the jobs of the run, as `status()` gives them. *Raises:* `RunError` — the run has not been started.; `SessionError` — its session did not answer.; `TimeoutError` — the jobs were not over in time. |
| `analysis_results()` | What the analyses of this run found, once its jobs are over (see `wait()`). *Returns:* `list` — AnalysisResult objects, one per job the run launched. `odatix.lib.analysis.count_by_status` counts them by verdict. |
| `execute()` | Check, prepare and start, in one call. |

## `run_job(mode, workspace=None, **overrides)`

Run one of the commands of a workspace, from beginning to end.

A shortcut for the common case:

```python
from odatix.run import run_job

run_job("fmax_synthesis", tool="vivado", overwrite=True)
```

**Args:**

- `mode` *(str)* — what to run.
- `workspace` *(Workspace)* — the workspace to run it in. The one of the current directory when not given.
- `**overrides` — any `RunOptions` setting.

**Returns:**

- `Run` — the run, once its jobs have been handed over to the daemon.

## `RunOptions`

Derives from `Settings`.

What one run does differently from what its settings file says.

Built the same way as the settings of a workspace, so a value given as text
(from a command line or a form) is read the same way here as it is there.

| Attribute | What it is |
|---|---|
| `COMMAND_DEFAULTS` | What a command does when it is not told otherwise: it asks before starting, and attaches the monitor to the jobs it starts. A script is the other way around (see the defaults above). |

| Method | What it does |
|---|---|
| `from_namespace(args, **overrides)` *(classmethod)* | The options a command line gives, as parsed by argparse. Every option of a run command lands in the setting of the same name (see odatix.components.cli_options), so this is a plain copy. What the command line leaves unset keeps the default of a command, and "--noexport" is the empty result path that exports nothing. *Args:* `args` *(argparse.Namespace)* — the parsed command line.; `**overrides` — settings the command works out itself from its own options ("--from"/"--to"/"--step" into `frequencies`, ...). |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| `tool` | `any` |  | EDA tool the jobs run with, or the tools an analysis runs. |
| `flow` | `any` |  | Flow of that tool. Its default flow when unset. |
| `targets` | `str_list` |  | Synthesis targets to run on, out of those the tool's target file enables. All of them when empty. |
| `architectures` | `str_list` |  | Architectures to run, as entries of the run settings file's "architectures". Its own list when empty. |
| `simulations` | `str_list` |  | Simulations to run, by name. Every simulation of the run settings file when empty. |
| `workflows` | `str_list` |  | Workflows to run, as entries of the run settings file's "workflows". Its own list when empty. |
| `until` | `any` |  | Last step of the flow to run, inclusive. |
| `rerun_from` | `any` |  | Step to run again, with the ones after it. |
| `overwrite` | `bool` | `False` | Run again what is already done. |
| `keep` | `bool` | `False` | Keep previous results, by timestamping the new ones. |
| `resume` | `bool` | `False` | Pick a stopped run up where it left off. |
| `nb_jobs` | `any` |  | How many jobs run at once. The settings file's own value when unset. |
| `log_size_limit` | `optional_int` |  | How many log lines the monitor keeps per job. |
| `force_single_thread` | `bool` | `False` | Ask each job to use a single thread. |
| `noask` | `bool` | `True` | Do not stop for the 'Continue?' confirmation. |
| `exit_when_done` | `bool` | `False` | Close the monitor once every job is done. |
| `detach` | `bool` | `True` | Hand the jobs over to the daemon without attaching a monitor. |
| `session` | `any` |  | Daemon session to enqueue into. |
| `session_access` | `any` |  | Who may use a session this run starts besides its owner: "user" (nobody), "group" (the group of the workspace) or "other" (every user). None is what the workspace says ("session_access" in odatix.yml). |
| `configure_session` | `bool` | `True` | Apply how this run wants the daemon to behave, on top of enqueueing its jobs. A run that is itself a job of the session it enqueues into (see odatix.dse) leaves it as it found it. |
| `debug` | `bool` | `False` | Report what reading the settings files finds. |
| `check_eda_tool` | `bool` | `True` | Check the eda tool actually runs before using it. |
| `continue_on_error` | `bool` | `False` | Keep going when a job fails. |
| `lower_bound` | `optional_int` |  | Lowest frequency of an fmax search, in MHz. |
| `upper_bound` | `optional_int` |  | Highest frequency of an fmax search, in MHz. |
| `frequencies` | `int_list` |  | Frequencies a fixed-frequency synthesis runs at, in MHz. The settings file's own when empty. |
| `source_result_types` | `any` |  | Result types a place & route starts from. |
| `from_type` | `any` |  | Result type the sources of a place & route come from. |
| `from_tool` | `any` |  | EDA tool they come from. |
| `from_flow` | `any` |  | Flow they come from. |
| `settings_file` | `any` |  | Run settings file to read, instead of the workspace's own. |
| `work_path` | `any` |  | Where the jobs run, instead of the workspace's own work directory. |
| `result_path` | `any` |  | Where the results are written. Nothing is exported when empty. |
| `arch_path` | `any` |  | Where the architectures are. |
| `sim_path` | `any` |  | Where the simulations are. |
| `workflow_path` | `any` |  | Where the workflows are. |
| `target_path` | `any` |  | Where the target files of the eda tools are. |
| `source_work_root` | `any` |  | Work directory a place & route reads its sources from. |
| `custom_metrics_file` | `any` |  | Extra metrics to read from the reports. |
| `output_filename` | `any` |  | Name of the result file, when the run writes one. |

## `JobPlan`

`JobPlan()`

The jobs a check phase found, each with its category and optional details.

Entries keep insertion order; `name` is the display name already used by the
CLI checklist, so both front-ends show the exact same wording.

Supports `len(x)`, iteration, `if x:`.

| Method | What it does |
|---|---|
| `add(name, category, **details)` | Record one job. `details` holds extra facts to display (tasks, target, ...). |
| `merge(other, suffix='')` | Append the entries of another plan, optionally suffixing their names. Used when a single run covers several eda tools: one plan per tool, one checklist for the user. |
| `names(category=None, colored=None)` | Names of the jobs of one category, in insertion order: every job when `category` is None. `colored=False` strips the terminal color codes, for anything but a terminal; by default, they are kept only when the standard output is one. |
| `counts()` | How many jobs fall in each category: `{"new": 4, "cached": 2, ...}`. |
| `run_count()` | How many jobs are actually going to be launched. |
| `sorted_entries()` | Entries by category severity, then by name. |
| `to_list()` | JSON-serializable form (dcc.Store, daemon api, ...). |
| `print_summary(noun='architectures')` | The CLI checklist: one section per non-empty category. A job resuming or running steps again says which ones ("steps: synthesis → pnr"). |

## `RunError`

`RunError(message, messages=None, code=-1)`

Derives from `Exception`.

A run cannot go on: its settings are unusable, its eda tool is missing,
there is nothing left to run...

**Attributes:**

- `messages` *(list)* — what the run reported before stopping, as `(level, text)` pairs, the last error being this exception's own message.
- `code` *(int)* — the exit code the command line uses for this.

## `NothingToRun`

`NothingToRun(message, messages=None)`

Derives from `RunError`.

Every job the run selected is already done, or already running in a
session: there is nothing left to start. Not a failure; `code` is
`NOTHING_TO_RUN`.

## `RunCancelled`

Derives from `Exception`.

The run was asked to stop while it was checking or preparing its jobs.

## `Session`

`Session(state)`

One session: the background process running the jobs a run handed over.

Get one from `sessions()`, from `Session.find()`, or from
`odatix.run.Run.session` once a run is started:

```python
from odatix.run import sessions

for session in sessions():
    print(session.id, session.counts())
```

**Args:**

- `state` *(dict)* — how to reach the session, as the session listing gives it. Not meant to be built by hand.

| Attribute | What it is |
|---|---|
| `id` *(property)* | The session id, its pid and its name (`"12345.nightly"`), as `odatix ps` shows it. |
| `name` *(property)* | The session name, what `-S` is given. |
| `pid` *(property)* | The process id of the session. |
| `workspace_root` *(property)* | The workspace the session belongs to. |
| `address` *(property)* | Where the session listens (a unix socket or host:port). |

| Method | What it does |
|---|---|
| `find(selector=None, workspace=None, any_workspace=False, any_user=False)` *(classmethod)* | The session `selector` names, as `odatix monitor -S` finds it. *Args:* `selector` *(str)* — its name, its id (`"12345.nightly"`), its pid, or the start of one of them. Without one, the only session of the workspace.; `workspace` *(Workspace or str)* — the workspace to look in. The one of the current directory when not given.; `any_workspace` *(bool)* — look in every workspace, not only this one.; `any_user` *(bool)* — look among the sessions of every user, not only yours. One of another user is only found if it is shared with you (or if you are root). *Raises:* `SessionError` — no session, or several, match. |
| `is_alive()` | Whether the session answers. |
| `status(timeout=10.0)` | What the session says of itself: how many jobs it runs at once, its resource guard, and its jobs. *Returns:* `dict` — `nb_jobs`, `resource_guard` (`enabled`, `cpu_limit`, `mem_limit`...), `counts` (see `counts()`) and `jobs` (see `jobs()`). *Raises:* `SessionError` — the session did not answer. |
| `jobs(timeout=10.0)` | The jobs of the session, in the order it received them. *Returns:* `list` — one dict per job: `id` (what `pause()`, `resume()` and `kill()` take), `name`, `status` ("queued", "running", "paused", "success", "failed", "killed", "canceled"...), `progress` (percent), `elapsed` ("HH:MM:SS") and `tmp_dir` (the job's work directory, absolute). |
| `counts(timeout=10.0)` | How many jobs are in each state. *Returns:* `dict` — `total`, `running`, `queued` (paused jobs included), `done` and `failed` (killed and canceled jobs included). |
| `is_finished(timeout=10.0)` | Whether every job of the session is over, however it ended. |
| `wait(timeout=None, poll_interval=2.0, job_ids=None)` | Wait until the jobs are over, however they end. *Args:* `timeout` *(float)* — give up after that many seconds. Forever when None.; `poll_interval` *(float)* — how often to ask the session, in seconds.; `job_ids` *(list)* — only wait for these jobs (ids from `jobs()`). *Returns:* `list` — the jobs waited for, as `jobs()` gives them. *Raises:* `SessionError` — the session is gone before the jobs are over.; `TimeoutError` — they were not over in time. |
| `pause(job_id)` | Pause a running job (an id from `jobs()`). |
| `resume(job_id)` | Resume a paused job, or start a queued or canceled one. |
| `kill(job_id)` | Kill a running or paused job, or cancel a queued one. |
| `set_jobs(nb_jobs)` | Change how many jobs run at once. |
| `set_resource_guard(enabled)` | Turn the resource guard (auto-pause on overload) on or off. |
| `stop()` | Stop the session, and the jobs still running in it, as `odatix stop` does. *Returns:* `bool` — whether the session is confirmed gone. |

## `sessions(workspace=None, any_workspace=False, any_user=False)`

The sessions running jobs, as `odatix ps` lists them.

**Args:**

- `workspace` *(Workspace or str)* — the workspace whose sessions to list. The one of the current directory when not given.
- `any_workspace` *(bool)* — list the sessions of every workspace.
- `any_user` *(bool)* — list the sessions of every user, not only yours, including those not shared with you (which cannot be used).

**Returns:**

- `list` — `Session` objects.

## `SessionError`

Derives from `RuntimeError`.

A session cannot be found, reached or told something.

## `export_results(workspace, result_type='all', tool='all', quiet=False)`

Export the results of the work directory again, as `odatix results
<result_type>` does, or only apply the derived metrics (`"derived"`).

Exporting is what turns the reports a job left in its work directory into
the results files Odatix Explorer reads. Runs do it themselves; exporting
again is for after a metric definition changed. Every export but
`"analysis"` and `"derived"` writes a results file from scratch, and
applies the derived metrics again right after.

**Args:**

- `workspace` *(Workspace)* — the workspace whose results to export.
- `result_type` *(str)* — one of `RESULT_TYPES`.
- `tool` *(str)* — for "all" and "synth", the eda tool whose results to export ("all" for every one of them); for "analysis", the tool whose analyses to report.
- `quiet` *(bool)* — print nothing; what the export said is still in the report.

**Returns:**

- `ExportReport` — how it went. It is false when an error was reported, even if the export went on with the rest: a metric that cannot be read is a definition to fix.

**Raises:**

- `ValueError` — for an unknown result type.

## `ExportReport`

`ExportReport(result_type, ok, messages=None, output=None)`

How an export went.

True when it went through without a single error, so that
`if export_results(ws):` reads as expected.

**Attributes:**

- `result_type` *(str)* — what was exported (see `RESULT_TYPES`).
- `ok` *(bool)* — whether it went through without reporting any error.
- `messages` *(list)* — what it reported, as `(level, text)` pairs (level being "error", "warning", "note" or "tip").
- `output` *(list)* — every line it printed, without color codes.

Supports `if x:`.

| Method | What it does |
|---|---|
| `errors()` | Only what was reported as an error. |
| `warnings()` | Only what was reported as a warning. |
| `summary()` | The last line the export printed that is not a diagnostic ("Derived metrics updated in 1 results file"), or "" when it printed none. |

## `Reporter`

`Reporter()`

Collects what a run reports, keeping it printed as it always was.

Everything Odatix reports goes through `odatix.lib.printc`, so this
listens there rather than asking the run flows to report differently.

Supports `len(x)`, iteration.

| Attribute | What it is |
|---|---|
| `errors` *(property)* | The error messages, in order. |
| `warnings` *(property)* | The warning messages, in order. |

| Method | What it does |
|---|---|
| `listening()` | Collect everything reported inside the context. |
| `of_level(level)` | The messages of one level (`"error"`, `"warning"`, `"note"`...), in order. |
| `last_error()` | The last error message, or None. |
| `clear()` | Forget what was collected; returns the reporter. |

## `TerminalReporter`

Derives from `Reporter`.

What the command line uses: printed as it happens, and kept.

## `CollectingReporter`

Derives from `Reporter`.

Kept and not printed: what a script or a server wants, so that a run does
not write to a standard output nobody is reading.

| Method | What it does |
|---|---|
| `listening()` | Collect everything reported inside the context. |

---

## See also

- [`odatix.workspace`](/docs/python_api/workspace/) — the configuration a run executes.
- [Python API overview](/docs/python_api/) — the same API, told as a story.
- [Configuration file reference](/docs/reference/) — every file, every key.
- [Commands reference](/docs/commands/) — every command and its options.
