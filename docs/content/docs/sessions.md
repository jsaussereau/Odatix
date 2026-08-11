---
title: "Sessions & Job Monitor"
description: "Track parallel synthesis, simulation and workflow jobs in real time, and manage detached daemon sessions."
weight: 8
---

# Sessions & Job Monitor

> [!IMPORTANT] Requires Odatix 4.0+

Odatix runs `fmax`, `synth`, `sim` and `workflow` through a background **daemon**. Jobs are enqueued into a **session**, then monitored either immediately (default) or later (detached mode). The **Job Monitor** shows every job's progress and logs live, and lets you start, pause, resume or kill jobs at any time.

{{< toc >}}

## Default behavior

Without `-d`/`--detach`, a run command enqueues its jobs in a new session and immediately attaches the terminal Job Monitor:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado
{{< /code >}}

## Detached sessions

Use detached mode using `-d`/`--detach` to start jobs and return to the shell immediately. 

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -d
{{< /code >}}

## Session naming

When using a run command, you can give the session a meaningful name with `-S`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -d -S nightly
{{< /code >}}

The same pattern applies to `odatix synth`, `odatix sim` and `odatix workflow` commands. 

## Inspect and attach

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ls                 # list active sessions
$ odatix ls -S nightly      # filter with a selector
$ odatix monitor -S nightly # re-attach the monitor to a session
{{< /code >}}

![Job Monitor](/images/screenshots/job-monitor.png "Job Monitor")

### Session selectors

The `-S`/`--session` selector can match a full session ID (e.g. `12345.nightly`), a session name, a name prefix, or a PID. If several sessions match, Odatix asks you to refine the selector.

### Graphical monitor

The Job Monitor in [the Odatix GUI](/docs/gui/app/) is a graphical interface that shows the same information as the terminal monitor.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

Open the GUI, click the **Monitor Jobs** card (or **Monitor** in the top bar), and pick a session from the list. There is a single daemon behind both interfaces, so a run launched from the terminal is visible in the GUI and vice versa.

> [!TIP]
> You can also launch `odatix-gui` directly on the monitor page an on a specific session

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui monitor # Start the GUI on the monitor page
$ odatix-gui monitor -S my_session # Start the GUI on the monitor page of the session my_session
{{< /code >}}

> [!NOTE]
> If you run `odatix-gui` on a remote server, see [Hosting on a server](/docs/gui/host_server/) for instructions to access it over the network.

## Stop sessions

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix stop -S nightly    # stop one session
$ odatix stop --all         # stop every session
{{< /code >}}

## Duplicate scheduling policy

When preparing jobs, Odatix checks active daemon jobs that target the same work directory:

- If a matching job is in `failed`, `killed`, `canceled` or `cancelled`, it is re-enqueued.
- Otherwise the new job is **skipped** — it is already managed by a session.

This prevents accidental duplicate runs while still allowing a fast restart of failed jobs. It is visible in the preparation logs.

## See also

- [Hosting on a server](/docs/gui/host_server/)
- [Commands reference](/docs/commands/)
