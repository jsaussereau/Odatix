---
title: "Derived metrics"
description: "Link results of different job types together: import a metric from a matching result, or compute one across simulation and synthesis."
weight: 2
---

# Derived metrics

> [!IMPORTANT] Requires Odatix 4.0+

A **derived metric** is a metric a result does not hold itself, but gets from *another* result — or computes from metrics it already has.

This is what links job types together. A simulation knows how many cycles a benchmark takes. A synthesis knows at what frequency the design closes timing. Neither result can express "how long does this benchmark take on this design, in microseconds" on its own — the answer needs both. A derived metric copies `Cycles` from the matching simulation onto each synthesis result, then divides it by `Fmax`.

{{< toc >}}

## What they are good for

| Question | How it is answered |
|---|---|
| **Runtime** — how long does the benchmark actually take? | Import `Cycles` from the simulation, divide by the synthesis `Fmax`. |
| **Energy per benchmark** | Import `Cycles`, combine with the synthesis power figure and the period. |
| **Area–performance ratios** | Import a throughput measured in simulation, divide by the LUT or gate count. |
| **Accuracy vs. cost** | Import a workflow's `final_accuracy` onto the synthesis result of the same configuration, and plot it against area. |
| **Normalizing against a reference** | Pin the source to one fixed configuration and import its value onto every result, to express everything relative to it. |

Once derived, these values are ordinary metrics: they appear in the exported results and are usable as any axis in [Odatix Explorer](/docs/gui/explorer/) — which is the point. A scatter of area against *runtime* is only possible because the runtime was derived.

## Where they are defined

All derived metrics of a workspace live in a **single file**, `odatix_userconfig/derived_metrics.yml` (the path is the `derived_metrics_file` setting). One file, because a derived metric reads results the target's own file does not contain.

{{< code lang=yaml filename="odatix_userconfig/derived_metrics.yml" >}}
groups:
  cpus: ["AsteRISC/*", "Ibex/*"]

derived_metrics:
  # Copy the cycle count of the matching simulation onto every synthesis result
  Cycles:
    from: simulation
    for: "@cpus"
    unit: cycles

  # Then compute a runtime from it
  Runtime:
    type: operation
    op: "Cycles / Fmax"
    for: "@cpus"
    unit: us
{{< /code >}}

Metrics are computed **in declaration order**, so an `operation` can use a value an earlier import brought in — as `Runtime` does above.

The GUI has a **Derived Metrics** page that edits this file, if you prefer not to write the YAML by hand.

## The two kinds

| `type` | What it does | Required |
|--------|--------------|----------|
| `import` (default when `from` is set) | Read a metric from a matching result of another kind. | `from` |
| `operation` | Evaluate an expression over metrics the result already has, imported ones included. | `op` |

## Common keys

| Key | Default | Description |
|-----|---------|-------------|
| `type` | inferred | `import` or `operation`. Inferred from `op` / `from` when omitted. |
| `from` | — | Which results to read: `simulation`, `workflow`, `fmax_synthesis`, `custom_freq_synthesis`, `synthesis`, `any`, or a list. Import only. |
| `metric` | the metric's own name | Name of the metric to read in the source result. |
| `op` | — | Expression over metric names, e.g. `"Cycles / Fmax"`. Operation only. |
| `apply_to` | `synthesis` | Which kinds of results receive the metric. Same vocabulary as `from`. |
| `for` | `*` | Which instances receive it: a pattern, a list, or `"@group"`. Matched against architecture, `architecture/configuration`, workflow name and simulation name. |
| `where` | — | `{meta key: patterns}` — only results matching this receive the metric. |
| `source_where` | — | `{meta key: patterns}` — only these results may be read as a source. |
| `step` | last step | Which step of the source job to read, when its flow is split into [steps](/docs/tools/add_flows/): a step name, a list, `"@group"`, or `any` for all of them. |
| `unit` | — | Unit label exported alongside the value. |
| `on_multiple` | `error` | What to do when several source results match: `error`, `first`, `last`, `skip`, `mean`, `min`, `max`, `sum`. |
| `optional` | `false` | Do not warn when no source result matches. |
| `overwrite` | `false` | Replace a value the result already has. |

## Groups

A **group** is a named list of patterns; `"@name"` stands for that list anywhere patterns are accepted. Groups are not tied to architectures — the same mechanism names sets of simulations, workflows, targets or parameter values.

{{< code lang=yaml filename="derived_metrics.yml" >}}
groups:
  cpus: ["AsteRISC/*", "Ibex/*"]
  benchmarks: ["TB_Dhrystone", "TB_Coremark"]
  fpga: ["xc7a100t*", "xc7s50*"]
{{< /code >}}

A group may reference another group.

## How a source result is matched

Results of every kind share one flat set of dimensions — architecture, configuration, and every [parameter domain](/docs/configurations/param_domains/). By default, a source result matches when both results **agree on every dimension they have in common**.

A dimension only one of them carries is not a constraint. That is what makes an *invariant* domain work: a simulation that declares

{{< code lang=yaml filename="simulations/TB_Dhrystone/_settings.yml" >}}
invariant_domains: [MEM]
{{< /code >}}

is run for a single value of `MEM`, and its result carries no `MEM` dimension at all — so it applies to *every* value of `MEM` on the synthesis side, with nothing to declare in `derived_metrics.yml`.

When the source was not declared invariant, the same result is obtained by telling which value to read. The `match` section refines the default join:

{{< code lang=yaml filename="derived_metrics.yml" >}}
Cycles:
  from: simulation
  for: "@cpus"
  match:
    pin: {MEM: 1024I_1024D}          # read this value of MEM, whatever the target's
    ignore: [Voltage]                # do not constrain on this domain at all
    map: {MEM: Cache}                # the domain is not named the same on both sides
    keys: [architecture, configuration]   # join on exactly these, nothing else
  on_multiple: error
{{< /code >}}

| `match` key | Effect |
|-------------|--------|
| `keys` | Join on exactly these dimensions, and nothing else. |
| `ignore` | Drop these dimensions from the join. |
| `pin` | Require a fixed value on the source side, and drop that dimension from the join. |
| `map` | Rename a source-side dimension to its target-side name, when the two do not agree. |

> [!NOTE]
> The key is `keys`, not `on`: YAML reads a bare `on:` as the boolean `true`. A file written with `on:` anyway is still honoured.

### Steps of the source job

A flow split into [steps](/docs/tools/add_flows/) exports **one result per step**, so a single job is several candidate sources. By default a derived metric reads the *last* step each job reached — the finished result — which is why nothing has to be said about steps in the common case.

`step` says otherwise:

{{< code lang=yaml filename="derived_metrics.yml" >}}
# What place & route did to the post-synthesis estimate
LUT_count_after_synthesis:
  metric: LUT_count
  from: synthesis
  step: synthesis        # a step name, a list of them, or "@group"

LUT_pnr_delta:
  type: operation
  op: LUT_count - LUT_count_after_synthesis
{{< /code >}}

`step: any` reads every step of the job at once, the values being reduced by `on_multiple`.

The step of the results that *receive* a metric is not restricted: every step result in scope gets it. Narrow that side with `where: {step: ...}`.

### When several sources match

`on_multiple` decides. The default, `error`, reports the ambiguity and writes nothing — refine `match` or pick a reduction (`first`, `mean`, `max`…) deliberately.

## Worked example: runtime and energy

{{< code lang=yaml filename="odatix_userconfig/derived_metrics.yml" >}}
groups:
  cpus: ["AsteRISC/*", "Ibex/*"]
  benchmarks: ["TB_Dhrystone", "TB_Coremark"]

derived_metrics:
  # 1. Bring the simulated cycle count onto every synthesis result
  Cycles:
    from: simulation
    source_where: {simulation: "@benchmarks"}
    for: "@cpus"
    match:
      pin: {MEM: 1024I_1024D}
    unit: cycles

  # 2. Runtime, from cycles and the frequency the design closes timing at
  Runtime:
    type: operation
    op: "Cycles / Fmax"
    for: "@cpus"
    unit: us

  # 3. Energy for the whole benchmark
  Benchmark_energy:
    type: operation
    op: "Runtime * Total_power"
    for: "@cpus"
    unit: uJ
{{< /code >}}

Every synthesis result of a CPU now carries `Cycles`, `Runtime` and `Benchmark_energy`, and Explorer can plot area against runtime, or energy against frequency.

## Running them

Derived metrics are **not** computed at export time — the result they need may not exist yet when a job finishes, since a synthesis can complete before the simulation it borrows from has run.

They are recomputed from scratch over the whole result set every time they run, so applying them twice changes nothing, and a value whose source disappeared is removed rather than left stale.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix res_derived   # apply derived metrics to the result files
$ odatix results       # export everything, then apply them
{{< /code >}}

If no source result matches, Odatix warns once per metric, naming a few of the affected results — set `optional: true` when that is expected.

## See also

- [Base metrics](/docs/results/metrics/) — extracting values from a job's own outputs.
- [Parameter domains](/docs/configurations/param_domains/) — the dimensions a join runs on.
- [Results & export](/docs/results/) — where derived metrics end up.
- [Odatix Explorer](/docs/gui/explorer/) — plotting them.
