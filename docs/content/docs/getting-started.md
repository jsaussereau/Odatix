---
title: "Getting started"
description: "From nothing to a first chart in five steps, then the core concepts behind every Odatix run."
weight: 0
---

# Getting started

This page takes you from nothing to a first chart in five steps, then explains
the ideas behind them. Every term in **bold** is defined where it first appears,
and again, with the words Odatix avoids for it, in the [glossary](/docs/glossary/).
For longer walkthroughs, see the [tutorials](/tutorials/).

{{< toc >}}

## Five steps to a first result

> [!IMPORTANT] Prerequisite: an EDA tool
> Odatix drives the EDA tools you already have and ships none of them. You need
> **at least one** installed and on your `PATH`, for instance AMD Vivado, Intel
> Quartus Prime, Synopsys Design Compiler, Cadence Genus or LibreLane. See
> [Install supported EDA tools](/install/eda_tools/). The examples below use
> Vivado: replace `vivado` with the name of yours (`quartus`,
> `design_compiler`, `genus`, `librelane`...).

**1. Install Odatix** (Python 3.6 or later; see [Install Odatix](/install/) for
the other ways):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ pip install odatix
{{< /code >}}

> [!WARNING] Odatix 4.0 is not on PyPI yet
> This documentation describes Odatix 4.0. Until it is released,
> `pip install odatix` installs Odatix 3.7, whose commands differ: the steps
> below fail with it. Install Odatix 4.0
> [from sources](/install/sources/) instead. `odatix --version` tells which one
> you have.

**2. Create a workspace.** A **workspace** is a directory holding an
`odatix.yml` file and the settings of what Odatix runs there:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p ~/odatix_examples && cd ~/odatix_examples
{{< /code >}}

**3. Fill it with the examples.** They add example
[**architectures**](/docs/glossary/#architecture) (parametrizable designs) and,
for each, several [**configurations**](/docs/glossary/#configuration) (one set of
parameter values each):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix init --examples
{{< /code >}}

It asks before writing anything (`-y` skips the question), then ends with the
command of a first run, the one of the next step.

**4. Run.** `odatix fmax` searches the maximum frequency of every configuration
listed in `odatix_userconfig/fmax_settings.yml`, on every
[**target**](/docs/glossary/#target) (FPGA device or ASIC technology) the target
file of the [**tool**](/docs/glossary/#tool) enables. Each pair is a
[**job**](/docs/glossary/#job). Start with a single configuration, and stop each
search after synthesis (`--until synthesis`, `-u` for short): its ten or so
syntheses take about a quarter of an hour, where the full run below can take
hours.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado -a "Example_Counter_verilog/08bits" --until synthesis
{{< /code >}}

Odatix first lists the jobs it is about to run and asks `Continue? (Y/n)`
(`-y` skips the question). The jobs then run in parallel in the
[Job Monitor](/docs/sessions/terminal_monitor/), a full-screen view of their
progress and logs: press `q` once they are done to get your shell back, or `d`
to detach and let them run in the background (`odatix monitor` brings the
monitor back). With `-E`, the monitor closes by itself when the last job ends.

The full run implements every configuration of the file: 7 configurations on
Vivado, each one searched with up to about ten syntheses **and** place and
routes, since `pnr` is the step Vivado runs up to by default. Expect it to take
a while:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado
{{< /code >}}

Running it after the short run above does not start over: the configuration
already searched resumes at the step it stopped at.

With an ASIC tool, first give it a technology of yours: the targets it lists are
only examples (see [Add targets](/tutorials/own_flows/add_targets/)).

**5. Look at the results.** When the jobs of a run are done, Odatix exports
their results to `results/` (not before: a run still going has nothing in the
Explorer yet); Odatix Explorer charts them in your browser:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Everything above can also be done from the graphical interface: `odatix-gui`.
To run your own design next, follow [Add your own design](/tutorials/own_designs/).

## The core concepts

Everything in Odatix is built from a few key ideas. The steps above met most of
them; here they are in more detail.

### Architecture

An [**architecture**](/docs/glossary/#architecture) is a parametrizable RTL (or generated) design. It lives in `odatix_userconfig/architectures/<name>/`, described by a `_settings.yml` that points to your sources, the top-level file and module, the clock/reset signals, and the delimiters that mark the parameter section of the top level. See [Add your own design](/tutorials/own_designs/architecture/).

### Configuration

A [**configuration**](/docs/glossary/#configuration) is one set of parameter values of an architecture. You describe each configuration with a small *parameter file*, or you let Odatix generate them. See [Configurations](/docs/configurations/).
Parameters that vary together form a [**parameter domain**](/docs/glossary/#parameter-domain); a run combines the configurations of the domains it selects.

### Target and tool

A [**target**](/docs/glossary/#target) is where a configuration is implemented: an FPGA device or an ASIC technology. Each [**tool**](/docs/glossary/#tool) lists its targets in its target file (`target_<tool>.yml`, in `odatix_userconfig/targets/`), and a single run implements every selected configuration on every selected target.

### Job

A [**job**](/docs/glossary/#job) is the unit of work: one configuration of an architecture, on one target, by one tool (a fixed-frequency synthesis also has one job per frequency). Odatix runs the jobs of a [**session**](/docs/sessions/) in parallel, through a background [daemon](/docs/glossary/#daemon), and shows their progress in the Job Monitor.

### Workflow

A [**workflow**](/docs/glossary/#workflow) is a chain of tasks of your own, with their dependencies, like a Makefile. It lives in `odatix_userconfig/workflows/<name>/`, described by a `_settings.yml` that defines the tasks, their dependencies and the commands to run. A workflow does not have to involve a design: any command-line step can become a task. Like an architecture, it can have parameter domains: a run then gives each of its configurations a job of its own. See [Workflows](/docs/features/workflows/).

## The typical loop

{{< img src="/images/diagrams/typical-loop.svg" shadow="false" >}}

In commands (each of them can also be done from `odatix-gui`):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui                # define architectures, configurations, targets and workflows
$ odatix fmax --tool vivado # search the Fmax of every configuration on every target, in parallel
$ odatix-explorer           # chart the results in your browser
{{< /code >}}

## Keep going

{{< doc-cards cols="3" >}}
{{< doc-card title="Configurations" link="/docs/configurations/" icon="sliders" accent="#425ad6" >}}
Define parametrizable designs, parameter domains and automatic configuration generation.
{{< /doc-card >}}

{{< doc-card title="Graphical user interface" link="/docs/gui/" icon="window" accent="#0284c7" >}}
Odatix GUI, Odatix Explorer, and how to host them on a server.
{{< /doc-card >}}

{{< doc-card title="Sessions and job monitor" link="/docs/sessions/" icon="activity" accent="#059669" >}}
Job execution in daemon sessions, terminal and graphical job monitors.
{{< /doc-card >}}

{{< /doc-cards >}}
