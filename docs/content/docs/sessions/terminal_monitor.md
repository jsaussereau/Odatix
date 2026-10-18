---
title: "Terminal Job Monitor"
description: "The curses Job Monitor: job list, live logs, keyboard shortcuts, mouse support and themes."
weight: 1
---

# Terminal Job Monitor

The terminal monitor is a full-screen curses interface. It is what you get by default when you launch a run without `-d`/`--detach`, and it can be re-attached to any [session](/docs/sessions/) at any time. It needs nothing more than a terminal, which makes it the easiest option on a remote machine reached over SSH.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado    # runs and attaches the monitor
$ odatix monitor               # attach to the session of the current workspace
$ odatix monitor -S nightly    # attach to a specific session of the workspace
{{< /code >}}

![Job Monitor](/images/screenshots/job-monitor.png "Job Monitor")

{{< toc >}}

## Layout

The screen is split into four horizontal areas:

- a **header** with the session ID, the Odatix version, the number of jobs allowed in parallel, the auto-pause state, and how many jobs are done, running, paused and queued. In a narrow terminal, the least useful parts are shortened or left out first (version, then the number of parallel jobs); the session, the job counts and auto-pause always stay,
- the **progress window**, listing every job with its status and progress bar,
- the **log window**, showing the output of the selected job live,
- the **help bar** at the bottom, recalling the most useful keys (`d` detach, `q` quit, `h` help menu, `c` cursor mode). While a part of a log is selected, it recalls how to copy it instead.

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
| `a` | Turn auto-pause on or off |

Changing the number of parallel jobs takes effect immediately: raising it starts queued jobs right away, lowering it lets running jobs finish before the limit applies.

Auto-pause is the [resource guard](/docs/reference/workspace/#resource-guard): while it is on, jobs are paused when the CPU or memory usage of the machine stays at its limit, and resumed once it has settled well below it. The header says where it stands — `auto-pause: on`, `on (2 paused)`, `off`, or `unavailable` when it cannot run here (`psutil` not installed, or Windows). The log of a job it acts on says so (`Job paused by resource guard: system CPU usage too high (99% CPU, 40% mem)`), which tells it apart from a pause of yours (`Job paused by user`). Turning it off resumes the jobs it had paused right away.

## Display options

| Key | Action |
|---|---|
| `+` / `-` | Grow / shrink the progress window |
| `t` | Switch theme |
| `c` | Toggle cursor mode |
| `o` | Open the selected job's work directory (when supported) |
| `y`, right-click | Copy the selected part of the log |
| `h`, `?` | Show the help menu |

> [!TIP]
> **Cursor mode** re-enables your terminal's own text selection, so you can copy a chunk of a log with the mouse. While it is on, mouse clicks go to the terminal rather than to the monitor; press `c` again to give control back to the monitor.

## Terminals without colors

With `NO_COLOR` set, the monitor shows no colors (bold and reverse video stay). A terminal that cannot hide its cursor (`TERM=vt100`) still shows it. One that cannot show it at all (`TERM=dumb`, no terminal) says so, and how to follow the jobs instead (`odatix ls`, the GUI Monitor page).

## Mouse support

The monitor is fully usable with the mouse:

- **click** a job to select it,
- **double-click** a job to open its work directory (when supported),
- **scroll** over the job list or over the log to scroll that pane,
- **drag** the separator between the two panes to resize them.

## Detaching and quitting

Detaching and quitting are two different things:

- `d` **detaches** the monitor. The session keeps running in the background; re-attach later with `odatix monitor -S <session>`.
- `q` **quits**. If jobs are still running, it asks what to do: `d` leaves them running in their session (like detaching), `k` kills them all and closes the session, `Esc` stays in the monitor. `q` never kills anything by itself.

Once the monitor is closed, the terminal keeps a line saying what happened: which session goes on and how to re-attach (`odatix monitor -S <session>`), or how many jobs succeeded and that the session was closed.

The help menu (`h`) scrolls with `Up`/`Down` when the terminal is too small to show every key.

## When everything is done

With `-E`/`--exit`, there is no popup: the monitor closes by itself once every job is over, the session is closed with it, and the command prints how many jobs succeeded and failed (see [when the jobs are done](/docs/sessions/#when-the-jobs-are-done)). Otherwise:

Once every job of the session has finished, a popup summarizes the run (`x/y job(s) succeeded, n failed`) and offers three choices:

1. **Stay in the monitor** — keep browsing the logs.
2. **Close the session and quit** — shut the session down and return to the shell (default).
3. **Keep the session open and quit** — leave the session alive so you can re-attach later.

Navigate with `Up`/`Down` then `Enter`, press the option number directly, or click it. `Esc` or `q` keeps you in the monitor.

## See also

- [Sessions & job monitor](/docs/sessions/)
- [GUI monitor](/docs/sessions/gui_monitor/)
- [Commands reference](/docs/commands/)
