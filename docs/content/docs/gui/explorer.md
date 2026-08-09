---
title: "Odatix Explorer"
description: "The interactive web dashboard for exploring, comparing and exporting your results."
weight: 2
---

# Odatix Explorer

**Odatix Explorer** is a local web application that reads your exported results and turns them into interactive charts. It is the fastest way to compare architectures and produce publication-ready figures.

{{< toc >}}

## Launch it

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Explorer starts a local server, opens your browser, and loads the results from the `results/` directory by default.

![The Explorer Overview page: every metric of the selected results charted at once](/images/screenshots/explorer-overview.png)

## Chart types

| Chart | Best for |
|-------|----------|
| **Line** | Trends of a metric across an ordered parameter (Fmax vs data width). |
| **Column** | Direct side-by-side comparison of configurations. |
| **Column (per frequency)** | How a metric such as power evolves at different operating frequencies. |
| **Scatter** | Correlation between two metrics (power vs Fmax). |
| **3D scatter** | Correlation between three metrics (LUTs, registers, Fmax). |
| **Radar** | Multi-metric profile of a few configurations. |
| **Table** | The raw records behind the charts, sortable and filterable. |
| **Overview** | A comparative summary across many metrics at once. |

Alongside the charts, the **RTL Analysis** dashboard reports the pass/warning/error status of every analyzed configuration — see [RTL analysis](/docs/features/analysis/).

## Export figures

Every chart can be exported directly from the interface:

- **Vector**: SVG.
- **Raster**: PNG, JPEG, WEBP.
- **Themes**: switch appearance (including a dark theme) to match your document.

## Options

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer --input results --port 8052
$ odatix-explorer --network            # expose on the local network
$ odatix-explorer --nobrowser --theme odatix_dark
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `-i`, `--input` | Results directory (default: `results`). |
| `-n`, `--network` | Expose the server on the local network. |
| `-p`, `--port` | Preferred HTTP port. |
| `-B`, `--nobrowser` | Do not open the browser automatically. |
| `-T`, `--theme` | Force a specific app theme (same themes as the Odatix GUI). |
| `-N`, `--normal_term_mode` | Do not switch terminal mode. |
| `--safe_mode` | Keep running on internal errors. |

## See also

- [The Odatix GUI](/docs/gui/app/) — Explorer is also reachable from the full interface.
- [Hosting on a server](/docs/gui/host_server/) — run Explorer remotely.
- [Results & export](/docs/results/) — how the data Explorer reads is produced.
- Feature: [Interactive results exploration](/docs/features/explorer/).
