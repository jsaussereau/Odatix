---
title: "Documentation"
description: "The complete reference for Odatix — concepts, configuration, commands and the graphical tools."
---

# Odatix Documentation

Welcome to the Odatix documentation. It is organized in three layers, and every
page links to its counterparts in the other two:

| Layer | Where | Answers |
|-------|-------|---------|
| **Features** | [/docs/features/](/docs/features/) | What each capability is, when you need it, how it combines with the others, and how to drive it from the CLI and the GUI. |
| **Tutorials** | [/tutorials/](/tutorials/) | A complete walkthrough you can follow start to finish. |
| **Configuration reference** | [/docs/reference/](/docs/reference/) | Every key of every configuration file, exhaustively. |

Start with a feature if you are wondering *what Odatix can do*, a tutorial if you
want to *get something running*, and the reference when you know what you need
and want the exact key.

## Start here

{{< card title="Features" link="/docs/features/" >}}
A high-level tour of what Odatix does — architecture exploration, synthesis, Fmax search, simulation, workflows and results exploration.
{{< /card >}}

{{< card title="Getting started" link="/docs/getting-started/" >}}
Install Odatix, initialize a workspace, and understand the core concepts — designs, configurations, targets and jobs.
{{< /card >}}

## By topic

{{< section-container >}}
<div class="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">

{{< card title="Configurations" link="/docs/configurations/" no-margin="true" >}}
Define parametrizable designs, parameter domains and automatic configuration generation.
{{< /card >}}

{{< card title="Graphical User Interface" link="/docs/gui/" no-margin="true" >}}
Odatix GUI, Odatix Explorer, and how to host them on a server.
{{< /card >}}

{{< card title="Sessions and job monitor" link="/docs/sessions/" no-margin="true" >}}
Job execution in daemon sessions, terminal and graphical job monitors.
{{< /card >}}

{{< card title="Metrics" link="/docs/metrics/" no-margin="true" >}}
Define what Odatix measures — extract any value from your reports, and derive metrics that link simulation and synthesis results.
{{< /card >}}

{{< card title="Custom tools and flows" link="/docs/custom_tools/" no-margin="true" >}}
Add your own EDA tools to Odatix, and your own ways of running the ones it ships.
{{< /card >}}

{{< card title="Results & export" link="/docs/results/" no-margin="true" >}}
How results are stored, exported, and consumed by Odatix Explorer.
{{< /card >}}

{{< card title="Python API" link="/docs/python_api/" no-margin="true" >}}
Programmatic access to Odatix functionality in Python.
{{< /card >}}

{{< card title="Configuration file reference" link="/docs/reference/" no-margin="true" >}}
Every YAML key Odatix reads, and how settings are resolved and overridden.
{{< /card >}}

{{< card title="Commands reference" link="/docs/commands/" no-margin="true" >}}
Every `odatix` and `odatix-explorer` command, with options and examples.
{{< /card >}}

{{< card title="Troubleshooting" link="/docs/troubleshooting/" no-margin="true" >}}
Diagnose missing tools, invalid settings, daemon sessions, exports and empty Explorer dashboards.
{{< /card >}}

</div>
{{< /section-container >}}

## See also

- [Install Odatix](/install/) and the [supported EDA tools](/install/eda_tools/)
- [Tutorials](/tutorials/) — hands-on, step-by-step guides
