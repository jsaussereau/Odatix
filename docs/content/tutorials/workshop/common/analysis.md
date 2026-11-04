---
title: "Check the RTL in ten seconds"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 3
description: "The common track, part 2: an RTL analysis elaborates the nine configurations with Verilator or GHDL, and catches a wrong delimiter before it costs a synthesis."
categories: ["Tutorial", "Analysis"]
tags: ["workshop", "gui", "analysis", "cordic"]
featured_image: "/images/features/analysis.svg"
next_tutorials: ["/tutorials/workshop/common/synthesis"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Verilator **or** GHDL | 5 min | Nine configurations checked |

The architecture of [the previous page](/tutorials/workshop/common/describe/)
has nine configurations, and none has been run yet.

## Step 1 — Run the analysis

> [!EXAMPLE] Explaination
> Before running anything long, make sure your RTL is correctly interpreted by the tools you will use. Odatix can run a quick analysis on every configuration, and it takes only a few seconds.

Click **Run** → **RTL analysis**. The page that opens is the
one every run goes through:

1. Under **Tools**, keep only your installed tools switched on.

   > [!TIP]
   > You can use verilator for the SytemVerilog RTL, and GHDL for the VHDL RTL.

   {{< img src="/images/screenshots/workshop/gui-analysis-select-tools.png" >}}

2. Under **Architectures**, switch on `My_Cordic_sv` (or `_vhdl`): its two domains and the nine combinations appear, all selected.

   {{< img src="/images/screenshots/workshop/gui-analysis-select.png" title="Run jobs: one tool, one architecture, nine configurations selected" >}}

3. Click **Save all** and **Run jobs**.

   Odatix checks the selection and shows what it is about to run — nine new jobs,
   and a tool that answers:

   {{< img src="/images/screenshots/workshop/gui-analysis-confirm.png" title="Ready to run: nine analysis jobs with Verilator" >}}

4. Click **Start**. The page turns into the **monitor** of the jobs, and after a few seconds the analysis is over (or minutes depending on the tool).

   > [!WARNING]
   > A successful job does not mean the tool accepted it! It just means analysis did not crash.  

   {{< img src="/images/screenshots/workshop/gui-analysis-monitor.png" title="The analysis is over: every configuration passed" >}}

## Step 2 — Read what it found

To check what the tool(s) found, click **Close session and open RTL analysis**.

{{< img src="/images/screenshots/workshop/gui-analysis-results.png" title="The analysis is over: every configuration passed" >}} 

The interface shows what each tool found, per configuration.
Here, everything should be fine if you use tool that support the input RTL language.

With a wrong delimiter for instance — say `,` for `ITERATIONS`, so that the replacement eats the `)` closing the parameter list — every configuration would fail on a syntax error at a line of the RTL you never touched. 

That is the sign of a delimiter: fix it in **Edit configs** ([step 4 of the previous page](/tutorials/workshop/common/describe/#step-4--describe-what-changes)), and run the analysis again.

> [!TIP]
> Switch on more tools under **Tools** and the same check runs on each of them:
> simulators and synthesizers do not accept the same subset of the language.
> It is the page to come back to whenever something later fails on *every*
> configuration — it tells a broken design from a broken tool setup in seconds.
