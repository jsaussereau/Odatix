---
title: "Use Environment Modules"
date: 2026-07-31
author: "Jonathan Saussereau"
weight: 11
description: "Load a site-managed Python and EDA environment before launching Odatix on a shared server or cluster."
categories: ["Tutorial", "Server"]
tags: ["lmod", "environment-modules", "cluster", "eda"]
featured_image: ""
---

{{< toc >}}

Many laboratory servers and clusters use **Lmod** or Environment Modules to
provide several versions of Python, Vivado, Design Compiler and PDK setups.
Load the required modules in the shell that starts Odatix so the daemon and
its jobs inherit the correct executable paths and licence environment.

> [!NOTE]
> Module names are site-specific. Replace the names in this tutorial with the
> versions published by your system administrator.

## Step 1 — Discover available modules

Connect to the server and query its module catalogue:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ module avail
$ module spider python
$ module spider vivado
{{< /code >}}

Some sites need an initialization script before the `module` command is
available. Common locations include `/etc/profile.d/modules.sh`; ask the site
administrator instead of copying a path from another system.

## Step 2 — Load a reproducible environment

Start from a clean module set, then load the Python and EDA tool versions for
your project:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ module purge
$ module load python/3.11
$ module load vivado/2024.1
$ module list
{{< /code >}}

Verify the executables in the same terminal:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 --version
$ command -v odatix
$ odatix --version
$ vivado -version
{{< /code >}}

Load the implementation tool, PDK or licence module required by the selected
flow as well. A successful `module load` does not guarantee that a particular
target has all technology files configured; keep the target setup under version
control in the workspace.

## Step 3 — Launch Odatix after loading modules

Start jobs only after the environment is ready:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ cd ~/projects/my-odatix-workspace
$ odatix analyze --tool vivado -E
$ odatix fmax --tool vivado -d -S nightly
{{< /code >}}

If a detached session is restarted from a new shell, load the same modules
again before launching the new session. This avoids a job seeing a different
Python or EDA binary from the one used during validation.

## Step 4 — Put project setup in a small script

A project-local launch script is clearer and safer than relying on an
interactive shell history:

{{< code lang=bash filename="scripts/launch-vivado.sh" >}}
#!/usr/bin/env bash
set -euo pipefail

# Replace these with the module names approved at your site.
source /etc/profile.d/modules.sh
module purge
module load python/3.11
module load vivado/2024.1

exec odatix "$@"
{{< /code >}}

Make it executable and use it for the job command:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ chmod +x scripts/launch-vivado.sh
$ scripts/launch-vivado.sh fmax --tool vivado -d -S nightly
{{< /code >}}

Keep the script in the project repository, but do not commit credentials,
licence secrets or private site paths that should not be shared.

## Step 5 — Diagnose a module-related failure

When the tool preflight fails, capture the environment before bypassing it:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ module list
$ command -v vivado
$ vivado -version
$ odatix fmax --tool vivado -D
{{< /code >}}

`--trust` only skips Odatix's preflight check. It cannot fix a missing module,
licence variable or technology library.

## Next steps

- [Access Odatix over SSH](/tutorials/ssh/)
- [Hosting on a server](/docs/gui/host_server/)
- [Troubleshooting](/docs/troubleshooting/)
