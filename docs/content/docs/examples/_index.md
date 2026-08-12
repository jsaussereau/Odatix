---
title: "Examples"
description: "The designs and workflows shipped with Odatix, each isolating one mechanism — read them as worked examples, or copy them as starting points."
weight: 15
---

# Examples

`odatix init --examples` installs a workspace that already runs. The examples it contains are not
demos: they are the shortest complete answer to a question you will have to answer for
your own designs — how to sweep a parameter, how to keep the sources synthesizable, how
to read numbers back out of a tool.

They come in two families.

{{< doc-cards cols="2" >}}
{{< doc-card title="Architectures" link="/docs/examples/architectures/" icon="chip" accent="#7c3aed" cta="Browse the designs" >}}
Several RTL designs — a counter in four languages, an ALU, a multiplier, a sine ROM, a pipelined CORDIC, and a catalogue of configuration generators. Synthesis, Fmax search, simulation and parameter domains, on real hardware descriptions.
{{< /doc-card >}}

{{< doc-card title="Workflows" link="/docs/examples/workflows/" icon="workflow" accent="#ea580c" cta="Browse the workflows" >}}
Several script sweeps with no RTL and no EDA tool — task graphs, command placeholders, virtual and paired variables, multi-row metrics, environment bootstrapping. Odatix applied to anything that runs from a command line.
{{< /doc-card >}}
{{< /doc-cards >}}
<!-- 
## Which one to read

The two families use **the same mechanisms** — the same parameter domains, the same
substitution, the same metrics, the same job monitor. Only what gets run differs. So the
question is not which family applies to you, but which example isolates the thing you are
trying to do:

| If you want to… | Read |
|---|---|
| See a complete example, end to end | [Counter](/docs/examples/architectures/counter/) |
| Sweep a parameter without putting markers in your sources | [Counter](/docs/examples/architectures/counter/), [ALU](/docs/examples/architectures/alu/) |
| Sweep two parameters and combine them automatically | [Cordic](/docs/examples/architectures/cordic/), [Sine ROM](/docs/examples/architectures/rom/) |
| Generate configurations instead of writing them | [Configuration generation](/docs/examples/architectures/config_generation/) |
| Pass values on a command line rather than into a file | [CLI profile](/docs/examples/workflows/cli_profile/), [Parameter domains on the command line](/docs/examples/workflows/param_domains_cli/) |
| Declare a sweep with no configuration files at all | [Parameter domains as variables](/docs/examples/workflows/param_domains_cli_variables/) |
| Move two parameters together instead of crossing them | [Paired variables](/docs/examples/workflows/param_domains_paired_variables/) |
| Drive a tool through its JSON/YAML config file | [Parameter domains in a JSON file](/docs/examples/workflows/param_domains_json/) |
| Chain steps, with dependencies between them | [Basic](/docs/examples/workflows/basic/), [TensorFlow](/docs/examples/workflows/tensorflow/) |
| Get several result rows out of a single run | [Metric sweep](/docs/examples/workflows/metric_sweep/) |
| Run something that only exists on one OS | [Crossplatform](/docs/examples/workflows/crossplatform/) | -->

## Running them

{{< doc-card title="Tutorials" link="/tutorials/run_examples/" icon="tutorial" accent="#0d9488" cta="Browse the tutorials" >}}
Step-by-step instructions to run the examples, and understand how Odatix works.
{{< /doc-card >}}
