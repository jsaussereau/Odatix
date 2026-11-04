---
title: "Synthesize it"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 4
description: "The common track, part 3: choose a synthesis target and start the fixed-frequency synthesis of the nine configurations, which runs in the background while you write the simulation."
categories: ["Tutorial", "Synthesis"]
tags: ["workshop", "gui", "synthesis", "cordic"]
featured_image: "/images/features/rtl-synthesis.svg"
next_tutorials: ["/tutorials/workshop/common/simulate"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Yosys + nextpnr, or your own synthesis tool | 15 min, then a few minutes in the background | Nine configurations synthesized |

A **fixed-frequency synthesis** synthesizes each configuration once, at the
clock the architecture gives (here 100 MHz, as we gave at the [creating the architecture](/tutorials/workshop/common/describe/#step-3--create-the-architecture) section).

> [!NOTE]
> It reports all the main metrics given by the tool.

## Step 1 — Choose the synthesis tool and strategy

The page is written for **Yosys + nextpnr**, from the [OSS CAD
Suite](/install/oss_cad_suite/): free, and the same on every system. Another
synthesis tool works the same way — take its tab at each step. 

> [!IMPORTANT]
> Whichever it is, it has to work in your terminal before Odatix can drive it: Odatix runs the executable the way you would.

Click on **Run** → **Fixed-frequency synthesis**, then the card of your tool:

{{< img src="/images/screenshots/workshop/gui-synthesis-tools.png" title="Fixed-frequency synthesis: one card per tool, one line per strategy" >}}

Each line of a card is a synthesis **strategy**.

Some tools like Vivado or Quartus support **incremental steps**: they can resume a run at a later step, rather than starting over. **Hover** a strategy, and a menu **Run up to** lists the steps of the job — click **synthesis**.

The numbers after synthesis are optimistic but cheap, and a later run **resumes** at place and route rather than starting over.

> [!TIP]
> The default option for this workshop is to use the **Standard** stategy of the **Yosys + nextpnr** tool. 

1. Click on the card corresponding to your tool and strategy.

## Step 2 — Select your targets

A **target** is what the tool implements on: an FPGA part, a technology or a
platform. Its name is passed to the tool as is. Each job synthesizes one
configuration on one target, so nine configurations on two targets make
eighteen jobs.

On the run page, click **Choose targets**. The page lists the targets of your
tool, one card per target:

1. You can enable as many as you want.

    {{< img src="/images/screenshots/workshop/gui-synthesis-targets.png" title="Fixed-frequency synthesis: one card per tool, one line per strategy" >}}

    > [!WARNING] 
    > Just keep in mind that each enabled target multiplies the number of jobs by the number of configurations. With Yosys_FPGA, you can safely enable two targets.

    > [!CAUTION]
    > `ice40-up5k-SG48` has only 39 I/Os, which is too few for the CORDIC

2. Save. The save button is highlighted as long as some changes are not saved.
3. Go back to the run page.

> [!NOTE]
> The targets go into a target file of the workspace, one per tool
> (`target_yosys_fpga.yml` for example). You can also edit that file by hand. 
> A target is enabled when its line is not commented out.

## Step 3 — Launch the synthesis

On the run page, as for [the analysis](/tutorials/workshop/common/analysis/):

1. **Maximum number of parallel jobs**: Choose a number of jobs that fits your machine. The default is 8, which is fine for most laptops. If possible, choose nine here.
2. Switch on your architecture: nine configurations.
3. **Run jobs**, then **Start**.

{{< img src="/images/screenshots/workshop/gui-synthesis-select.png" title="The synthesis of the nine configurations, nine at a time (here with Vivado, up to synthesis)" >}}

The monitor follows the jobs, the log of the selected one on the right:

{{< img src="/images/screenshots/workshop/gui-synthesis-monitor.png" title="The monitor: four syntheses running, five queued" >}}

With Yosys + nextpnr, each job takes **about one minutes** on a laptop, placement and routing included. with Vivado (2024.2, Artix-7, up to synthesis), about twelve. 

The area metric is `LUT_count` with both. With Design Compiler or Genus, the area metric is `Cell_Area`; with Quartus, `ALM_count`. 

> [!TIP]
> **Do not wait for it.** The jobs run in the background, in a daemon of their own: you can leave the monitor, close the browser tab, or even stop `odatix-gui`. Going back to the GUI monitor or running `odatix ps` and `odatix monitor` in a terminal, finds them again.
