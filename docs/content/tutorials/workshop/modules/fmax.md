---
title: "How fast can it go?"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 1
description: "Module A: let Odatix find the maximum frequency of every configuration with the synthesis tool you have, FPGA or ASIC, then compare synthesis strategies and write one of your own."
categories: ["Tutorial", "Fmax"]
tags: ["workshop", "fmax", "vivado", "quartus", "design compiler", "genus", "yosys", "nextpnr", "fpga", "flows"]
featured_image: "/images/features/fmax-synthesis.svg"
next_tutorials: ["/tutorials/workshop/modules/accuracy", "/tutorials/workshop/modules/asic"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Yosys + nextpnr, or Vivado, Quartus, Design Compiler, Genus | 30–40 min | The maximum frequency of three configurations, the cost of all nine |

A simulation says whether the design is right. This module says how fast it
runs — and it does so without anyone writing a timing constraint, because
finding the maximum frequency of a design is a search, and searches are what
Odatix automates.

An **fmax synthesis** is launched exactly like the [fixed-frequency synthesis
of the common track](/tutorials/workshop/common/synthesis/): the same tool
cards, the same target page, the same monitor. What changes is the question —
not *what does it look like at 100 MHz*, but *how far can the clock go*.

The page is written for **Yosys + nextpnr**, from the [OSS CAD
Suite](/install/oss_cad_suite/): free, and the same on every system. Every step
works with Vivado, Quartus, Design Compiler or Genus too — click the card of
yours instead, and the results of all of them land on the same charts.

## Step 1 — Choose the tool and strategy

Click on **Run** → **Fmax synthesis**, then the card of your tool. As for the
fixed-frequency synthesis, each line of a card is a **strategy**; take
**Standard**.

> [!IMPORTANT]
> Whichever tool it is, it has to work in your terminal before Odatix can drive
> it: Odatix runs the executable the way you would. For Quartus, check
> `tool_install_path` in its target file instead.

> [!NOTE]
> An fmax search of Design Compiler or Genus *is* a synthesis, with no place
> and route after it: there is no step to stop at. 

## Step 2 — Select your target

Same as [the synthesis of the common
track](/tutorials/workshop/common/synthesis/#step-2--select-your-targets).

## Step 3 — Launch the search

An fmax search looks for the fastest clock between two bounds, and a narrower
range is a shorter search. The run page sets both the bounds and the selection:

1. You can keep default bounds, or override them with the **Override bounds** switch. 
2. **Maximum number of parallel jobs**: *same as before*.
3. Switch on your architecture
4. **Run jobs**, then **Start**.

> [!NOTE]
> With the override off, each architecture searches between its own bounds:
> the **Synthesis settings** of its page under **RTL architectures**
> (`fmax_synthesis` in its `_settings.yml`). Your architecture has none yet,
> so the search would start from the 1–1000 MHz defaults and waste iterations.


### What it is doing

With Vivado, Quartus, Design Compiler or Genus, each job is a **binary search**
on the clock period. Odatix synthesizes the configuration at a frequency, reads
the slack, and picks the next frequency from it, between the bounds of step 3.
nextpnr shortens the search: it times the routed design and says the frequency
it reaches, so a Yosys + nextpnr job routes the design at the lower bound, then
again at the frequency the first run reached. One number per configuration
comes out of several synthesis runs, and no constraint file was written by
hand. In the monitor, the log of a selected job shows the search narrowing
down, frequency after frequency.

> [!IMPORTANT]
> **Why it is so much faster with Yosys + nextpnr.** A binary search runs a
> whole synthesis per frequency it tries — six to ten of them — and each only
> answers *met* or *missed*. The Yosys + nextpnr job synthesizes **once**: the
> netlist does not depend on the clock. Then it places and routes **twice**
> (three times with the `timing` strategy), and nextpnr reports the frequency
> the routed design actually reaches, read on its critical path — so there is
> nothing to search for. Yosys and nextpnr are also light: a few seconds of
> synthesis and a few tens of seconds of routing on this design.
>
> The price: the result is the fmax of *one* placement, not a bound narrowed
> down run after run. Another `seed` or one more pass can move it by a few
> percent — harmless when comparing configurations with each other, as here.

The figures of the ECP5 are those of a small Lattice FPGA, lower than a recent
AMD or Intel part: compare configurations with each other, not with your
neighbour's Vivado.


## Step 4 — The cost of the whole space, for free

A search answers *how fast can it go*, and pays for the answer. The
**fixed-frequency synthesis** of [the common
track](/tutorials/workshop/common/synthesis/) asked a different question —
*what does it look like at 100 MHz* — and cost one synthesis per design instead
of a series. Its nine results, area and slack included, are already in
`results/`: this module reuses them as they are, and so does the
[finale](/tutorials/workshop/finale/dse/).

If you skipped the common track's synthesis, run it now — nine designs, one
synthesis each, about two minutes with Yosys + nextpnr. This is how to get a
cost for the **whole** design space inside a workshop slot, with the fmax
searches of step 3 giving the speed of the few points worth knowing it for.

## Step 5 — Read the results

Click **Explorer** in the topbar, and build the chart of the module:

1. Chart type **Lines**.
2. **Data**: the file of your tool.
3. **Axes** → x: `WIDTH`, y: `Fmax`.
4. **Style** → **Color by**: `Target`.

Then change y to `LUT_count` (`ALM_count` with Quartus, `Cell_Area` with Design
Compiler or Genus), and the trade-off appears in full: the stages that [bought
no accuracy](/tutorials/workshop/common/explore/#step-2--chart-the-accuracy)
are plainly visible in the area, and they cost latency on top.

The fmax searches and the fixed-frequency syntheses of one tool land in the
same file, and Explorer reads every file of `results/` at once: if your
neighbour ran another tool, **Color by**: `tool` puts both on the same chart.

## Step 6 — Compare synthesis strategies

Same design, same target, a different way of synthesizing it. Each strategy
line of a tool card is a **flow**, and each flow runs in its own work
directory, so they never overwrite one another. Compare them at a fixed
frequency, so that one strategy costs one synthesis per design rather than a
search:

1. Click on **Run** → **Fixed-frequency synthesis**, then, on the card of
   **Yosys + nextpnr**, the `abc9` line (timing-driven mapping).
2. **Run jobs**, then **Start**.
3. Do it again with the `timing` line (ABC9 and nextpnr ripping up critical
   routes).

> [!TIP]
> Using the `Session` dropdown, you can run new jobs in an existing session. It will be added to the queue. This is useful to compare different strategies or tools without having to wait for the first one to finish.

With another tool, take its own lines: `performance` and `area` with Vivado or
Quartus, `ultra_timing` and `ultra_area` with Design Compiler, `timing` and
`area` with Genus.

In Explorer, **Style** → **Color by**: `flow` puts them on the same chart. The
flow each result came from is recorded with it, so this comparison needs no
bookkeeping of yours. On a design this small, do not expect a large gap: the
LUT counts of the three strategies come within a few LUTs of one another, and
that is a result too — a strategy is worth what it changes on *your* design.

> [!NOTE]
> This is also the first thing the [finale](/tutorials/workshop/finale/dse/)
> searches automatically: a strategy is one more axis of the design space, not
> a different project.

## Next

- [Accuracy against cost](/tutorials/workshop/modules/accuracy/) — put the accuracy of
  the common track next to the frequency and the area of this module.
- [ASIC with open-source tools](/tutorials/workshop/modules/asic/) — the same design,
  down to a layout.
- [Place and route after synthesis](/tutorials/workshop/modules/pnr/) — the netlists of
  an ASIC synthesis, placed and routed, against what the synthesis estimated.
- [Let the search do the work](/tutorials/workshop/finale/dse/) — stop sweeping, start
  searching.
