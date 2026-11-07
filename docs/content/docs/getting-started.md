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

{{< doc-cards cols="2" >}}
{{< doc-card title="Run the examples" link="/tutorials/run_examples/" icon="rocket" accent="#059669" >}}
Get results quickly on designs that ship with Odatix, already configured: run a synthesis, an Fmax search, simulations or a workflow, then chart the results.
{{< /doc-card >}}

{{< doc-card title="Hands-on workshop" link="/tutorials/workshop/" icon="tutorial" accent="#d97706" >}}
Set everything up yourself, step by step: on a pipelined CORDIC core, you configure simulations, FPGA and ASIC implementation and the design space, then let an automated exploration find the Pareto front of accuracy, area and latency.
{{< /doc-card >}}
{{< /doc-cards >}}

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
