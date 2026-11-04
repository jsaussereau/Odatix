---
title: "Explore the results"
date: 2026-11-04
author: "Jonathan Saussereau"
weight: 6
description: "The common track, last part: open Odatix Explorer on the results of the simulation and of the synthesis, and make the charts answer the questions the design was built on."
categories: ["Tutorial", "Explorer"]
tags: ["workshop", "explorer", "charts", "cordic"]
featured_image: "/images/features/explorer.svg"
next_tutorials: ["/tutorials/workshop/modules/fmax", "/tutorials/workshop/modules/accuracy"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| None — the results of the two previous pages | 20 min | The accuracy and the cost of the nine configurations, on charts |

**Odatix Explorer** reads the `results/` directory and turns it into
interactive charts. The pages before this one left two result files there: the
simulation (nine configurations, their SNR), and the synthesis, perhaps still
running (the same nine, their area and timing). This page charts the first
while the second finishes, then puts them side by side.

Every chart here is a question about the design, and the formatting — the
chart type, the colors, the grouping — is what makes the chart answer it.

## Step 1 — Open Odatix Explorer

Odatix Explorer is integrated in the GUI: click **Explorer** in the topbar.

> [!TIP]
> A standalone version can also be run from a terminal:
> {{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Its home page lists the result files and, under **Insights**, the charts it suggests from what the results contain.

The sidebar of a chart page has three tabs: **Plot** (chart type, data, axes, style),
**Filters** and **Save**.

> [!TIP]
> The **Overview** chart type draws every metric of the selection at once: the
> fastest way to see what a result file holds before asking it anything.

## Step 2 — Chart the accuracy

Let's try to answer visually to a first simple question: **does the accuracy come from the width, or from the stages?** 

One metric against one parameter, split by the other — a scatter:

1. Chart type **Scatter**.
2. **Data**: the `simulation` file.
3. **Axes** → x: `WIDTH`, y: `snr`.
4. **Style** → **Color by**: `ITERATIONS`.
 
**The width carries the accuracy, and the extra stages do not.** 
From 4 to 12 bits the SNR goes from about 2 dB to about 50 dB, while adding stages at a
fixed width makes it very slightly *worse*.

{{< details title="What you should see" >}}
{{< img src="/images/screenshots/workshop/gui-sim-explorer-accuracy.png" title="Odatix Explorer: the chart, its axes and its styling in the sidebar" shadow="false" >}}
{{< /details >}}


5. Switch the chart type to **Lines**: same axes, same colors, and the trend now
reads as three lines.

> [!TIP]
> **Save** → **Saved views** stores a chart under a name — sources, axes,
> style, filters — and brings it back in one click. Save this one.

## Step 3 — Chart the latency

Second question: **what sets the latency?** A handful of discrete values calls
for bars, not lines:

1. Chart type **Columns**.
2. **Axes** → x: `ITERATIONS`, y: `latency`.
3. **Style** → **Color by**: `WIDTH`.

Three groups of three bars, and within each group the bars are the same
height: the latency follows the stages only and the width changes nothing. 
As expected, a pipeline of *n* stages takes *n* + 1 cycles.

{{< details title="What you should see" >}}
{{< img src="/images/screenshots/workshop/gui-sim-explorer-latency.png" title="Odatix Explorer: the chart, its axes and its styling in the sidebar" shadow="false" >}}
{{< /details >}}

## Step 4 — Bring the synthesis in

Once the nine syntheses are done, under **Data**, select the file of your tool
(`yosys_fpga` here) and unselect `simulation`: the next charts read metrics
only the synthesis has.

## Step 5 — Chart the cost

Same question as step 2, asked about area: **what does the width cost, and
what do the stages cost?** Deliberately the same chart, with another metric:

1. Chart type **Lines**.
2. **Axes** → x: `WIDTH`, y: `LUT_count` (`ALM_count` with Quartus,
   `Cell_Area` with Design Compiler or Genus).
3. **Style** → **Color by**: `ITERATIONS`.


This time the three lines are far apart: going from 12 to 24 stages doubles
the area at every width, and step 2 showed it buys no accuracy. **Every design
with 16 or 24 stages pays for something it does not get.**

{{< details title="What you should see" >}}
{{< img src="/images/screenshots/workshop/gui-synthesis-explorer-cost.png" title="Odatix Explorer: the chart, its axes and its styling in the sidebar" shadow="false" >}}
{{< /details >}}

## Step 6 — One bar per configuration

A trend chart convinces an engineer; a ranking convinces a room. Put the nine
configurations side by side:

1. Chart type **Columns**.
2. **Axes** → x: `Configuration`, y: `LUT_count`.
3. **Style** → **Color by**: `Target`.

Nine bars, one per configuration — correct, but the labels are long and the
order says nothing.

{{< details title="What you should see" >}}
{{< img src="/images/screenshots/workshop/gui-synthesis-explorer-target.png" title="Odatix Explorer: the chart, its axes and its styling in the sidebar" shadow="false" >}}
{{< /details >}}

Now, still under **Axes**:

4. **Dissociate**: `ITERATIONS`.
5. **Color by**: `ITERATIONS`.
6. **Pattern by**: `Target`.

The dimension leaves the configuration names for the legend: three bars per
remaining name, one color per number of stages, and the doubling of step 5 is
now visible within every group.

{{< details title="What you should see" >}}
{{< img src="/images/screenshots/workshop/gui-synthesis-explorer-target-dissociate.png" title="Odatix Explorer: the chart, its axes and its styling in the sidebar" shadow="false" >}}
{{< /details >}}

> [!NOTE]
> **Dissociate** works on any dimension: it splits a dimension out of the x
> axis into traces of its own. **Color by** colors records without touching
> the x axis; dissociating restructures it.

## Step 7 — Spend a budget

Last question, the one a project actually asks: **say the budget is 3000 LUTs —
which configurations fit?** The **Filters** tab answers without touching the
chart:

1. Chart type **Lines**.
2. **Dissociate**: `None`.
3. **Color by**: `Target`.
4. **Filters** → **Rules** → add a rule: `LUT count` **<** `3000`.
5. **Records outside the rules**: **Dim**.

The rule header counts the records it keeps, and the chart fades the
configurations you cannot afford — on this target, everything with 24 stages
and the widest 16-stage design. Set **Records outside the rules** to
**Highlight** to flip the emphasis, or **Invert** the rules to select the
offenders themselves.

{{< details title="What you should see" >}}
{{< img src="/images/screenshots/workshop/gui-synthesis-explorer-filters.png" title="Odatix Explorer: the chart, its axes and its styling in the sidebar" shadow="false" >}}
{{< /details >}}

The same mechanism checks timing: a rule `Worst Slack` **≥** `0`, inverted and
highlighted, marks the designs that miss their clock. Here it marks none:
every configuration meets 100 MHz with room to spare.

> [!TIP]
> **Save** → **Download image** exports the chart as SVG or PNG; **Image
> background** → *White* makes it ready for a slide or a paper, whatever the
> theme on screen. **Download CSV** exports the data behind it.

## What the nine points actually say

Read the charts together and they all point the same way: at every width, the
best design is the one with the **fewest** stages — and 12 is the smallest
value the sweep contains. The optimum sits on the edge of the design space.

Look back at the values typed on [the first
page](/tutorials/workshop/common/describe/#step-4--describe-what-changes): they
were a guess, and not a good one. Every configuration has at least as many
stages as it has bits, and a CORDIC stage refines the angle by about one bit —
past the width, a stage can only truncate. Of the nine runs, six went to
points the other three dominate.

An optimum on the edge of the space is not an answer; it is a hint that the
space is in the wrong place. The next step is not a better guess, it is **more
data**:

- **More values.** Try to simulation and synthesize more combinations of widths and more stages, and chart them all together.
- **More targets.** [Step 2 of the
  synthesis](/tutorials/workshop/common/synthesis/#step-2--select-your-targets)
  enables more than one part: each gets its own results, and **Color by**:
  `Target` puts them on one chart.
- **A search.** Once the space outgrows what a sweep can afford, the finale
  [lets the search do the work](/tutorials/workshop/finale/dse/). This is actually the finale of the workshop, keep this for the end!
## The chart this page cannot draw

Accuracy on one page, cost on another. However, *decibels against LUTs*, on one
chart, needs the simulation and the synthesis results **merged**: that is the
module [Accuracy against cost](/tutorials/workshop/modules/accuracy/), and it
takes your results as they are.

## Next

You have described a design, checked it, synthesized and simulated nine
configurations of it, and read the trade-off on charts. Pick your modules —
[they are independent of each
other](/tutorials/workshop/#how-the-session-is-organized):

- [How fast can it go?](/tutorials/workshop/modules/fmax/) — maximum frequency
- [ASIC with open-source tools](/tutorials/workshop/modules/asic/) — LibreLane, sky130
- [Shape your own design space](/tutorials/workshop/modules/design_space/) — no EDA tool
  needed
