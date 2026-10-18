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

Explorer starts a local server, opens your browser, and loads the results from the `results/` directory by default. The home page lists the result files, then **Insights**: charts Explorer suggests from what your results contain, the best place to start. Chart pages open on the most recently written result file.

![The Explorer Overview page: every metric of the selected results charted at once](/images/screenshots/explorer-overview.png)

## Chart types

| Chart | Best for |
|-------|----------|
| **Lines** | Trends of a metric across an ordered parameter (Fmax vs data width). |
| **Columns** | Direct side-by-side comparison of configurations. |
| **Scatter** | Correlation between two metrics (power vs Fmax). |
| **Scatter 3D** | Correlation between three metrics (LUTs, registers, Fmax). |
| **Radar** | Multi-metric profile of a few configurations. |
| **Parallel coordinates** | Several metrics of many configurations, one axis per metric. |
| **Overview** | A comparative summary across many metrics at once. |
| **Table** | The raw records behind the charts, sortable and filterable. |

To compare operating frequencies, pick **Color by: Frequency** on a lines or
columns chart.

Alongside the charts, two pages report on whole campaigns:

- **RTL analysis** — the pass/warning/error status of every analyzed configuration, see [RTL analysis](/docs/features/analysis/).
- **Exploration** — the `odatix dse` campaigns: the Pareto front, the number of design points evaluated and measured, and of those **reused** (results already on disk, taken instead of being run again, and not counted in the budget), the progress batch after batch and the failures. See [Design space exploration](/docs/reference/dse/).

### Several records at the same x

Lines, columns and radar charts draw one value per x in each trace. When
several records of a trace share an x value — one record per step of a job
split into steps, one record per row of a `multiple` metric — Explorer splits
the trace by the dimension that tells them apart (`Step`, `EBNO`, `flow`...)
and names it in the legend (`EBNO: 2.0`), so that every record is drawn. Those
traces take their own colors, or their own symbols when you chose **Color by**
yourself. Two different series never look the same: when the color and symbol
dimensions do not tell two traces apart (two frequencies of one design, say),
the dimensions that do are added to the symbols. By default **Color by** is the
first of architecture, workflow, source, frequency and target that varies.
If nothing at all tells two records apart, the chart says how many
are not drawn; the **Table** page lists them.

Scatter, parallel coordinates and table draw every record as it is.

## The sidebar

The sidebar has three tabs.

**Plot**
: The chart type, then **Data** (the result files to read, with the time they
  were loaded and a ⟳ button to reload them now), **Axes** (x, y and z, the
  order of the x axis, the dimensions to dissociate into separate traces),
  **Style** (color by, symbol by, legend grouping and order, palette, plot
  theme) and **Display** (legend, title, lines, log scales, axes from zero...).

**Filters**
: **Rules** keep the records whose metrics meet a condition (`LUT_count < 1000`),
  and say how many records they keep. Below, one checklist per dimension
  (architecture, target, frequency, step scope...) hides values. By default
  only the last step of each job is shown (**Step scope**: last): check
  `intermediate` to see the other steps too.

**Save**
: **Export** sets the image format and background of the exported image;
  **Download image** saves it, and **Download CSV** saves the data the chart
  shows (without the internal `_` columns, units in the headers).
  **Saved views** stores the whole display state (sources, chart type, axes,
  style, filters and rules) under a name, and restores it from the list.

### Saved views

A view is a JSON file in `<results>/explorer_views/`: copy it next to another
result directory to share it. Saved views also appear as cards on the Explorer
home page. Saving under the name of an existing view asks first: the first
click says the view exists, a second click replaces it.

### Data reload

Explorer watches its result directory: a run that writes new records, or an
`odatix results` that re-exports them, shows up within a few seconds without
reloading the page. The ⟳ button of the **Data** section forces it.

## Export figures

Every chart can be exported directly from the interface:

- **Vector**: SVG.
- **Raster**: PNG, JPEG, WEBP.
- **Background** (**Save** tab → **Image background**): *Transparent* keeps the
  text colors of the app theme (light text in a dark theme), *White* draws dark
  text on white whatever the theme, ready for a document or a slide, and
  *Theme* paints the theme background in, as on screen. The chart on screen
  already shows the chosen background.
- **Download image** in the **Save** tab saves the chart, like the camera
  button of the chart toolbar.
- **Data**: **Download CSV** in the **Save** tab.

The chart toolbar has no "share" button: nothing is ever uploaded to Plotly or
any other service.

## Options

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer --input results --port 8052
$ odatix-explorer --network --read-only  # expose on the local network, views read-only
$ odatix-explorer --nobrowser --theme odatix_dark
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `-i`, `--input` | Results directory (default: the `result_path` of the workspace settings file, else `results`). |
| `-c`, `--config` | Workspace settings file that gives the results directory (default: `odatix.yml`). |
| `-n`, `--network` | Expose the server on the local network. |
| `-p`, `--port` | HTTP port. A port given with `-p` must be free: if it is taken, Explorer stops with an error instead of moving elsewhere. Without `-p`, Explorer takes 8052, or the next free port, and prints the address it took. |
| `-B`, `--nobrowser` | Do not open the browser automatically. |
| `-T`, `--theme` | Default theme for browsers without a saved choice (same themes as the Odatix GUI). |
| `--read-only` | Nobody can save a view on the server. Recommended with `--network`. |
| `-N`, `--normal-term-mode` | Do not switch terminal mode. |
| `--safe-mode` | Keep running on internal errors. |

## See also

- [The Odatix GUI](/docs/gui/app/) — Explorer is also reachable from the full interface.
- [Hosting on a server](/docs/gui/host_server/) — run Explorer remotely.
- [Results & export](/docs/results/) — how the data Explorer reads is produced.
- Feature: [Interactive results exploration](/docs/features/explorer/).
