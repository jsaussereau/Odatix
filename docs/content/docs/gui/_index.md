---
title: "Graphical User Interface (GUI)"
description: "The daemon, the Job Monitor, Odatix Explorer, and how to run them on a remote server."
weight: 3
---

# Graphical User Interface (GUI)

Odatix has a graphical application, `odatix-gui`, covering the whole workflow: configuring the workspace, launching jobs, tracking them in the [Job Monitor](/docs/sessions/), and visualizing results in **Odatix Explorer**. Jobs are scheduled by a background **daemon**, shared with the command line.

{{< toc >}}

## Two applications?

`odatix-explorer` is **included in** `odatix-gui`: when you run the GUI, the results dashboard is one of its pages, alongside the workspace configuration and the Job Monitor. You do not need to start anything else to explore your results.

`odatix-explorer` also exists as a **standalone application**. It serves the exploration interface *only* — the same charts and exports, without the workspace configuration and job-launching pages. This is what you want when you publish results to an audience, for instance on a website or an internal server: visitors can browse and export the results, but they cannot modify the workspace configuration or launch jobs.

| | `odatix-gui` | `odatix-explorer` |
|---|---|---|
| Configure the workspace | ✅ | ❌ |
| Launch and monitor jobs | ✅ | ❌ |
| Explore results | ✅ | ✅ |
| Typical use | your own machine | shared/public result hosting |

See **[Hosting on a server](/docs/gui/host_server/)** for how to expose either one over the network.

## In this section

{{< doc-cards cols="3" >}}
{{< doc-card title="Odatix GUI" link="/docs/gui/" icon="window" accent="#0284c7" >}}
The GUI application, with workspace configuration, job monitor and results dashboard.
{{< /doc-card >}}

{{< doc-card title="Odatix Explorer" link="/docs/gui/explorer/" icon="chart" accent="#0284c7" >}}
The results dashboard, with charts, exports and interactive filtering.
{{< /doc-card >}}

{{< doc-card title="Hosting a server" link="/docs/gui/host_server/" icon="server" accent="#0284c7" >}}
How to expose Odatix GUI and Odatix Explorer over the network.
{{< /doc-card >}}
{{< /doc-cards >}}
