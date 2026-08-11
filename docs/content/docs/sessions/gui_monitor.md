---
title: "GUI Job Monitor"
description: "The browser Job Monitor: session picker, live stats, task filtering and sorting, layout modes and live logs."
weight: 2
---

# GUI Job Monitor

> [!IMPORTANT] Requires Odatix 4.0+

The GUI monitor is the Job Monitor page of [the Odatix GUI](/docs/gui/app/). It shows exactly the same [sessions](/docs/sessions/) and jobs as the terminal monitor — there is a single daemon behind both — with a richer view: live counters, filtering, sorting and adjustable layouts.

{{< toc >}}

## Opening the monitor

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

Open the GUI, click the **Monitor Jobs** card (or **Monitor** in the top bar), and pick a session from the list.

> [!TIP]
> You can also launch `odatix-gui` directly on the monitor page and on a specific session.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui monitor # Start the GUI on the monitor page
$ odatix-gui monitor -S my_session # Start the GUI on the monitor page of the session my_session
{{< /code >}}

> [!NOTE]
> If you run `odatix-gui` on a remote server, see [Hosting on a server](/docs/gui/host_server/) for instructions to access it over the network.

## Toolbar

The top bar of the page carries everything that applies to the whole session:

- the **session dropdown**, listing every active session; switching sessions reloads the whole view,
- the **Parallel** control (`−` / `+`), which changes how many jobs the daemon runs at the same time — the change takes effect immediately,
- the **layout mode** buttons (see [below](#layout-modes)),
- the **kill-all** button, which kills every task and exits the session.

Below the toolbar, a row of live counters shows **Total**, **Running**, **Queued**, **Done** and **Failed** jobs, next to an **Overall** progress bar for the session as a whole.

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

Each task is a row showing its status dot, name, progress bar and percentage, runtime, and status label. Click a row to select it — the log panel follows the selection.

Every row carries its own controls, shown according to the task's state:

- **Start / resume** the task,
- **Pause** the task,
- **Kill** the task (or cancel it, if still queued).

### Filtering and sorting

The panel header offers a filter — **All**, **Running**, **Queued**, **Done**, **Failed** — to narrow the list down to what you care about, which is useful on sessions with hundreds of jobs.

Tasks can be sorted by **Default** (enqueue order), **Name**, **Status**, **Progress** or **Runtime**, and the button next to the dropdown reverses the order.

## Log panel

The log panel streams the output of the selected task live, with the tool's colors preserved and the formatting rules of the tool's `tool.yml` applied. Its header shows the selected task, and the **Open task directory** button opens that job's work directory in your file browser (only when the daemon runs on the same machine as your browser).

The log area is focusable, so `Home`, `End` and `PageUp`/`PageDown` scroll the log rather than the page.

## When everything is done

When the last job of the session finishes, a popup summarizes the run and offers three ways out:

1. **Close session and open Explorer** — shut the session down and jump straight to the results (default).
2. **Keep session and open Explorer** — go to the results while leaving the session alive.
3. **Stay in the monitor** — keep browsing the logs.

## Monitoring a remote daemon

The monitor page reads its target from the URL, which lets you point it at a specific session or at a daemon running elsewhere:

- `?session=<name>` (or `?S=<name>`) — select a session, matching a full session ID, a name, or a unique name prefix,
- `?host=<host>&port=<port>` — connect to a daemon API at an explicit endpoint.

This is what `odatix-gui monitor -S my_session` produces under the hood.

## See also

- [Sessions & Job Monitor](/docs/sessions/)
- [Terminal monitor](/docs/sessions/terminal_monitor/)
- [The Odatix GUI](/docs/gui/app/)
- [Hosting on a server](/docs/gui/host_server/)
