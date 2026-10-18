---
title: "Run the examples"
weight: 1
description: "Try Odatix end to end on its built-in example designs, before bringing in your own."
---

Odatix ships with ready-to-run example designs, testbenches and workflows. These
tutorials take you from an empty directory to interactive results using nothing
but those examples — no design of your own required yet. Setting one up takes a
minute; its runs take what the tools take, from seconds for an RTL analysis to a
quarter of an hour or more for a synthesis, so each tutorial starts small.

Every one of them starts the same way (in the same directory, if you follow several):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p ~/odatix_examples && cd ~/odatix_examples
$ odatix init --examples
{{< /code >}}

## In the order they make sense

{{< tutorial-cards cols="3" numbered="true" >}}

Once these work, bring in your own project:
[Run Odatix on your own designs](/tutorials/own_designs/).

> [!NOTE]
> All run commands are daemon-driven. To detach, re-attach, list and stop
> sessions, see [Sessions and Job Monitor](/docs/sessions/).
