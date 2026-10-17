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

## Security

Adding a job to a session means running a command line on the machine that hosts it. Reaching a session's API is therefore exactly the right to execute code as the user who owns it, and Odatix treats it that way.

### A session is private to its owner

By default a session listens on a **Unix domain socket** — not on a network port. The socket lives in a directory only its owner may enter (`$XDG_RUNTIME_DIR/odatix`, or `/tmp/odatix-<uid>`), so no other user on the machine can reach it, and nothing on the network can.

On Windows, where the API server cannot use a Unix socket, a session falls back to a **loopback TCP port** (`127.0.0.1`). It is not reachable from another machine, and the token below is still required.

Whichever transport is used, `odatix ls` shows the address of each session:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ls
workspace          session         address                                     pid     uptime
/home/me/project   12345.nightly   unix:/run/user/1000/odatix/a2a661b8.sock    12345   01:12:40
{{< /code >}}

### Every request is authenticated

Each session generates two random tokens when it starts, and every API call must present one:

| Token | What it allows |
|---|---|
| **control** | everything: enqueue, start, pause, kill, change the job count, shut the session down |
| **read** | snapshots and logs only — watching a session, never acting on it |

The tokens are stored in the session's state file (`<workspace>/.odatix_sessions/state.<name>.json`), created readable **by its owner only**. Odatix commands read them from there, so nothing has to be passed by hand on the same machine.

The `Host` header of every request is checked as well. A web page you visit can be made to send requests to `127.0.0.1`, but it cannot read your state file and cannot forge that header, so it is refused twice over.

> [!WARNING]
> Anyone who can read a session's state file can run commands as you. Do not copy it, and do not make `.odatix_sessions/` world-readable.

### Reaching a session on another machine

`-R`/`--remote` works on a remote session over SSH, with **no port opened anywhere**: the remote session keeps listening on its private socket, and SSH forwards the API to it.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ls -R user@server                        # list the sessions of another machine
$ odatix ls -R user@server:/path/to/workspace     # ... in a given workspace
$ odatix monitor -R user@server -S nightly        # attach the monitor to a remote session
$ odatix stop -R user@server -S nightly           # stop a remote session
{{< /code >}}

Authentication, encryption and host verification are SSH's, exactly as your site already configures them; the session token then authorises the calls inside the tunnel. Odatix must be installed and on the `PATH` of the remote machine (set `ODATIX_REMOTE_COMMAND` if it is called something else).

### Exposing a session on the network

A session refuses to bind anything but a loopback address unless it is explicitly told to. Prefer the SSH tunnel above; use this only when a tunnel is genuinely not an option (a container, a private network you control):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix monitor --host 10.0.0.4 --port 8000 --token <control token>
{{< /code >}}

The token can also come from the `ODATIX_DAEMON_TOKEN` environment variable. Note that a TCP session speaks plain HTTP: on an untrusted network the token travels in clear, which is the reason the tunnel is the recommended path.

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
