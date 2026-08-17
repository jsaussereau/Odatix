---
title: "Parameter Domains on the Command Line"
description: "A traffic simulation with four independent parameter domains, each feeding a placeholder of the command line, for sixteen runs."
weight: 4
---

# `param_domains_cli` — four parameter domains into four placeholders

Sources: `examples/workflow_param_domains_cli` — settings in `workflows/param_domains_cli/`.

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - param_domains_cli + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*
{{< /code >}}

A traffic simulation with four independent knobs — speed limit, vehicle count, signal timing, road length — each its own [parameter domain](/docs/configurations/param_domains/):

{{< code lang=yaml filename="workflows/param_domains_cli/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed} --num_vehicles ${num_vehicles} --signal_timing ${signal_timing} --road_length ${road_length}
{{< /code >}}

Each domain is a directory of configuration files, and its `_settings.yml` says only that nothing is substituted into a source:

{{< code lang=yaml filename="workflows/param_domains_cli/max_speed/_settings.yml" >}}
# This parameter domain is used for command placeholder substitution.
# Placeholders are injected in task commands through ${max_speed}.
use_parameters: No
{{< /code >}}

{{< code lang=text filename="workflows/param_domains_cli/" >}}
max_speed/       30kmh.txt (30)   70kmh.txt (70)
num_vehicles/    100.txt (100)    300.txt (300)
signal_timing/   15s.txt (15)     45s.txt (45)
road_length/     1km.txt (1)      5km.txt (5)
{{< /code >}}

Note the split between the **file name** and the **file content**: `30kmh.txt` is what the run is called, `30` is what the command receives. Units belong in the name, where they make results readable, and never in the value.

Four domains of two values each, combined with `+`:

{{< code lang=yaml filename="workflow_settings.yml" >}}
  - param_domains_cli + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*
{{< /code >}}

give 2 × 2 × 2 × 2 = **16 runs**. Results are read back from the JSON the script writes:

{{< code lang=yaml filename="workflows/param_domains_cli/_metrics.yml" >}}
metrics:
  average_travel_time:
    type: json
    settings:
      file: workflow_results.json
      key: average_travel_time

  co2_emissions:
    type: json
    settings:
      file: workflow_results.json
      key: co2_emissions

  congestion_level:
    type: json
    settings:
      file: workflow_results.json
      key: congestion_level
{{< /code >}}

## Where to go next

<div class="not-prose docs-links">
  <a class="docs-link" href="/docs/examples/workflows/">
    <span class="docs-link__title">All workflow examples</span>
    <span class="docs-link__text">The nine examples and what each one isolates.</span>
  </a>
  <a class="docs-link" href="/docs/features/workflows/">
    <span class="docs-link__title">Workflows</span>
    <span class="docs-link__text">The feature reference.</span>
  </a>
  <a class="docs-link" href="/docs/reference/workflow/">
    <span class="docs-link__title">Workflow settings</span>
    <span class="docs-link__text">Every setting these examples use, and the ones they do not.</span>
  </a>
  <a class="docs-link" href="/docs/results/">
    <span class="docs-link__title">Metrics</span>
    <span class="docs-link__text">The extractor types, and what <code>multiple</code> and <code>metadata</code> do.</span>
  </a>
</div>

