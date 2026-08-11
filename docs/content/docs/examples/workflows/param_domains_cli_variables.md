---
title: "Parameter Domains as Variables"
description: "The same four-way sweep declared as virtual parameter domains — twenty lines of YAML instead of four directories of configuration files."
weight: 5
---

# `param_domains_cli_variables` — the same sweep, with no directories

Sources: `examples/workflow_param_domains_cli` — settings in `workflows/param_domains_cli_variables/`.

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - param_domains_cli_variables + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*
{{< /code >}}

Identical sources, identical command, identical metrics — and **no domain directories at all**. The four sweeps are declared as variables instead:

{{< code lang=yaml filename="workflows/param_domains_cli_variables/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed} --num_vehicles ${num_vehicles} --signal_timing ${signal_timing} --road_length ${road_length}

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

  road_length:
    type: list
    unit: km
    settings:
      list: [1, 5]
{{< /code >}}

Selected the same way, with `+ max_speed/*`, and named the same way — `unit: kmh` produces `max_speed/35kmh`, reproducing by declaration what the directory version encoded in its file names. This is the [virtual parameter domain](/docs/configurations/virtual_param_domains/) mechanism, and reading the two workflows side by side is the fastest way to understand it.

3 × 2 × 2 × 2 = **24 runs**, from twenty lines of YAML and not one file.

> [!TIP]
> Prefer variables whenever the values are just values. Keep directories when a configuration is a **fragment of source code** rather than a scalar — which is the usual case for RTL, and the unusual case for workflows.

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

