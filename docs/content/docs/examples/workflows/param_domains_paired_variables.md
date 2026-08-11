---
title: "Paired Variables"
description: "Two variables that describe the same physical scenario, zipped together with a group label instead of cross-combined."
weight: 6
---

# `param_domains_paired_variables` — zipping two variables together

Sources: `examples/workflow_param_domains_cli` — settings in `workflows/param_domains_paired_variables/`.

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - param_domains_paired_variables + max_speed/* + road_length/* + num_vehicles/* + signal_timing/*
{{< /code >}}

Cross-combining every variable is not always what you want. Here, `max_speed` and `road_length` describe **the same thing** — a road profile — and combining them freely would produce a 35 km/h motorway and a 90 km/h city street, neither of which is worth simulating.

Giving them the same `group` label zips them instead:

{{< code lang=yaml filename="workflows/param_domains_paired_variables/_settings.yml" >}}
variables:
  max_speed:
    type: list
    unit: kmh
    group: road_profile
    settings:
      list: [35, 90]

  road_length:
    type: list
    unit: km
    group: road_profile
    settings:
      list: [1, 10]

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

`35 kmh` pairs with `1 km` and `90 kmh` with `10 km`, position by position — two coherent road profiles, urban and highway. The ungrouped variables still cross-combine normally with them:

| | Without pairing | With pairing |
|---|---|---|
| Combinations | 2 × 2 × 2 × 2 = **16** | 2 × 2 × 2 = **8** |
| Nonsensical points | 8 of them | none |

> [!TIP]
> Pairing is the answer whenever several parameters describe one physical scenario — a technology node and its supply voltage, a cache size and its associativity, a memory depth and the address width that indexes it. It halves the sweep and removes the combinations that would need explaining away in the results.

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

