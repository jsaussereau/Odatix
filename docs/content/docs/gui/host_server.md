---
title: "Hosting on a Server"
description: "Run jobs and Odatix Explorer on a remote machine and access them from your workstation."
weight: 3
---

# Hosting on a Server

EDA runs are heavy: it is common to run Odatix on a powerful remote machine (a lab server or cluster node) while you work from a laptop. This page covers running jobs remotely, keeping them alive after you disconnect, and reaching Odatix Explorer over the network.

{{< toc >}}

## Run jobs remotely and disconnect

Because runs are daemon-driven, you can start a **detached** session over SSH and log out — the jobs keep running:

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ odatix fmax --tool vivado -d -S nightly
$ odatix ls                 # confirm the session is running
$ exit                      # jobs continue in the daemon
{{< /code >}}

Reconnect later and re-attach the monitor:

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ odatix monitor -S nightly
{{< /code >}}

See [Job Monitor & sessions](/docs/sessions/) for the full session model.

## Access Odatix Explorer over the network

Explorer serves a web UI. There are two ways to reach it from your workstation.

### Option A — SSH tunnel (recommended)

Keep Explorer bound to localhost on the server, and forward its port through SSH. This is secure by default and needs no firewall changes.

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ odatix-explorer --nobrowser --port 8052
{{< /code >}}

{{< code lang=bash filename="Terminal (on your workstation)" prompt="true" >}}
$ ssh -N -L 8052:localhost:8052 user@server
{{< /code >}}

Then open `http://localhost:8052` in your local browser. For a step-by-step guide, see the [SSH tutorial](/tutorials/ssh/).

A port given with `--port` is the port Explorer listens on, or nothing: if
another program (another user's Explorer, on a shared server) already holds it,
Explorer stops with an error rather than moving to another port your tunnel
does not point at. Without `--port`, it takes 8052 or the next free one: read
the address it prints before you open the tunnel. Restarting it right away on
the same port works, the port is not left blocked by the previous run.

### Option B — expose on the local network

If the server and your workstation share a trusted network, bind Explorer to the network interface:

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ odatix-explorer --network --port 8052
{{< /code >}}

Then browse to `http://<server-address>:8052` from your workstation.

> [!WARNING]
> `--network` exposes Explorer to every machine that can reach the server on that port, with no authentication. Anyone who reaches it can read every result of the result directory, and save or replace [saved views](/docs/gui/explorer/#saved-views) in it. Only use it on a trusted network, prefer the SSH tunnel otherwise, and add `--read-only` so that visitors cannot write anything:
>
> `odatix-explorer --network --read-only --port 8052`

## Running it in the background

Under `nohup`, `tmux` or a service manager, Explorer and the GUI write their
address as soon as they start, so the log tells which address to use:

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ nohup odatix-explorer --nobrowser > explorer.log 2>&1 < /dev/null &
$ cat explorer.log
[odatix-explorer] Server running on http://127.0.0.1:8052/ (localhost only)
[odatix-explorer] not started from a terminal: end the process (Ctrl+C, kill) to stop the server
{{< /code >}}

Without a terminal on its standard input, there is no key to wait for and no
terminal mode to change: `--normal-term-mode` is not needed.

## Keeping a foreground process alive

If you run Explorer (or an attached monitor) in the foreground over SSH and want it to survive a disconnect, run it inside a terminal multiplexer such as `tmux` or `screen`:

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ tmux new -s odatix
$ odatix-explorer --network --port 8052
# detach with Ctrl-b then d; reattach later with: tmux attach -t odatix
{{< /code >}}

## See also

- [SSH tutorial](/tutorials/ssh/)
- [Job Monitor & sessions](/docs/sessions/)
- [Odatix Explorer](/docs/gui/explorer/)
