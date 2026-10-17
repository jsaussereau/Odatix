---
title: "Getting Started"
description: "From nothing to a first chart in five steps, then the core concepts behind every Odatix run."
weight: 0
---

# Getting Started

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

**2. Create a workspace.** A **workspace** is a directory holding an
`odatix.yml` file and the settings of what Odatix runs there:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/odatix_first && cd ~/odatix_first
{{< /code >}}

**3. Fill it with the examples.** They add example
[**architectures**](/docs/glossary/#architecture) (parametrizable designs) and,
for each, several [**configurations**](/docs/glossary/#configuration) (one set of
parameter values each):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix init --examples
{{< /code >}}

**4. Run.** `odatix fmax` searches the maximum frequency of every configuration
listed in `odatix_userconfig/fmax_settings.yml`, on every
[**target**](/docs/glossary/#target) (FPGA device or ASIC technology) the target
file of the [**tool**](/docs/glossary/#tool) enables. Each pair is a
[**job**](/docs/glossary/#job); the jobs run in parallel, in the Job Monitor:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado
{{< /code >}}

With an ASIC tool, first give it a technology of yours: the targets it lists are
only examples (see [Add targets](/tutorials/own_flows/add_targets/)).

**5. Look at the results.** When the jobs are done, Odatix exports their results
to `results/`; Odatix Explorer charts them in your browser:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Everything above can also be done from the graphical interface: `odatix-gui`.
To run your own design next, follow [Add your own design](/tutorials/own_designs/).

## The core concepts

Everything in Odatix is built from a few key ideas. The steps above met most of
them; here they are in more detail.

### Workflow

A [**workflow**](/docs/glossary/#workflow) is a Makefile-like task execution graph. It lives in `odatix_userconfig/workflows/<name>/`, described by a `_settings.yml` that lets you define the tasks, their dependencies, and the commands to run. See [Workflows](/docs/features/workflows/) for details. They do not have to be tied to a design, and can be used for any kind of task automation.

### RTL Architecture

An **architecture** is an HDL (or generated) design. It lives in `odatix_userconfig/architectures/<name>/`, described by a `_settings.yml` that points to your sources, the top-level file and module, the clock/reset signals, and the delimiters that mark the parameter section of the top level. Parametrizable design configurations can be explored with odatix.

### Design Configuration

A **configuration** is one concrete instantiation of a design — a specific set of parameter values. You describe each configuration with a small *parameter file*, or you let Odatix generate them automatically. See [Configurations](/docs/configurations/). 
The impact of different parameters can be studied by grouping parameters into a [parameter domain](/docs/configurations/param_domains/).

### Target

A **target** is where a configuration is implemented — an FPGA device or an ASIC technology. Targets are listed in the per-tool `target_*.yml` files, and a single run implements every selected configuration on every selected target.

### Job

A **job** is the unit of work: implement (or simulate) *one configuration* on *one target*. Odatix schedules jobs in parallel through a background [daemon](/docs/glossary/#daemon), grouped into a [session](/docs/sessions/), and shows their progress in the Job Monitor.

## The typical loop

{{< img src="/images/diagrams/typical-loop.svg" shadow="false" >}}

In commands:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui                # start the GUI where you can define workflows, design architectures, configurations, and targets 
$ odatix fmax --tool vivado # find Fmax for every configuration/target, in parallel (can also be done from odatix-gui)
$ odatix-explorer           # open the interactive results dashboard (can also be done from the odatix-gui)
{{< /code >}}

## Keep going

{{< doc-cards cols="3" >}}
{{< doc-card title="Configurations" link="/docs/configurations/" icon="sliders" accent="#425ad6" >}}
Define parametrizable designs, parameter domains and automatic configuration generation.
{{< /doc-card >}}

{{< doc-card title="Graphical User Interface" link="/docs/gui/" icon="window" accent="#0284c7" >}}
Odatix GUI, Odatix Explorer, and how to host them on a server.
{{< /doc-card >}}

{{< doc-card title="Sessions and job monitor" link="/docs/sessions/" icon="activity" accent="#059669" >}}
Job execution in daemon sessions, terminal and graphical job monitors.
{{< /doc-card >}}

{{< /doc-cards >}}
