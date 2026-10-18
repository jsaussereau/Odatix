---
title: "Interactive Results Exploration"
description: "Odatix Explorer turns your synthesis, simulation, analysis and workflow results into an interactive dashboard for comparison and publication."
layout: "doc-features"
badge: "Analysis"
badgeColor: "#db2777"
cta: true
weight: 8
aliases:
  - /docs/features/rtl_analysis/
features:
  - title: "Interactive dashboard"
    description: "A local web app to slice, filter and compare results across designs, configurations and targets."
  - title: "Eight chart types"
    description: "Lines, columns, scatter, 3D scatter, radar, parallel coordinates, overview and table, plus a page for design space explorations."
  - title: "Metric correlation"
    description: "Plot any metric against any other to reveal trade-offs — power vs Fmax, area vs throughput, and more."
  - title: "Publication-ready export"
    description: "Export figures in vector (SVG) or raster (PNG, JPEG, WEBP) formats, with customizable themes."
---

## Make sense of your results

Running hundreds of configurations produces a lot of numbers. **Odatix Explorer**
is the tool that makes them useful: an interactive, web-based dashboard that
reads your exported results and lets you compare architectures visually — no
spreadsheets required.

It is where every other feature converges. Synthesis figures, simulation
benchmarks, analysis verdicts and workflow metrics are all ordinary records in
the same result files, so a single chart can put them side by side.

![The Explorer Overview page: every metric of the selected results charted at once](/images/screenshots/explorer-overview.png)

## When you need it

- **Picking a design point.** Which configuration gives the best Fmax per LUT? A
  scatter chart answers in one look what a table hides.
- **Understanding a trend.** Fmax against data width, area against memory depth —
  a line chart over a parameter domain shows where a design stops scaling.
- **Comparing tools, flows or targets.** The same design synthesized with two
  flows, or on two FPGAs, plotted on the same axes.
- **Producing figures.** A paper, a slide deck or a README needs vector charts
  that stay crisp — export them straight from the chart you are looking at.
- **Sanity-checking a campaign.** The overview and RTL analysis dashboards make a
  configuration that failed, or one whose numbers look impossible, obvious.

## A chart for every question

| Chart | Best for |
|-------|----------|
| **Line** | Trends of a metric across an ordered parameter (e.g. Fmax vs data width) |
| **Column** | Direct side-by-side comparison of configurations |
| **Scatter** | Correlation between two metrics (e.g. power vs Fmax) |
| **3D scatter** | Correlation between three metrics (e.g. LUTs, registers, Fmax) |
| **Radar** | Multi-metric profile of a few configurations at a glance |
| **Parallel coordinates** | Several metrics of many configurations, one axis per metric |
| **Overview** | A comparative summary across many metrics at once |
| **Table** | Every record of the selection, sortable and filterable |

To compare operating frequencies, pick **Color by: Frequency** on a line or
column chart. When several records of a trace fall on the same x value (one
record per step of a job, one record per row of a `multiple` metric), Explorer
splits the trace by the dimension that tells them apart and names it in the
legend, so no record is hidden. The **Exploration** page follows the Pareto
front and the progress of `odatix dse` campaigns (designs evaluated, measured,
and reused from results already on disk), and **RTL Analysis** shows the
verdicts of `odatix analyze`.

![The same results as lines, columns, radar and scatter](/images/screenshots/explorer-charts.png)

Every chart can be exported directly: **SVG** for papers and slides, **PNG /
JPEG / WEBP** for reports and READMEs, with a theme (dark included) to match your
document. The data behind a chart downloads as CSV. Nothing leaves your machine:
the chart toolbar has no "share" button that would upload a figure to a
third-party service.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | Every parameter domain becomes an axis: charts are grouped and coloured by the parameters you defined. |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) | Fmax across configurations is the chart Odatix was built for. |
| [Place & route](/docs/features/pnr/) | Put synthesis estimates and post-route reality side by side. |
| [Simulation](/docs/features/simulation/) | Benchmark numbers live next to area and timing, so throughput-per-LUT is one chart away. |
| [Workflows](/docs/features/workflows/) | Any metric a workflow extracts is chartable and correlatable like the rest. |
| [Derived metrics](/docs/results/derived_metrics/) | Compute what you actually want to plot — runtime, energy, efficiency — from metrics several job types produced. |

## Using it

### From the CLI

Results are exported automatically at the end of each run, into `results/`.
Explorer just reads them:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer                    # open the dashboard on ./results
$ odatix-explorer -i other_results   # read a different directory
{{< /code >}}

If a run was launched with `-e/--noexport`, or you changed a metric definition,
re-export without re-running anything:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results synth     # synthesis and place & route results
$ odatix results sim       # simulation results
$ odatix results workflow  # workflow results
$ odatix results derived   # apply derived_metrics.yml
{{< /code >}}

What lands in `results/` and in which file is documented in
[Results & export](/docs/results/); what gets extracted, in
[Metrics files](/docs/reference/metrics/).

### From the GUI

`odatix-gui` → **Explore Results** opens the same dashboard inside the full
interface, with its chart pages in the top bar — so configuring, launching,
monitoring and exploring all happen in one place. Charts, filters and export
options are identical; `odatix-explorer` is simply the standalone way in.

Both can be [hosted on a server](/docs/gui/host_server/) and reached from your
workstation.

## Where to go next

- **Tutorial** — [Explore your results](/tutorials/run_examples/synthesis/#step-6--explore-the-results).
- **Reference** — [Metrics files](/docs/reference/metrics/) · [Commands](/docs/commands/)
- **Guides** — [Odatix Explorer](/docs/gui/explorer/) · [Results & export](/docs/results/) · [Derived metrics](/docs/results/derived_metrics/)
