---
title: "Virtual Parameter Domains"
description: "Sweep parameters that are injected into commands or config files instead of replaced in source files — defined inline, with no folders required."
weight: 5
---

# Virtual Parameter Domains

> [!IMPORTANT] Requires Odatix 4.0+

Classic [parameter domains](/docs/configurations/param_domains/) are *file-based*: each domain is a folder of parameter files spliced into your sources. In workflows, parameters are often better passed **on the command line** or written into a config file. **Virtual parameter domains** cover that case: they are generated inline in `_settings.yml`, need no folders, and are substituted into your task commands via `${var}` placeholders.

{{< toc >}}

## When to use them

Use virtual parameter domains when:

- Your workflow task or your rtl generation command takes parameters as **CLI arguments** (`--max_speed 45`) rather than editing a source file.
- You want to sweep a parameter space for your workflow **without creating a folder and files** for every value.

> [!NOTE]
> Keep `use_parameters: No`, since you are not replacing text inside a source file, you are injecting values into commands.

## Define variables inline

Declare the sweep directly under `generate_configurations_settings.variables`, using the same [generation methods](/docs/configurations/config_generation/) as file-based domains (`list`, `range`, `power_of_two`, `function`, set operations…). An optional `unit` annotates the value.

{{< code lang=yaml filename="workflows/traffic/_settings.yml" >}}
use_parameters: No

tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed} --num_vehicles ${num_vehicles} --signal_timing ${signal_timing}

generate_configurations_settings:
  variables:
    max_speed:
      type: list
      unit: kmh
      settings:
        list: [35, 45, 55]
    num_vehicles:
      type: list
      settings:
        list: [100, 300]
    signal_timing:
      type: list
      unit: s
      settings:
        list: [15, 45]
{{< /code >}}

Odatix expands the **cross-product** of all variables — here `3 × 2 × 2 = 12` configurations — copies the sources into one work directory per configuration, substitutes each `${var}`, and runs the tasks in parallel.

## Placeholders come from more than variables

Any `${...}` placeholder in a command is substituted from the resolved configuration — variables, generated values, and workflow-level settings alike. This lets a single command template drive an entire sweep without touching source files:

{{< code lang=yaml filename="_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 run_profile.py --profile "${workflow_cli_profile}" --tag "demo"
{{< /code >}}

## Architectures: sweeping the generation command

The same mechanism is available to architectures that generate their RTL from a
higher-level description ([`generate_rtl`](/docs/configurations/)): `generate_command`
accepts the very same `${...}` placeholders, filled from the architecture's parameter
domains and from its variables.

{{< code lang=yaml filename="architectures/Example_Counter_Chisel_CLI/_settings.yml" >}}
generate_rtl: Yes
design_path: "examples/counter_chisel_cli"
generate_command: "sbt 'runMain example.Counter --width ${width} --o=rtl'"
generate_output: "rtl"

use_parameters: No

generate_configurations_settings:
  variables:
    width:
      type: list
      unit: bits
      settings:
        list: [4, 8, 16, 24, 32, 48, 64]
{{< /code >}}

Odatix runs the architecture once per value of `width`, exactly as if `width` were a
folder-based parameter domain: `Example_Counter_Chisel_CLI+width/4bits`,
`…+width/8bits`, and so on. Select one from the command line like any other domain:

{{< code lang=bash >}}
odatix fmax -a Example_Counter_Chisel_CLI+width/16bits
{{< /code >}}

This one ships with `odatix init --examples`: it is the counter of
`Example_Counter_chisel`, parameterized on the command line instead of by replacing a
value in its Scala source.

A name that matches a **file-based** parameter domain is substituted with the content of
its selected parameter file, and a name that matches neither is left untouched, so
environment variables such as `$HOME` still reach the shell.

> [!NOTE]
> Variables only expand into runs when `generate_command` actually references them. An
> architecture whose variables are there to
> [generate configurations](/docs/configurations/config_generation/)
> (`generate_configurations: Yes`) keeps that sole meaning.

## Expanding several data points per run

Sometimes a single configuration run produces *several* measurements (for example a BER curve over a range of Eb/N0). Metrics can expand one run into one record per data point — see [Define a workflow](/docs/reference/workflow/) and the `metric_sweep` example shipped with `odatix init --examples`.

## See also

- [Parameter domains](/docs/configurations/param_domains/) (file-based)
- [Configuration generation](/docs/configurations/config_generation/)
- [Define a workflow](/docs/reference/workflow/)
