---
title: "Features"
description: "Everything Odatix can do, from architecture exploration to interactive results analysis."
weight: 1
---

# Features

Odatix automates the full implementation and validation loop of configurable
digital designs. Each feature below has its own page explaining what it does,
when you need it, how it combines with the others, and how to use it from the
command line and from the GUI.

Every feature page is the entry point of a trio:

| Layer | Where | For |
|-------|-------|-----|
| **Feature page** | this section | What it is, when to use it, how it fits with the rest. |
| **[Tutorial](/tutorials/)** | `/tutorials/` | A complete, step-by-step run you can follow start to finish. |
| **[Configuration reference](/docs/reference/)** | `/docs/reference/` | Every key of every file, exhaustively. |

{{< section-container >}}
<div class="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">

{{< card title="Architecture exploration" link="/docs/features/architecture-exploration/" >}}
Define parametrizable designs once and let Odatix generate every configuration — with parameter domains and automatic configuration generation.
{{< /card >}}

{{< card title="RTL analysis" link="/docs/features/analysis/" >}}
Elaborate every configuration with one or several tools before synthesis, and catch missing sources, black boxes and lint issues early.
{{< /card >}}

{{< card title="RTL synthesis" link="/docs/features/rtl_synthesis/" >}}
Run synthesis for every configuration on FPGA and ASIC tools, and collect area, resource, power and timing metrics automatically.
{{< /card >}}

{{< card title="Fmax synthesis" link="/docs/features/rtl_fmax_synthesis/" >}}
Automatically find the maximum operating frequency of any design through a parallel binary search on the clock constraint.
{{< /card >}}

{{< card title="Place & route" link="/docs/features/pnr/" >}}
Feed the synthesized netlist from one EDA tool into a PNR tool to implement your design up to layout and signoff, and get post-route metrics.
{{< /card >}}

{{< card title="Simulation & validation" link="/docs/features/simulation/" >}}
Validate and benchmark every design configuration with the simulator of your choice.
{{< /card >}}

{{< card title="Custom workflows" link="/docs/features/workflows/" >}}
Orchestrate arbitrary task pipelines with dependencies, progress tracking and custom metrics — for any kind of task, hardware or not.
{{< /card >}}

{{< card title="Results exploration" link="/docs/features/explorer/" >}}
Turn results into an interactive dashboard with line, column, scatter, radar and 3D charts, and export publication-ready figures.
{{< /card >}}

</div>
{{< /section-container >}}

## A typical campaign

The features are designed to be chained. A full design space exploration usually
looks like this:

1. Describe the design and its parameters once — [architecture exploration](/docs/features/architecture-exploration/).
2. Validate and benchmark them — [simulation](/docs/features/simulation/).
3. Check that every configuration elaborates — [RTL analysis](/docs/features/analysis/).
4. Implement them — [fmax](/docs/features/rtl_fmax_synthesis/) or [custom-frequency synthesis](/docs/features/rtl_synthesis/).
5. Take the interesting ones further — [place & route](/docs/features/pnr/).
6. Compare and publish — [Explorer](/docs/features/explorer/).

[Workflows](/docs/features/workflows/) run alongside all of it, for everything
that is not synthesis or simulation.

## See also

- [Getting started](/docs/getting-started/) — install, initialize a workspace, core concepts.
- [Configuration file reference](/docs/reference/) — every key of every file.
- [Tutorials](/tutorials/) — hands-on walkthroughs of each feature.
