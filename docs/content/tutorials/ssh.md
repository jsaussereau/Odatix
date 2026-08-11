---
title: "Access Odatix over SSH"
date: 2026-07-31
author: "Jonathan Saussereau"
weight: 10
description: "Run Odatix on a remote server, keep jobs alive after logout, and securely access Odatix Explorer from a workstation."
categories: ["Tutorial", "Server"]
tags: ["ssh", "remote", "daemon", "explorer"]
featured_image: ""
---

{{< toc >}}

This tutorial keeps compute-heavy EDA runs on a server while the browser and
interactive work stay on your workstation. It uses a detached Odatix session
for the jobs and an SSH tunnel for Odatix Explorer.

> [!IMPORTANT]
> The server must already have Odatix, the required EDA tools and the workspace
> files. Do not expose Explorer directly to an untrusted network when an SSH
> tunnel is available.

## Step 1 — Connect to the server

From the workstation, open a terminal and connect to the account that owns the
workspace:

{{< code lang=bash filename="Terminal (workstation)" prompt="true" >}}
$ ssh user@server.example.org
{{< /code >}}

Change to the workspace, then activate the environment and load the tool setup
if your site requires them:

{{< code lang=bash filename="Terminal (server)" prompt="true" >}}
$ cd ~/projects/my-odatix-workspace
$ source .venv/bin/activate          # if this is where Odatix was installed
$ module load vivado                 # only on sites using environment modules
{{< /code >}}

The optional [environment-modules tutorial](/tutorials/modules/) explains how
to make that step repeatable on a shared cluster.

If you use VS Code, the Remote - SSH extension can open the same server
workspace directly. The terminal commands below remain the same.

## Step 2 — Start a detached run

Give the session a name and detach so the jobs stay alive after the SSH shell
closes:

{{< code lang=bash filename="Terminal (server)" prompt="true" >}}
$ odatix fmax --tool vivado -d -S nightly
$ odatix ls -S nightly
$ exit
{{< /code >}}

The daemon was started on the server, so closing the SSH session does not stop
the queued jobs.

## Step 3 — Reconnect and monitor later

Reconnect whenever you want to inspect the session:

{{< code lang=bash filename="Terminal (workstation)" prompt="true" >}}
$ ssh user@server.example.org
{{< /code >}}

{{< code lang=bash filename="Terminal (server)" prompt="true" >}}
$ cd ~/projects/my-odatix-workspace
$ odatix monitor -S nightly
{{< /code >}}

Use `odatix ls` to list sessions, or `odatix stop -S nightly` to stop the one
named `nightly`. See [Job Monitor & sessions](/docs/gui/monitor/) for the full
session model.

## Step 4 — Start Explorer on the server

Use a second SSH terminal on the server, or a terminal multiplexer such as
`tmux`, then start Explorer without opening a remote browser:

{{< code lang=bash filename="Terminal (server)" prompt="true" >}}
$ cd ~/projects/my-odatix-workspace
$ odatix-explorer --nobrowser --port 8052
{{< /code >}}

By default, Explorer listens only on the server's loopback interface. Leave
this terminal running while viewing the dashboard.

## Step 5 — Create an SSH tunnel

In a separate local terminal, forward a local port to Explorer on the server:

{{< code lang=bash filename="Terminal (workstation)" prompt="true" >}}
$ ssh -N -L 8052:127.0.0.1:8052 user@server.example.org
{{< /code >}}

Open `http://127.0.0.1:8052` in the workstation browser. Traffic stays inside
the encrypted SSH connection; the server does not need an open firewall port.

Press `Ctrl-C` in the tunnel terminal when you no longer need the dashboard.
Stop Explorer with `Ctrl-C` in its server terminal.

## Optional: use a persistent Explorer shell

If Explorer must stay up after the SSH window closes, start it in `tmux`:

{{< code lang=bash filename="Terminal (server)" prompt="true" >}}
$ tmux new -s odatix-explorer
$ odatix-explorer --nobrowser --port 8052
# Detach with Ctrl-b then d
$ tmux attach -t odatix-explorer
{{< /code >}}

## Next steps

- [Hosting on a server](/docs/gui/host_server/) — reference for remote use
- [Environment modules](/tutorials/modules/) — load site-managed EDA tools
- [Troubleshooting](/docs/troubleshooting/) — resolve daemon and remote-access problems
