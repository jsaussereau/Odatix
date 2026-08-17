---
title: "Documentation"
description: "The complete reference for Odatix — concepts, configuration, commands and the graphical tools."
toc: false
---

<!-- ## Start here -->

The documentation is organized in three layers, and every page links to its
counterparts in the other two. Start with a **feature** if you are wondering
what Odatix can do, a **tutorial** if you want to get something running, and the
**reference** when you know what you need and want the exact key.

{{< doc-cards cols="2" >}}
{{< doc-card title="Features" link="/docs/features/" icon="compass" accent="#2563eb" badge="What it does" cta="Tour the features" >}}
A high-level tour of what Odatix does — architecture exploration, synthesis, Fmax search, simulation, workflows and results exploration.
{{< /doc-card >}}

{{< doc-card title="Getting started" link="/docs/getting-started/" icon="rocket" accent="#2563eb" badge="Hands on" cta="Run your first job" >}}
Install Odatix, initialize a workspace, and understand the core concepts — designs, configurations, targets and jobs.
{{< /doc-card >}}

<!-- {{< doc-card title="Configuration reference" link="/docs/reference/" icon="book" accent="#a21caf" badge="Exhaustive" cta="Open the reference" >}}
Every YAML key Odatix reads, and how settings are resolved and overridden across files.
{{< /doc-card >}} -->
{{< /doc-cards >}}

## By topic

{{< doc-cards cols="3" >}}

{{< doc-card title="Graphical User Interface" link="/docs/gui/" icon="window" accent="#0284c7" >}}
Odatix GUI, Odatix Explorer, and how to host them on a server.
{{< /doc-card >}}

{{< doc-card title="Configurations" link="/docs/configurations/" icon="sliders" accent="#425ad6" >}}
Define parametrizable designs, parameter domains and automatic configuration generation.
{{< /doc-card >}}

{{< doc-card title="Sessions and job monitor" link="/docs/sessions/" icon="activity" accent="#059669" >}}
Job execution in daemon sessions, terminal and graphical job monitors.
{{< /doc-card >}}

{{< doc-card title="Tools and flows" link="/docs/tools/" icon="wrench" accent="#fbbf24" >}}
Add your own EDA tools to Odatix, and your own ways of running the ones it ships.
{{< /doc-card >}}

{{< doc-card title="Results & export" link="/docs/results/" icon="chart" accent="#db2777" >}}
How results are stored, exported, and consumed by Odatix Explorer.
{{< /doc-card >}}

{{< doc-card title="Examples" link="/docs/examples/" icon="blocks" accent="#65a30d" >}}
Ready-to-run examples shipped with Odatix — six architectures, from counter to CORDIC, and nine workflows, each isolating one mechanism.
{{< /doc-card >}}

{{< doc-card title="Python API" link="/docs/python_api/" icon="code" accent="#006dad" >}}
Programmatic access to Odatix functionality in Python.
{{< /doc-card >}}

{{< doc-card title="Configuration file reference" link="/docs/reference/" icon="book" accent="#a21caf" >}}
Every configuration file Odatix reads, and every key it accepts.
{{< /doc-card >}}

{{< doc-card title="Commands reference" link="/docs/commands/" icon="terminal" accent="#475569" >}}
Every `odatix` and `odatix-explorer` command, with options and examples.
{{< /doc-card >}}

{{< doc-card title="Troubleshooting" link="/docs/troubleshooting/" icon="lifebuoy" accent="#be123c" >}}
Diagnose missing tools, invalid settings, daemon sessions, exports and empty Explorer dashboards.
{{< /doc-card >}}
{{< /doc-cards >}}
<!-- 
## See also

<div class="not-prose docs-links">
  <a class="docs-link" href="/install/">
    <span class="docs-link__title">Install Odatix</span>
    <span class="docs-link__text">Pick where the package comes from, then check the prerequisites.</span>
  </a>
  <a class="docs-link" href="/install/eda_tools/">
    <span class="docs-link__title">Supported EDA tools</span>
    <span class="docs-link__text">Vivado, Design Compiler, Genus, OpenLane, Verilator, GHDL…</span>
  </a>
  <a class="docs-link" href="/tutorials/">
    <span class="docs-link__title">Tutorials</span>
    <span class="docs-link__text">Hands-on, step-by-step guides you can follow in one sitting.</span>
  </a>
  <a class="docs-link" href="/faq/">
    <span class="docs-link__title">FAQ</span>
    <span class="docs-link__text">The questions people ask before running their first jobs.</span>
  </a>
</div> -->
