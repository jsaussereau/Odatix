---
title: "Sessions & Job Monitor"
description: "Track parallel synthesis, simulation and workflow jobs in real time, and manage detached daemon sessions."
weight: 8
---

# Sessions & Job Monitor

> [!IMPORTANT] Requires Odatix 4.0+

Odatix runs `fmax`, `synth`, `sim` and `workflow` through a background **daemon**. Jobs are enqueued into a **session**, then monitored either immediately (default) or later (detached mode). A [**Job Monitor**](/docs/sessions/#two-equivalent-monitors) shows every job's progress and logs live, and lets you start, pause, resume or kill jobs at any time.

{{< toc >}}

## Sessions

A session is a set of jobs handed over to the daemon by a single run command. The daemon owns the session: it schedules the jobs, runs a limited number of them in parallel, and keeps them alive whether or not a monitor is attached. Closing a monitor does not stop the jobs — only [stopping the session](#stop-sessions) does.

Each session has an ID of the form `<pid>.<name>` (e.g. `12345.nightly`), and can be attached, detached and re-attached freely, from the terminal or from the browser.

### Default behavior

Without `-d`/`--detach`, a run command enqueues its jobs in a new session and immediately attaches the terminal Job Monitor:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado
{{< /code >}}

### Detached sessions

Use detached mode with `-d`/`--detach` to start jobs and return to the shell immediately.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -d
{{< /code >}}

### Session naming

When using a run command, you can give the session a meaningful name with `-S`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -d -S nightly
{{< /code >}}

The same pattern applies to `odatix synth`, `odatix sim` and `odatix workflow` commands.

### Inspect and attach

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ls                 # list active sessions
$ odatix ls -S nightly      # filter with a selector
$ odatix monitor -S nightly # re-attach the monitor to a session
{{< /code >}}

### Session selectors

The `-S`/`--session` selector can match a full session ID (e.g. `12345.nightly`), a session name, a name prefix, or a PID. If several sessions match, Odatix asks you to refine the selector.

### Stop sessions

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix stop -S nightly    # stop one session
$ odatix stop --all         # stop every session
{{< /code >}}

## Two equivalent monitors

Odatix ships **two Job Monitors**, and they are interchangeable: both talk to the same daemon through the same API, show the same jobs with the same progress and the same logs, and offer the same controls (start, pause, resume, kill, and the number of jobs running in parallel).

| | [Terminal monitor](/docs/sessions/terminal_monitor/) | [GUI monitor](/docs/sessions/gui_monitor/) |
|---|---|---|
| Command | `odatix monitor` | `odatix-gui monitor` |
| Interface | curses, in your terminal | web page, in your browser |
| Works over SSH | ✅ directly | ✅ [via port forwarding](/docs/gui/host_server/) |
| Job list, live logs, progress | ✅ | ✅ |
| Start / pause / kill jobs | ✅ | ✅ |
| Change parallel job count | ✅ | ✅ |
| Filter and sort the job list | ❌ | ✅ |
| Mouse and keyboard driven | ✅ | mouse driven |

> [!NOTE]
> Because there is a single daemon behind both interfaces, a run launched from the terminal is visible in the GUI and vice versa, and you can switch from one to the other in the middle of a run.

Pick whichever fits the moment:

- **[Terminal monitor](/docs/sessions/terminal_monitor/)** — the default when you launch a run from the command line, and the fastest option on a remote machine you reach over SSH.
- **[GUI monitor](/docs/sessions/gui_monitor/)** — richer view with filtering, sorting and layout modes, and the natural choice when you are already using [the Odatix GUI](/docs/gui/app/).

## Duplicate scheduling policy

When preparing jobs, Odatix checks active daemon jobs that target the same work directory:

- If a matching job is in `failed`, `killed`, `canceled` or `cancelled`, it is re-enqueued.
- Otherwise the new job is **skipped** — it is already managed by a session.

This prevents accidental duplicate runs while still allowing a fast restart of failed jobs. It is visible in the preparation logs.

## See also

- [Terminal monitor](/docs/sessions/terminal_monitor/)
- [GUI monitor](/docs/sessions/gui_monitor/)
- [Hosting on a server](/docs/gui/host_server/)
- [Commands reference](/docs/commands/)
