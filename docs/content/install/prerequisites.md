---
title: "Prerequisites"
description: "Check the software, EDA tools and workspace access required before running Odatix."
weight: 1
---

# Prerequisites

Check these requirements before creating a workspace. Odatix itself is a Python
application; the software required after that depends on the jobs you plan to
run.

{{< toc >}}

## Core requirements

| Requirement | Needed for | Notes |
|-------------|------------|-------|
| Python 3.6 or newer | Every Odatix command | A virtual environment is recommended. |
| `pip` | Installing Odatix | Use the `pip` attached to the Python interpreter you intend to run. |
| A writable workspace | Every run | Odatix creates `work/`, `results/` and configuration files. |
| A shell supported by your platform | Workflows and tool commands | Linux is the recommended platform for EDA flows. |

`make` is not required by the Odatix CLI itself, but the bundled simulation
examples use Makefiles. Install it if you plan to run or adapt those examples.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 --version
$ python3 -m pip --version
$ make --version                 # needed by the bundled Makefile simulations
{{< /code >}}

## Select the tools for your task

| What you want to do | Additional requirement |
|---------------------|------------------------|
| Check RTL elaboration | An analysis-capable tool such as Verilator, Vivado, Genus or Design Compiler. |
| Run FPGA or ASIC synthesis | A supported synthesis tool, its libraries/PDK setup, and any required licence. |
| Run place & route | A configured implementation tool plus technology-specific libraries and scripts. |
| Run simulations | A simulator and a testbench command or Makefile. |
| Run a workflow | Whatever executables, data files and Python packages its tasks require. |

The supplied `dummy` tool is useful for exercising workspace creation,
scheduling and result handling without an EDA licence. It does not produce
hardware results that should be used for engineering decisions.

See [supported EDA tools](/install/eda_tools/) for installation notes. For a
custom or in-house tool, see [Custom tools and flows](/docs/custom_tools/).

## Verify the command-line installation

After installing Odatix, confirm that the executable resolves from the intended
environment:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix --version
$ odatix -h
$ odatix-explorer -h
{{< /code >}}

For an EDA tool, first use its own version command in the same terminal that
will launch Odatix. For example, `verilator --version` or `vivado -version`.
This catches a missing `PATH`, module or licence environment before a campaign
queues many jobs.

## Before a first run

1. Create a clean directory and initialize it with `odatix init` or
   `odatix init --examples`.
2. Select only designs, simulations or workflows that are ready in the matching
   run-settings file.
3. Select a valid target in the tool's `target_<tool>.yml` file for synthesis
   or place & route.
4. Start with a small configuration set and a conservative `nb_jobs` value.
5. Run [RTL analysis](/docs/features/analysis/) before a costly synthesis campaign when
   the selected tool supports it.

On a shared server, load the required EDA environment before starting Odatix;
see the [environment-modules tutorial](/tutorials/modules/). For a remote
workspace, use the [SSH tutorial](/tutorials/ssh/).

## Next steps

- [Install Odatix from PyPI](/install/pypi/)
- [Install Odatix from sources](/install/sources/)
- [Getting started](/docs/getting-started/)
- [Troubleshooting](/docs/troubleshooting/)
