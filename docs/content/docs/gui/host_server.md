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

See [Job Monitor & sessions](/docs/gui/monitor/) for the full session model.

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

### Option B — expose on the local network

If the server and your workstation share a trusted network, bind Explorer to the network interface:

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ odatix-explorer --network --port 8052
{{< /code >}}

Then browse to `http://<server-address>:8052` from your workstation.

> [!WARNING]
> `--network` exposes Explorer to every machine that can reach the server on that port. Only use it on a trusted network, and prefer the SSH tunnel otherwise.

## Keeping a foreground process alive

If you run Explorer (or an attached monitor) in the foreground over SSH and want it to survive a disconnect, run it inside a terminal multiplexer such as `tmux` or `screen`:

{{< code lang=bash filename="Terminal (on the server)" prompt="true" >}}
$ tmux new -s odatix
$ odatix-explorer --network --port 8052
# detach with Ctrl-b then d; reattach later with: tmux attach -t odatix
{{< /code >}}

## See also

- [SSH tutorial](/tutorials/ssh/)
- [Job Monitor & sessions](/docs/gui/monitor/)
- [Odatix Explorer](/docs/gui/explorer/)
