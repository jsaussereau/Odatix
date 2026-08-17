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

{{< doc-cards cols="2" >}}
{{< doc-card title="Architecture exploration" link="/docs/features/architecture-exploration/" icon="explore" accent="#2563eb" cta="Explore architectures" >}}
Define parametrizable designs once and let Odatix generate every configuration — with parameter domains and automatic configuration generation.
{{< /doc-card >}}

{{< doc-card title="RTL analysis" link="/docs/features/analysis/" icon="inspect" accent="#f59e0b" cta="Analyze your RTL" >}}
Elaborate every configuration with one or several tools before synthesis, and catch missing sources, black boxes and lint issues early.
{{< /doc-card >}}

{{< doc-card title="RTL synthesis" link="/docs/features/rtl_synthesis/" icon="chip" accent="#7c3aed" cta="Synthesize everything" >}}
Run synthesis for every configuration on FPGA and ASIC tools, and collect area, resource, power and timing metrics automatically.
{{< /doc-card >}}

{{< doc-card title="Fmax synthesis" link="/docs/features/rtl_fmax_synthesis/" icon="frequency" accent="#0ea5e9" cta="Find each Fmax" >}}
Automatically find the maximum operating frequency of any design through a parallel binary search on the clock constraint.
{{< /doc-card >}}

{{< doc-card title="Place & route" link="/docs/features/pnr/" icon="route" accent="#0d9488" cta="Go to layout" >}}
Feed the synthesized netlist from one EDA tool into a PNR tool to implement your design up to layout and signoff, and get post-route metrics.
{{< /doc-card >}}

{{< doc-card title="Simulation & validation" link="/docs/features/simulation/" icon="waves" accent="#16a34a" cta="Validate your design" >}}
Validate and benchmark every design configuration with the simulator of your choice.
{{< /doc-card >}}

{{< doc-card title="Custom workflows" link="/docs/features/workflows/" icon="workflow" accent="#ea580c" cta="Build a workflow" >}}
Orchestrate arbitrary task pipelines with dependencies, progress tracking and custom metrics — for any kind of task, hardware or not.
{{< /doc-card >}}

{{< doc-card title="Results exploration" link="/docs/features/explorer/" icon="chart" accent="#db2777" cta="Explore your results" >}}
Turn results into an interactive dashboard with line, column, scatter, radar and 3D charts, and export publication-ready figures.
{{< /doc-card >}}
{{< /doc-cards >}}

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

<div class="not-prose docs-links">
  <a class="docs-link" href="/docs/getting-started/">
    <span class="docs-link__title">Getting started</span>
    <span class="docs-link__text">Install, initialize a workspace, core concepts.</span>
  </a>
  <a class="docs-link" href="/docs/reference/">
    <span class="docs-link__title">Configuration file reference</span>
    <span class="docs-link__text">Every key of every file, exhaustively.</span>
  </a>
  <a class="docs-link" href="/tutorials/">
    <span class="docs-link__title">Tutorials</span>
    <span class="docs-link__text">Hands-on walkthroughs of each feature.</span>
  </a>
  <a class="docs-link" href="/install/eda_tools/">
    <span class="docs-link__title">Supported EDA tools</span>
    <span class="docs-link__text">Which tools drive which feature.</span>
  </a>
</div>
