---
title: "Terminal Job Monitor"
description: "The curses Job Monitor: job list, live logs, keyboard shortcuts, mouse support and themes."
weight: 1
---

# Terminal Job Monitor

The terminal monitor is a full-screen curses interface. It is what you get by default when you launch a run without `-d`/`--detach`, and it can be re-attached to any [session](/docs/sessions/) at any time. It needs nothing more than a terminal, which makes it the easiest option on a remote machine reached over SSH.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado    # runs and attaches the monitor
$ odatix monitor               # attach to the current workspace session
$ odatix monitor -S nightly    # attach to a specific session
{{< /code >}}

![Job Monitor](/images/screenshots/job-monitor.png "Job Monitor")

{{< toc >}}

## Layout

The screen is split into four horizontal areas:

- a **header** with the session and the global run status,
- the **progress window**, listing every job with its status and progress bar,
- the **log window**, showing the output of the selected job live,
- the **help bar** at the bottom, recalling the most useful keys (`d` detach, `q` quit, `h` help menu, `c` cursor mode).

The separator between the progress window and the log window can be dragged with the mouse, or moved with `+` and `-`, to give more room to whichever half you are watching.

## Selecting and reading jobs

Move the selection with `PageUp`/`PageDown` (or `p`/`n`), or click a job directly. The log window follows the selection and shows the job's output as it is produced, with the tool's own colors preserved.

| Key | Action |
|---|---|
| `PageDown`, `n` | Select next job |
| `PageUp`, `p` | Select previous job |
| `Up` / `Down` | Scroll the log up / down |
| `Left` / `Right` | Scroll the log horizontally (long lines) |
| `Home` / `End` | Jump to the top / bottom of the log |

Scrolling up disables autoscroll so the view stops jumping while you read; `End` re-enables it and returns to the live tail.

## Controlling jobs

| Key | Action |
|---|---|
| `Space` | Pause the selected job |
| `s` | Start or resume the selected job |
| `k` | Kill (or cancel, if still queued) the selected job |
| `>` , `.` | Allow one more job in parallel |
| `<` , `,` | Allow one fewer job in parallel |

Changing the number of parallel jobs takes effect immediately: raising it starts queued jobs right away, lowering it lets running jobs finish before the limit applies.

## Display options

| Key | Action |
|---|---|
| `+` / `-` | Grow / shrink the progress window |
| `t` | Switch theme |
| `c` | Toggle cursor mode |
| `o` | Open the selected job's work directory (when supported) |
| `h`, `?` | Show the help menu |

> [!TIP]
> **Cursor mode** re-enables your terminal's own text selection, so you can copy a chunk of a log with the mouse. While it is on, mouse clicks go to the terminal rather than to the monitor; press `c` again to give control back to the monitor.

## Mouse support

The monitor is fully usable with the mouse:

- **click** a job to select it,
- **double-click** a job to open its work directory (when supported),
- **scroll** over the job list or over the log to scroll that pane,
- **drag** the separator between the two panes to resize them.

## Detaching and quitting

Detaching and quitting are two different things:

- `d` **detaches** the monitor. The session keeps running in the background; re-attach later with `odatix monitor -S <session>`.
- `q` **quits**. If jobs are still running, Odatix asks for confirmation (`Kill all jobs and stop daemon: Yes (y) / No (n)?`) before killing them and stopping the daemon.

## When everything is done

Once every job of the session has finished, a popup summarizes the run (`x/y job(s) finished`) and offers three choices:

1. **Stay in the monitor** — keep browsing the logs.
2. **Close the session and quit** — shut the session down and return to the shell (default).
3. **Keep the session open and quit** — leave the session alive so you can re-attach later.

Navigate with `Up`/`Down` then `Enter`, press the option number directly, or click it. `Esc` or `q` keeps you in the monitor.

## See also

- [Sessions & Job Monitor](/docs/sessions/)
- [GUI monitor](/docs/sessions/gui_monitor/)
- [Commands reference](/docs/commands/)
