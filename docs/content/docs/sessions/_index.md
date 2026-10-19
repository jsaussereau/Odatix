---
title: "Sessions & job monitor"
description: "Track parallel synthesis, simulation and workflow jobs in real time, and manage detached daemon sessions."
weight: 8
---

# Sessions & job monitor

> [!IMPORTANT] Requires Odatix 4.0+

Odatix runs `fmax`, `synth`, `pnr`, `sim` and `workflow` jobs in the background. Jobs are enqueued into a **session**, then monitored either immediately (default) or later (detached mode). A [**Job Monitor**](/docs/sessions/#two-equivalent-monitors) shows every job's progress and logs live, and lets you start, pause, resume or kill jobs at any time.

{{< toc >}}

## Sessions

A session is a background process, a **daemon**, that runs the jobs handed over to it. Each session is its own daemon process: it schedules its jobs, runs a limited number of them in parallel, and keeps them alive whether or not a monitor is attached. Closing a monitor does not stop the jobs — only [stopping the session](#stop-sessions) does.

Each session has an ID of the form `<pid>.<name>` (e.g. `12345.nightly`), where `<pid>` is the process of its daemon, and can be attached, detached and re-attached freely, from the terminal or from the browser.

A session belongs to the workspace it was started in. The session commands (`odatix ps`, `odatix monitor`, `odatix stop`) work on the sessions of the current workspace: see [sessions of other workspaces](#sessions-of-other-workspaces).

### Default behavior

Without `-d`/`--detach`, a run command enqueues its jobs in a new session and immediately attaches the terminal Job Monitor:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado
{{< /code >}}

### Detached sessions

Use detached mode with `-d`/`--detach` to start jobs and return to the shell immediately. The command says which session took the jobs:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -d
...
[odatix fmax] note: 4 job(s) handed to session 438856.pts-3.myhost: follow them with "odatix monitor -S pts-3.myhost", stop it with "odatix stop -S pts-3.myhost"
{{< /code >}}

### When the jobs are done

A session stays alive once its jobs are done, so that you can still look at their logs. Close it from the end-of-run dialog of the monitor, or with [`odatix stop`](#stop-sessions).

With `-E`/`--exit`, the monitor closes by itself once every job of the run is over (a job still exporting its results is not over), and so does the session. The command then prints what became of the jobs:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -y -E
...
[odatix workflow] warning: 3/4 job(s) succeeded, 1 failed
[odatix workflow] note: Session 517634.pts-12.myhost closed
{{< /code >}}

`-E` waits for the jobs of its own run only. If jobs of another run are still running in that session (several runs can share one with `-S`), the session is kept open and the command says how to follow it.

When the terminal cannot show the monitor (a script, a CI job, `nohup`), `-E` still means that the run is over when the command returns: the command waits for the jobs, printing a line each time their count changes (and saying when auto-pause holds some of them), then closes the session the same way. Without a terminal, every line is written as soon as it is printed, without color codes. <kbd>Ctrl</kbd>+<kbd>C</kbd> stops the waiting, not the jobs. Without `-E`, the command returns at once and the jobs keep running in their session.

### Session naming

When using a run command, you can give the session a meaningful name with `-S`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -d -S nightly
{{< /code >}}

The same pattern applies to `odatix synth`, `odatix pnr`, `odatix sim` and `odatix workflow` commands.

Without `-S`, every run starts a new session, named after the terminal and the machine it was started from: `<tty>.<host>` (e.g. `pts-3.myhost`), then `pts-3.myhost.2`, `pts-3.myhost.3`... when that name is taken. A run started without a terminal (a script, a CI job) gets `script.<host>`, and a run started from the GUI `gui.<host>`.

Running a command with `-S` naming a session that is already running **adds its jobs to that session**, instead of starting a new one. They run with the session's settings and environment: the environment variables are those of the command that started the session, not those of the command that adds the jobs.

### Inspect and attach

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ps                 # list the active sessions of this workspace, and where their jobs stand
$ odatix ps -V              # also show where each session listens
$ odatix ps -S nightly      # filter with a selector
$ odatix monitor -S nightly # re-attach the monitor to a session
{{< /code >}}

Without `-S`, `odatix monitor` attaches to the only session of the workspace; when there are several, it lists them and asks for `-S`.

### Session selectors

The `-S`/`--session` selector can match a full session ID (e.g. `12345.nightly`), a session name, a name prefix, or a PID. It is looked up among the sessions of the current workspace. If several sessions match, Odatix lists them and asks you to refine the selector.

### Stop sessions

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix stop -S nightly    # stop one session
$ odatix stop --all         # stop every session of this workspace
{{< /code >}}

### Sessions of other workspaces

Every session of a user runs on the same machine, whatever project it belongs to, and a name like `nightly` can name a session in several of them. The session commands therefore keep to the **current workspace**: `odatix ps` lists its sessions (and says how many others there are), and `-S` only finds a session of this workspace. `odatix stop --all` stops the sessions of this workspace only.

Add `--any-workspace` to reach the sessions of every workspace:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ps --any-workspace                   # every session of the machine
$ odatix monitor --any-workspace -S nightly   # a session of another workspace
$ odatix stop --any-workspace --all           # every session of every workspace
{{< /code >}}

Outside of any workspace (a directory with no `odatix.yml` above it), every session is in reach, as with `--any-workspace`.

### Sessions of other users

The session commands also keep to **your own** sessions: `odatix ps` lists them
(and says how many sessions other users run here), and `-S` only finds one of
yours. Add `--any-user` to reach the sessions of every user; `ps --any-user`
says whose each session is and who may use it:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ps --any-user
session          user   access  jobs           pid    uptime
12345.nightly    me     user    3/19 done      12345  01:12:40
23456.regress    alice  group   0/40 done      23456  00:05:10
34567.debug      bob    no      -              34567  02:30:00
{{< /code >}}

Reaching a session of another user is not the right to use it. A session is
private to its owner unless it was started shared:

| Access | Who may use the session besides its owner |
|---|---|
| `user` (default) | Nobody. |
| `group` | The members of the group of the workspace directory. |
| `other` | Every user of the machine. |

Using it means everything its owner can do: monitor it, add, pause or kill its
jobs, stop it. Choose the access in `odatix.yml` (`session_access`, for every
session of the workspace) or for one run (`--session-access`):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -S regress --session-access group   # a session the team may use
$ odatix monitor --any-user -S regress             # attach to it, as another member of the group
$ odatix synth -S regress                          # add jobs to it, from the same workspace
{{< /code >}}

`no` in the `access` column is a session not shared with you: commands on it
fail with `Session ... belongs to bob and is not shared with you`. Root can act
on every session, which is what an administrator does to clean up a machine:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo odatix ps --any-workspace --any-user     # every session of the machine
$ sudo odatix stop --any-workspace --any-user --all
{{< /code >}}

## Security

Adding a job to a session means running a command line on the machine that hosts it. Reaching a session's API is therefore exactly the right to execute code as the user who owns it, and Odatix treats it that way.

### A session is private to its owner

By default a session listens on a **Unix domain socket** — not on a network port. The socket lives in a directory only its owner may enter (`$XDG_RUNTIME_DIR/odatix`, or `/tmp/odatix-<uid>`), so no other user on the machine can reach it, and nothing on the network can.

A session shared with a group or with every user (see [sessions of other users](#sessions-of-other-users)) is reached the same way, with permissions that let exactly those users in: its state file, which holds its tokens, is readable by the group of the workspace (`group`) or by everybody (`other`); its socket is in `/tmp/odatix-<uid>-shared`, a directory they may traverse but not list. The directory holding the state files of a workspace (`.odatix_sessions`) is never listable by other users, and the logs of a session stay private to its owner.

On Windows, where the API server cannot use a Unix socket, a session falls back to a **loopback TCP port** (`127.0.0.1`). It is not reachable from another machine, and the token below is still required.

Whichever transport is used, `odatix ps` shows the address of each session:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix ps
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
$ odatix ps -R user@server                        # list the sessions of another machine
$ odatix ps -R user@server:/path/to/workspace     # ... in a given workspace
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
> Both interfaces talk to the same session daemons, so a run launched from the terminal is visible in the GUI and vice versa, and you can switch from one to the other in the middle of a run.

Pick whichever fits the moment:

- **[Terminal monitor](/docs/sessions/terminal_monitor/)** — the default when you launch a run from the command line, and the fastest option on a remote machine you reach over SSH.
- **[GUI monitor](/docs/sessions/gui_monitor/)** — richer view with filtering, sorting and layout modes, and the natural choice when you are already using [the Odatix GUI](/docs/gui/app/).

## Duplicate scheduling policy

When preparing jobs, Odatix checks the jobs of the active sessions (of every workspace) that use the same work directory:

- If a matching job is in `failed`, `killed`, `canceled` or `cancelled`, it is re-enqueued.
- Otherwise the new job is **skipped** — it is already managed by a session. A run whose jobs are all skipped, or already done, has nothing to run: it says so and exits with `0`.

This prevents two sessions from running the same job directory at the same time, while still allowing a fast restart of failed jobs. It applies to every run command (`fmax`, `synth`, `pnr`, `analyze`, `sim`, `workflow`), and is visible in the preparation logs and in the "Already managed in a session" section of the plan.

## From a Python script

The [Python API](/docs/python_api/#following-and-stopping-a-run) lists the sessions of a workspace, follows the jobs of a run it started, and stops a session, as `odatix ps`, `odatix monitor` and `odatix stop` do.

## See also

- [Terminal monitor](/docs/sessions/terminal_monitor/)
- [GUI monitor](/docs/sessions/gui_monitor/)
- [Hosting on a server](/docs/gui/host_server/)
- [Commands reference](/docs/commands/)
