---
title: "Graphical User Interface (GUI)"
description: "The daemon, the Job Monitor, Odatix Explorer, and how to run them on a remote server."
weight: 7
---

# Graphical User Interface (GUI)

Odatix has one graphical application, `odatix-gui`, covering the whole workflow: configuring the workspace, launching jobs, tracking them in the **Job Monitor**, and visualizing results in **Odatix Explorer**. Jobs are scheduled by a background **daemon**, shared with the command line.

{{< toc >}}

## The execution model at a glance

{{< code lang=text filename="How a run flows" >}}
 odatix fmax ─► enqueue jobs in the daemon ─► Job Monitor (live progress & logs)
                                                     │
                                                 results/
                                                     │
 odatix-explorer ◄──────────────── interactive charts & export
{{< /code >}}

Every `fmax`, `synth`, `sim` and `workflow` run enqueues jobs into a **daemon session**. By default Odatix attaches the Job Monitor immediately; with `--detach` it returns to the shell and you attach later.

## Two applications, one Explorer

Odatix Explorer is **included in `odatix-gui`**: when you run the GUI, the results dashboard is one of its pages, alongside the workspace configuration and the Job Monitor. You do not need to start anything else to explore your results.

`odatix-explorer` also exists as a **standalone application**. It serves the exploration interface *only* — the same charts and exports, without the workspace configuration and job-launching pages. This is what you want when you publish results to an audience, for instance on a website or an internal server: visitors can browse and export the results, but they cannot modify the workspace configuration or launch jobs.

| | `odatix-gui` | `odatix-explorer` |
|---|---|---|
| Explore results | ✅ | ✅ |
| Configure the workspace | ✅ | ❌ |
| Launch and monitor jobs | ✅ | ❌ |
| Typical use | your own machine | shared/public result hosting |

See **[Hosting on a server](/docs/gui/host_server/)** for how to expose either one over the network.

## In this section

- **[The Odatix GUI](/docs/gui/app/)** — the application itself: configuring a workspace and launching jobs from the browser.
- **[Job Monitor & sessions](/docs/gui/monitor/)** — track parallel jobs, and manage detached daemon sessions.
- **[Odatix Explorer](/docs/gui/explorer/)** — the interactive results dashboard and its options.
- **[Hosting on a server](/docs/gui/host_server/)** — run the monitor and Explorer on a remote machine and access them over the network.
