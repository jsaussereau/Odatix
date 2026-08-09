---
title: "Run the Examples"
weight: 1
description: "Try Odatix end to end on its built-in example designs, in a few minutes."
---

Odatix ships with ready-to-run example designs, testbenches and workflows. These
tutorials take you from an empty directory to interactive results using nothing
but those examples — no design of your own required yet.

Every one of them starts the same way:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/odatix_example && cd ~/odatix_example
$ odatix init --examples
{{< /code >}}

## In the order they make sense

{{< tutorial-cards cols="3" numbered="true" >}}

Once these work, bring in your own project:
[Run Odatix on your own designs](/tutorials/own_designs/).

> [!NOTE]
> All run commands are daemon-driven. To detach, re-attach, list and stop
> sessions, see [Job Monitor & sessions](/docs/gui/monitor/).
