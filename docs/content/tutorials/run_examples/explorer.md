---
title: "Explore Your Results"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 7
description: "Open Odatix Explorer and compare your synthesis and simulation results with interactive charts."
layout: "doc-features"
categories: ["Tutorial", "Explorer"]
tags: ["explorer", "charts", "results"]
featured_image: "/images/features/explorer.svg"
---

{{< toc >}}

Once you have run a synthesis or simulation (see the [Fmax synthesis](/tutorials/run_examples/fmax_synthesis/) tutorial), it is time to make sense of the numbers. **Odatix Explorer** is a local web app that turns your results into interactive charts.

## Step 1 — Make sure results are exported

Run commands export automatically by default. If you used `-e`/`--noexport`, export now:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results
{{< /code >}}

## Step 2 — Launch Explorer

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Explorer starts a local server, opens your browser, and loads the `results/` directory.

![The Explorer Overview page: every metric of the selected results charted at once](/images/screenshots/explorer-overview.png)

## Step 3 — Pick a chart

Choose the chart that fits your question:

| You want to… | Use |
|--------------|-----|
| See a trend across an ordered parameter (Fmax vs data width) | **Line** |
| Compare configurations side by side | **Column** |
| Compare a metric at several frequencies | **Column (per frequency)** |
| Correlate two metrics (power vs Fmax) | **Scatter** |
| Correlate three metrics | **3D scatter** |
| Profile a few configurations across many metrics | **Radar** |
| Get a broad summary at a glance | **Overview** |

## Step 4 — Filter and compare

Use the controls to pick which designs, configurations and targets to show, and which metric to plot. Comparisons update instantly, so you can quickly narrow down to the best design point for your constraints.

## Step 5 — Export a figure

Every chart exports directly:

- **Vector**: SVG — perfect for papers and slides.
- **Raster**: PNG, JPEG, WEBP — ready for a report or README.
- **Themes**: switch appearance (including a dark theme) to match your document.

## Running Explorer on a server?

If your results are on a remote machine, see [Hosting on a server](/docs/gui/host_server/) for SSH tunneling and network access.

## Next steps

- **Feature** — [Interactive results exploration](/docs/features/explorer/).
- **Reference** — [Metrics files](/docs/reference/metrics/) — what gets extracted and charted · [Commands](/docs/commands/)
- **Guides** — [Odatix Explorer](/docs/gui/explorer/) (every option) · [Results & export](/docs/results/) · [Derived metrics](/docs/results/derived_metrics/), to compute what you actually want to plot.
