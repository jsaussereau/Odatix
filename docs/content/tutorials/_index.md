---
title: "Tutorials"
description: "Short, practical, shareable guides to get things done with Odatix."
---

These are hands-on, copy-paste walkthroughs — complete enough to follow start to
finish, short enough to finish in one sitting.

Each one is the practical half of a feature: read the
[feature page](/docs/features/) for what it is and when to use it, follow the
tutorial to actually run it, and keep the
[configuration reference](/docs/reference/) open for every key you may want to
change.

> [!NOTE]
> All run commands are daemon-driven. To detach, re-attach, list and stop
> sessions, see [Job Monitor & sessions](/docs/gui/monitor/).

## Run the built-in examples

The fastest way to see Odatix work is to run its bundled examples — no design of
your own required. They can be followed in order, or not.

{{< tutorial-cards section="/tutorials/run_examples" cols="3" numbered="true" >}}

## Use Odatix with your own project

Once the examples run, bring in the design, testbench or script you already have.

{{< tutorial-cards section="/tutorials/own_designs" cols="3" >}}

## Your own tools and scripts

A tool is a directory with a `tool.yml`, and a flow is one way of running it —
both are things you can add yourself.

{{< tutorial-cards section="/tutorials/own_flows" cols="3" >}}

## Running on a server

{{< tutorial-cards section="/tutorials" only="pages" cols="3" >}}

## One tutorial per feature

| Feature | Tutorial |
|---------|----------|
| [Architecture exploration](/docs/features/architecture-exploration/) | [Implement your own RTL](/tutorials/own_designs/synthesis/) |
| [RTL analysis](/docs/features/analysis/) | [RTL analysis](/tutorials/run_examples/analysis/) |
| [RTL synthesis](/docs/features/rtl_synthesis/) | [Custom-frequency synthesis](/tutorials/run_examples/synthesis/) |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) | [Parallel Fmax synthesis](/tutorials/run_examples/fmax_synthesis/) |
| [Place & route](/docs/features/pnr/) | [Place & route a synthesized design](/tutorials/run_examples/pnr/) |
| [Simulation](/docs/features/simulation/) | [Parallel simulations](/tutorials/run_examples/simulations/) · [Simulate your own RTL](/tutorials/own_designs/simulations/) |
| [Workflows](/docs/features/workflows/) | [Run a workflow](/tutorials/run_examples/workflows/) · [Create your own workflow](/tutorials/own_designs/workflows/) |
| [Results exploration](/docs/features/explorer/) | [Explore your results](/tutorials/run_examples/rtl_analysis/) |
