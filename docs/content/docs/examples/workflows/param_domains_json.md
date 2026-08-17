---
title: "Parameter Domains in a JSON File"
description: "The same sweep, on a script that takes no arguments: each domain substitutes its value into a JSON parameter file that sits in the sources."
weight: 7
---

# `param_domains_json` — substituting into a parameter file

Sources: `examples/workflow_param_domains_json` — settings in `workflows/param_domains_json/`.

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - param_domains_json + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*
{{< /code >}}

The same traffic simulation, but the script takes no arguments at all: it reads a JSON file that sits in its sources.

{{< code lang=yaml filename="workflows/param_domains_json/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py
{{< /code >}}

{{< code lang=json filename="examples/workflow_param_domains_json/workflow_params.json" >}}
{
    "num_vehicles": 150,
    "signal_timing": 45,
    "max_speed": 60,
    "road_length": 1,
    "other": ""
}
{{< /code >}}

{{< code lang=python filename="examples/workflow_param_domains_json/simulate_traffic.py" >}}
if __name__ == "__main__":
    # Load parameters from JSON file
    with open("workflow_params.json", "r") as f:
        params = json.load(f)
{{< /code >}}

Each domain therefore **writes its value into that file**, which is ordinary delimiter substitution with the JSON key as the start delimiter:

{{< code lang=yaml filename="workflows/param_domains_json/max_speed/_settings.yml" >}}
use_parameters: Yes
param_target_file: "workflow_params.json"
start_delimiter: '"max_speed": '
stop_delimiter: ','
{{< /code >}}

The other three domains are identical, with their own key. `param_target_file` is relative to the **root of the work directory**, which is where a workflow's `sources` are copied — a workflow has no `rtl/` subfolder, unlike an [architecture](/docs/reference/architecture/).

This is the pattern for any tool driven by a configuration file rather than by flags — and there are many: simulators, synthesis scripts, training configs, benchmark harnesses. The JSON stays valid and runnable on its own, exactly as the RTL examples keep their sources synthesizable outside Odatix.

> [!TIP]
> Using the key as the start delimiter and `,` as the stop delimiter works for any flat JSON, and leaves the formatting of the file untouched. Only the value between them is rewritten — the key order, the indentation and the unrelated entries (`"other": ""` here) survive.

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

