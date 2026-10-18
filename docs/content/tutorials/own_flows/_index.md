---
title: "Run Odatix on your own tools and scripts"
weight: 3
description: "Add a flow of your own to a tool Odatix ships, or wrap a tool it has never heard of."
---

Odatix has no hard-coded list of supported tools: a tool is a directory holding a
`tool.yml`, a *flow* is one way of running it, and a *target* is what it runs on.
All three are things you can add, from the GUI, from a short YAML file or from
the Python API.

{{< tutorial-cards >}}

> [!NOTE]
> Not a synthesis at all? A script, a training run, a benchmark — anything with
> no clock and no target — is a [workflow](/docs/features/workflows/), not a tool.

For the complete reference behind these tutorials, see
[Tools and flows](/docs/tools/).
