---
title: "GUI Job Monitor"
description: "The browser Job Monitor: session picker, live stats, task filtering and sorting, layout modes and live logs."
weight: 2
---

# GUI Job Monitor

> [!IMPORTANT] Requires Odatix 4.0+

The GUI monitor is the Job Monitor page of [the Odatix GUI](/docs/gui/app/). It shows exactly the same [sessions](/docs/sessions/) and jobs as the terminal monitor — both talk to the same session daemons — with a richer view: live counters, filtering, sorting and adjustable layouts.

{{< toc >}}

## Opening the monitor

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

Open the GUI, click the **Monitor Jobs** card (or **Monitor** in the top bar). The page shows the latest session of the workspace the GUI runs in. While it loads, it says so (*Looking for sessions…*, *Loading session…*) instead of showing empty counters. When the workspace has no session, it says *No session in this workspace* and offers **Run jobs**; the sessions of other workspaces stay in the list, to pick explicitly.

> [!TIP]
> You can also launch `odatix-gui` directly on the monitor page and on a specific session.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui monitor # Start the GUI on the monitor page
$ odatix-gui monitor -S my_session # Start the GUI on the monitor page of the session my_session
$ odatix-gui monitor --daemon-host myhost --daemon-port 8000 # Monitor a session API at an explicit endpoint
{{< /code >}}

`-p` sets the port of the GUI itself, not the one of a session. The other options of `odatix-gui` (`--normal-term-mode`, `--safe-mode`, `--read-only`) work on this page too.

> [!NOTE]
> If you run `odatix-gui` on a remote server, see [Hosting on a server](/docs/gui/host_server/) for instructions to access it over the network.

## Toolbar

The top bar of the page carries everything that applies to the whole session:

- the **session dropdown**, listing every active session; switching sessions reloads the whole view. The sessions of the workspace the GUI runs in come first, latest first, and the latest of them is the one shown when none is named. The sessions of other workspaces follow under an **Other workspaces** heading, each with its workspace (`1234.nightly — ~/other_project`, or its last folders when the path is long; the full path is in the hover text). A session of another workspace is never selected by default. Typing in the list searches the session names and the workspace paths,
- the **Parallel** control (`−` / `+`), which changes how many jobs the daemon runs at the same time — the change takes effect immediately,
- the **Auto-pause** switch, which turns the [resource guard](/docs/reference/workspace/#resource-guard) of the session on or off. While it is on, jobs are paused when the CPU or memory usage of the machine reaches its limit; its tooltip shows the limits and the current load, and the switch shows how many jobs it has paused. Turning it off resumes them right away. It reads *N/A* when the guard cannot run on the machine of the session (`psutil` not installed, or Windows),
- the **layout mode** buttons (see [below](#layout-modes)),
- the **kill-all** button (✖), which kills every task and closes the session, once you have confirmed it: the dialog says how many jobs will be killed or canceled, and in which session (and workspace, when it is another one). Once the session is closed, a line under the counters says so, and the page moves on to another session of the workspace, or shows *No session in this workspace*.

When the selected session cannot be shown (it was stopped, or never existed), the toolbar and the session list stay, with a message and two ways out: **Run jobs** and **Back to home**. Pick another session in the list to get back to the dashboard.

Below the toolbar, a row of live counters shows **Total**, **Running**, **Paused**, **Queued**, **Done** and **Failed** jobs, next to an **Overall** progress bar for the session as a whole. **Paused** counts the jobs paused by you or by auto-pause, **Queued** the ones that have not started, **Running** includes the jobs exporting their results, and **Failed** the killed and canceled ones; the filters below group them the same way. On a shared machine, auto-pause can hold a job because of the load of other users: the status of a paused job then says for how long, when the session reports it.

## Layout modes

Four modes decide how the task list and the log share the page:

| Mode | Description |
|---|---|
| **Split** | Task list and log side by side (default) |
| **Stacked** | Task list above, log below |
| **Tasks** | Task list only |
| **Log** | Log only |

In Split and Stacked mode, the divider between the two panels can be dragged to resize them.

## Task list

Each task is a row showing its status dot, name, progress bar and percentage, runtime, and status label. When a name does not fit, its first part (the architecture or the workflow) is shortened first, so that the configuration and frequency that tell the jobs apart stay visible; hovering the row shows the full name, target and directory. When the jobs run on several targets, the row also shows its target. Click a row to select it — the log panel follows the selection.

Every row carries its own controls, shown according to the task's state:

- **Start / resume** the task,
- **Pause** the task,
- **Kill** the task (or cancel it, if still queued).

### Filtering and sorting

The panel header offers a filter — **All**, **Running**, **Paused**, **Queued**, **Done**, **Failed** — to narrow the list down to what you care about, which is useful on sessions with hundreds of jobs.

Tasks can be sorted by **Default** (enqueue order), **Name**, **Status**, **Progress** or **Runtime**, and the button next to the dropdown reverses the order.

## Log panel

The log panel streams the output of the selected task live, with the tool's colors preserved (adjusted to stay readable on light and dark themes) and the formatting rules of the tool's `tool.yml` applied. Its header shows the selected task, and the **Open task directory** button opens that job's work directory in your file browser (only when the daemon runs on the same machine as your browser).

The log area is focusable, so `Home`, `End` and `PageUp`/`PageDown` scroll the log rather than the page.

## When everything is done

When the last job of the session finishes, a popup summarizes the run and offers these ways out. After an [RTL analysis](/docs/features/analysis/), it gives the verdicts of the analyses (failed, warnings, passed...) rather than the job statuses, which only say whether the tool ran, and its buttons open the **RTL analysis** dashboard of the Explorer instead of its home page:

1. **Close session and open Explorer** — shut the session down and jump straight to the results (default).
2. **Keep session and open Explorer** — go to the results while leaving the session alive.
3. **Close session only** — shut the session down and go back to the home page of the GUI.
4. **✖** (top right) — close the popup and stay in the monitor, to keep browsing the logs.

## Monitoring a remote daemon

The monitor page reads its target from the URL, which lets you point it at a specific session or at a daemon running elsewhere:

- `?session=<name>` (or `?S=<name>`) — select a session, matching a full session ID, a name, or a unique name prefix,
- `?host=<host>&port=<port>` — connect to a daemon API at an explicit endpoint.

This is what `odatix-gui monitor -S my_session` produces under the hood.

## See also

- [Sessions & job monitor](/docs/sessions/)
- [Terminal monitor](/docs/sessions/terminal_monitor/)
- [The Odatix GUI](/docs/gui/app/)
- [Hosting on a server](/docs/gui/host_server/)
