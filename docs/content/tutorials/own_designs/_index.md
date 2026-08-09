---
title: "Run Odatix on your own designs"
weight: 2
description: "Bring an existing RTL design, testbench or arbitrary script into an Odatix workspace."
---

These tutorials turn a project you already have into an Odatix workspace. They
start with the smallest useful setup, then point to the reference pages when
your design space becomes larger.

> [!IMPORTANT]
> Start with one configuration and one target. Confirm that it passes RTL
> analysis or simulation before enabling large parameter sweeps or many
> parallel jobs.

{{< tutorial-cards cols="3" >}}

## Suggested order

1. [Implement your own RTL](/tutorials/own_designs/synthesis/) to create the
	architecture definition and configuration files.
2. [Simulate your own RTL](/tutorials/own_designs/simulations/) to connect a
	testbench and capture validation data.
3. Use [derived metrics](/docs/metrics/derived/) when simulation, synthesis or
	workflow results need to be compared together.

For Chisel, HLS or another generated-RTL flow, use the same architecture layout
with `generate_rtl` and `generate_command`; the [Configurations](/docs/configurations/)
reference explains the required settings.
