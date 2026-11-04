---
title: "Accuracy against cost"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 2
description: "Module B: merge the results of simulation and those of synthesis — the accuracy the testbench measured, carried onto the area each synthesis reported — and chart what a decibel costs."
categories: ["Tutorial", "Explorer"]
tags: ["workshop", "derived metrics", "gui", "explorer", "accuracy", "snr"]
featured_image: "/images/features/explorer.svg"
next_tutorials: ["/tutorials/workshop/modules/workflow", "/tutorials/workshop/finale/dse"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| The simulations and syntheses of the common track | 20 min | Simulation and synthesis results merged, and one chart: decibels against area |

Here is the question a signal processing audience actually asks, and the one no
single tool answers: **what does accuracy cost?** The common track left you two
sets of results on the same nine configurations, and neither can answer it on
its own:

- the **simulation** results know the SNR, and nothing about area;
- the **synthesis** results know the area, and nothing about accuracy.

Copying numbers between two spreadsheets is how most of us have been drawing
that chart so far. This module **merges the two result sets** instead: each
synthesis result gets the accuracy its simulation measured, and from then on
the SNR is a metric of the synthesis like any other — chartable against the
area, and something a search can optimize.

The tool for it is a **derived metric**: a metric a result does not hold
itself, but gets from another result, or computes from the ones it has.

> [!IMPORTANT]
> This module needs simulation **and** synthesis results for the same
> configurations: the common track produced both, on your `My_Cordic_*`. With no
> synthesis tool, use the results bundle the organizers provide, which already
> holds both.

Every result the other modules add — the maximum frequencies of [How fast can
it go?](/tutorials/workshop/modules/fmax/), the layouts of [ASIC with open-source
tools](/tutorials/workshop/modules/asic/), the post-route figures of [Place and route
after synthesis](/tutorials/workshop/modules/pnr/) — is merged the same way, with
nothing more to do, before or after this module. The
[finale](/tutorials/workshop/finale/dse/) optimizes the SNR it brings.

## Step 1 — Carry the accuracy onto the synthesis results

In `odatix-gui`: **Configure** → **Derived metrics** (or the address
`/derived_metrics`). The page is empty: the workspace has none yet.

Click **Add new derived metric**. A new card reads **Import from another
result**, **From** **Simulation**: exactly what is needed. Type `snr` over its
provisional name, open the card with its arrow, and set its **Unit** to `dB`.
Then the same for `enob`, in `bits`.

| Name | Type | From | Unit |
|---|---|---|---|
| `snr` | Import from another result | Simulation | `dB` |
| `enob` | Import from another result | Simulation | `bits` |

Leave every other field empty. Click **Save all**, then **Apply to results**:

{{< img src="/images/screenshots/workshop/gui-derived-metrics.png" title="Two derived metrics imported from the simulation, applied to the results" >}}

*Derived metrics updated in 1 results file*: the file of your synthesis tool.
Each of its records now carries the accuracy of the same design:

{{< code lang=yaml filename="results/results_yosys_fpga.yml (width 8, iterations 12)" >}}
  metrics:
    LUT_count: 1945         # from the synthesis
    Worst_Slack: 4.848      # ns, from the synthesis
    snr: 28.66              # dB, from the simulation
    enob: 4.86              # bits, from the simulation
{{< /code >}}

How does a simulation result find *its* synthesis result? By agreeing on
everything they have in common: the architecture, the configuration, and every
parameter domain they both carry — here `WIDTH` and `ITERATIONS`. Nothing had to
be named, matched or keyed by hand. When they do not line up by themselves, the
fields under the arrow of a card — **Pin**, **Ignore Domains**, **Map
Domains**, **Match On** — say how; see [Derived
metrics](/docs/results/derived_metrics/).

> [!NOTE]
> Derived metrics are recomputed over the whole result set at the end of every
> run and by `odatix results`, so they are never stale: every synthesis the
> other modules run gets its `snr` without anyone clicking **Apply** again.

{{< details title="What the page wrote" >}}
{{< code lang=yaml filename="odatix_userconfig/derived_metrics.yml" >}}
derived_metrics:
  snr:
    from: simulation
    unit: dB
  enob:
    from: simulation
    unit: bits
{{< /code >}}

Written by hand, the same file works the same; `odatix results derived` is
**Apply to results** from the terminal.
{{< /details >}}

> [!WARNING]
> If a configuration was simulated **twice** — by two simulators, or by your
> simulation and the shipped one — Odatix refuses to choose between the two
> results and says so. Under the arrow of the card, set **On Multiple Matches**
> to `first`: the testbench is deterministic, so either will do.

## Step 2 — Chart what a decibel costs

In the menu, **Explorer** — or `odatix-explorer` in a terminal. Then:

1. **Scatter**
2. **Data**: keep the file of your synthesis tool (`yosys_fpga` here) only
3. **Axes** → X metric: `LUT count` (`ALM count` with Quartus, `Cell Area` on an
   ASIC flow), Y metric: `snr`
4. **Style** → **Color by**: `WIDTH`

{{< img src="/images/screenshots/workshop/explorer-snr-lut.png" title="snr against LUT count: one point per configuration, synthesized and simulated" >}}

Read the chart from its lower-left corner: every point with another one above
and to its left is a design someone is paying for and getting nothing back. The
rest — the ones nothing beats on both axes at once — are the trade-off, and
there is no single best among them. Here, the three 12-stage designs: the
16- and 24-stage ones of each width are further right **and** lower — more area
for less accuracy, the conclusion of the common track with a price on it. That
staircase is a **Pareto front**, drawn by hand for the last time: the
[finale](/tutorials/workshop/finale/dse/) computes it.

> [!TIP]
> Add `Worst Slack` as the z axis on a **Scatter 3D**, or put everything on
> **Parallel coordinates** — one axis per metric, every configuration a line.
> With four metrics that matter, it is often the chart that makes a room go
> quiet.

## Step 3 — Ask a question of your own

A derived metric can also be computed rather than imported, from metrics the
result already has — imported ones included. Back on **Derived metrics**:

| Name | Type | Operation |
|---|---|---|
| `LUT_per_bit` | Operation on other metrics | `LUT_count / enob` |

**Save all**, **Apply to results**. `LUT_per_bit` is now a metric like any
other: the cost of one effective bit of output, for each design — 127 LUTs per
bit at width 8 and 12 stages, 85 at width 12 — and the whole space can be
ranked by it. Chart it as **Columns** against the configuration, and the chart
ranks the design space by efficiency rather than by size: a different question,
answered with one line and no re-run.

Other things worth two minutes, if the module is going well:

- `latency` imported from the simulation the way `snr` is, then `Latency_ns`
  as the operation `latency * 1000 / meta.frequency` — the real latency of
  each design, which neither the simulation (cycles) nor the synthesis (MHz)
  knows alone.
- A **rule** in the Explorer sidebar: **Filters** → `snr > 40`, which keeps only
  the configurations good enough for your application, and says how many
  survive.

{{< details title="Why this is not a spreadsheet" >}}
Everything in this module is a property of the workspace, not of a chart: the
join is in `derived_metrics.yml`, the metrics are in the result files, and both
are read by the Explorer, by `odatix results` and by an `odatix dse` campaign
alike. Which is what makes the finale possible at all — a search cannot
optimize a number that only exists in your spreadsheet.
{{< /details >}}

## If something did not work

| Symptom | What to do |
|---|---|
| `snr` does not appear on the synthesis results | The simulation and the synthesis must be on the **same** configurations of the **same** architecture — `My_Cordic_sv` for both, say, not one in SystemVerilog and the other in VHDL. |
| **Apply to results** warns that no source result matched | The same cause, and the warning names the record. **Optional**, under the arrow, silences it where it is expected. |
| It refuses to choose between several results | A configuration simulated twice: **On Multiple Matches** → `first`. |
| An operation metric is empty | It needs every metric of its operation on that record: import `enob` before dividing by it. |
| The chart is empty | The axes are metrics *some* records have: keep only the synthesis file under **Data**, and check **Step scope** is `last` under **Filters**. |

## Next

- Your next module: [How fast can it go?](/tutorials/workshop/modules/fmax/), [ASIC with
  open-source tools](/tutorials/workshop/modules/asic/) or [Shape your own design
  space](/tutorials/workshop/modules/design_space/) — their results get `snr` too.
- [Let the search do the work](/tutorials/workshop/finale/dse/) — the front you just
  drew by eye, computed, with `snr` as a genuine objective.
- [Derived metrics](/docs/results/derived_metrics/) — matching, groups, operations.
