---
title: "Metric Sweep"
description: "A BER simulation that sweeps its own axis and writes one CSV row per point — multi-row metrics, metadata, and metrics computed from other metrics."
weight: 8
---

# `metric_sweep` — one run, many result rows

Sources: `examples/workflow_metric_sweep` — settings in `workflows/metric_sweep/`. This one is **not listed** in the shipped `workflow_settings.yml` — add it to the `workflows:` list to run it:

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - metric_sweep + channel_gain/*
{{< /code >}}

Some tools do not produce a result, they produce a **curve**. A BER simulation sweeps its own Eb/N0 axis internally and writes one CSV row per point:

{{< code lang=yaml filename="workflows/metric_sweep/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_ber.py --channel_gain ${channel_gain} --ebno_from 1 --ebno_to 3 --ebno_step 0.5

variables:
  channel_gain:
    type: list
    settings:
      list: [0.5, 1.0]
{{< /code >}}

Two configurations, five Eb/N0 points each. Taking the first row of the CSV and discarding the rest would throw away most of the run, so `multiple: true` extracts **every** row, and a `metadata` block tags each one with the value it belongs to:

{{< code lang=yaml filename="workflows/metric_sweep/_metrics.yml" >}}
metrics:
  FER:
    type: csv
    multiple: true
    settings:
      file: results.csv
      key: FER

  BER:
    type: csv
    multiple: true
    settings:
      file: results.csv
      key: BER

  # "operation" metrics are evaluated once per expanded row, using that row's
  # own FER/BER values.
  fer_over_ber:
    type: operation
    settings:
      op: "FER / BER"

metadata:
  EBNO:
    type: csv
    multiple: true
    settings:
      file: results.csv
      key: EBNO
{{< /code >}}

The two runs expand into **ten result records**, each carrying its own `EBNO` — as if each point had been run as a separate configuration, without paying the cost of ten separate jobs.

Two mechanisms worth separating:

- **`multiple: true`** turns one job into several records. `metadata` is what makes them distinguishable; without it, ten records would share the same identity.
- **`type: operation`** computes a metric from other metrics of the same record. Here it is evaluated per row, with that row's own values — not once for the job.

> [!TIP]
> This is the right shape for any tool with an internal sweep — a simulator stepping through SNR points, a benchmark suite reporting per-test numbers, a profiler with per-function results. Let the tool do the inner loop, and let Odatix do the outer one.

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

