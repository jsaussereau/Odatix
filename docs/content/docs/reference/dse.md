---
title: "Design Space Exploration"
description: "Search a design space instead of sweeping it: campaigns, objectives, budget and search strategies."
weight: 9
---

# Design space exploration

Odatix runs every configuration an architecture describes. That is the right
thing to do with forty of them, and the wrong thing with forty thousand — which
is what four or five parameters already amount to, and it is exactly then that
the question is worth asking.

`odatix dse` runs the same synthesis, on the same architectures, with the same
parameters. It just stops running all of them: it evaluates a batch, looks at
what came out, and chooses the next batch from there.

**Nothing about your architectures changes.** The parameters, the rules that
produce the configurations and the results that come out are the ones already
there; an exploration reads the same parameter space a sweep enumerates. What it
adds is one file saying what makes a design good and how long to look for it.

{{< toc >}}

## Campaigns

An exploration is asked two questions, and they live in two files.

**What is being looked for** is a *campaign*: a file of
`odatix_userconfig/dse_campaigns/`, holding the architectures to search, the
objectives, the constraints and the search itself. A campaign is named after its
file, and so is what it finds (`results/dse/<campaign>.yml`).

**How the exploration is run** — how many jobs at once, whether to ask before
starting, and *which campaigns to run* — is `odatix_userconfig/dse_settings.yml`.

{{< code lang=yaml filename="odatix_userconfig/dse_settings.yml" >}}
overwrite:        No
ask_continue:     No
nb_jobs:          8

# campaigns to run, one after the other
campaigns:
  - fir_area_speed
{{< /code >}}

| Key | Meaning |
|-----|---------|
| `campaigns` | The campaigns to run, each named after its file in `dse_campaigns/`, without the `.yml`. Overridden by `-p/--campaign`. |
| `overwrite`, `ask_continue`, `nb_jobs`, ... | The usual run settings, shared by every campaign of the run. |

That split is what lets **two campaigns search the same architecture**. Asking
*how small can this get* and *how fast can this get* of the same design, with the
same parameter domains, used to be one search overwriting the other: they are
now two files, so two names, so two answers side by side.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ ls odatix_userconfig/dse_campaigns/
fir_area_speed.yml  fir_power.yml
$ odatix dse -p fir_power        # run one of them, whatever the settings file says
{{< /code >}}

## The campaign file

`odatix_userconfig/dse_campaigns/<campaign>.yml`, one per campaign.

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
# what evaluating one design runs
run:              fmax_synthesis
tool:             vivado
flow:             ""
target:           ""
simulations:      []

# what makes a design better than another
objectives:
  - metric: Fmax
    goal: max
  - metric: LUT_count
    goal: min

# what a design has to be for it to count at all
constraints: []

# how the search looks for it
search:
  strategy:       genetic
  mode:           batch
  budget:         50
  batch:          8
  patience:       0
  seed:

# architectures to explore, one search each
architectures:
  - Example_FIR_hls
{{< /code >}}

| Key | Meaning |
|-----|---------|
| `run` | What evaluating one design runs: `fmax_synthesis`, `custom_freq_synthesis` or `workflow`. |
| `tool`, `flow`, `target` | What runs a design: the eda tool, its flow, its target. One name each, or a list to search them (see below). |
| `simulations` | Simulations every design is run through as well (see below). Empty: none. |
| `frequencies` | What a fixed-frequency synthesis runs at (see below). Ignored by the other runs. |
| `reuse_results` | Whether results already measured for designs of this space are given to the search for free (see [below](#starting-from-what-is-already-measured)). Default: yes. |
| `objectives` | What the search is looking for (see below). |
| `constraints` | What a design has to be for it to count at all (see below). Empty: nothing is ruled out. |
| `search` | How the next designs are chosen, and when to stop. |
| `architectures` | The architectures to explore — the workflows, when `run` is `workflow` (see [below](#exploring-a-workflow)). Each gets its own search and its own budget. |
| `exclusions` | Which of the [exclusions](/docs/configurations/exclusions/) of the architecture this campaign applies, and the ones it adds (see below). |

Everything else about a run — the frequency bounds, the timeouts — keeps coming
from the settings file of the command being run
(`fmax_settings.yml` and friends). An exploration fills in that file's
selection and runs the command that was already there; it never writes over the
selection you keep.

## What runs the designs

`tool`, `flow` and `target` say what an evaluation is run with. One name each
and every design is run the same way:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
tool:             vivado
flow:             ""             # empty: the default flow of the tool
target:           ""             # empty: every target "target_vivado.yml" enables
{{< /code >}}

A **list** instead of a name is what the search chooses between:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
tool:             vivado
flow:             [standard, power_opt]
target:
  - xc7a100t-csg324-1
  - xc7k70t-fbg676-2
{{< /code >}}

| Key | Default | Meaning |
|-----|---------|---------|
| `tool` | *(none)* | The eda tool, or the tools the search chooses between. |
| `flow` | *(empty)* | Its flow, or the flows to choose between. Empty: the default flow of each tool. |
| `target` | *(empty)* | Its target, or the targets to choose between. Empty: every target the tool's target file enables. |

The three of them are **one axis**, not three: a flow is declared by a tool and
a target is enabled by one, so what the search moves along is the combinations
that actually exist. Naming two tools, two flows and two targets does not give
eight designs to try — it gives however many of those eight the workspace can
actually run, and the rest are never proposed. A tool, a flow or a target the
workspace does not hold stops the exploration before anything is synthesized.

Like the frequency, what runs a design is not a parameter of the architecture:
the same rtl built by two tools or for two targets is the same rtl. It is a
trade-off all the same, and searching it is what an exploration asking *which
target is this design cheapest on* is. A design run by two toolchains counts as
two designs, each with its own place on the front, and the results are read back
from the results file of each tool.

This is how an exploration searches **synthesis strategies**: the built-in flows
of Design Compiler, Vivado and Quartus are strategies (timing, area, power, runtime), and
DC NXT is a tool of its own running the same ones. Crossing the architecture
with the strategy finds, for each configuration, the strategy that puts it on
the front:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/mult_asic_strategies.yml" >}}
run:              custom_freq_synthesis
tool:             [design_compiler, dc_nxt]
flow:             [standard, ultra, ultra_timing, ultra_area, ultra_power]
{{< /code >}}

Leaving `target` empty keeps the behaviour of every other run: the design is
synthesized for every target its tool's file enables, and is worth what its best
one is worth. Naming targets does **not** rewrite `target_<tool>.yml` — the run
is simply told which of the enabled targets to work on, so other runs sharing
that file are unaffected.

## Exploring a workflow

Everything above works the same when what evaluates a design is a
[workflow](/docs/reference/workflow/) rather than a synthesis. A workflow is
swept exactly like an architecture — same parameter domains, same
configurations, same generation rules — so a search moves through it the same
way, and only two things change:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/image_codec_rate_quality.yml" >}}
run:              workflow
tool:             ""             # a workflow is not run by an eda tool
flow:             ""
target:           ""

objectives:
  - metric: bitrate_bpp         # a metric of the workflow's "_metrics.yml"
    goal: min
  - metric: psnr_db
    goal: max

constraints:
  - metric: encode_time_ms
    max: 120

architectures:
  - image_codec                 # a workflow, named as "workflow_settings.yml" names it
{{< /code >}}

- The names under `architectures` are **workflows**, selected the same way a
  run selects them (see [searching part of a space](#searching-part-of-a-space)).
  `image_codec` declares its four variables on its main domain, so `image_codec`
  searches all of them; a workflow with a second parameter domain `threads`
  would be searched by `my_workflow/* + threads/*`.
- `tool`, `flow` and `target` say nothing: a workflow runs its own commands, and
  its results are read from `results/results_workflow.yml`. `simulations` and
  `frequencies` are ignored for the same reason.

The metrics an objective or a constraint names are the ones the workflow's
`_metrics.yml` reads out of what its commands wrote, plus whatever
[derived metrics](/docs/results/derived_metrics/) add on top.

This is where an exploration is often worth the most: a workflow's knobs are
arguments on a command line, so there is nothing stopping five of them from
describing a hundred thousand runs, and nothing to synthesize means a batch
of ten comes back in a few seconds. The shipped example, `image_codec`, is a small transform
codec with four knobs — 3150 encoders, of which a campaign runs sixty and comes
back with the rate/quality curve none of them is beaten on:

{{< code lang=bash >}}
odatix dse -p image_codec_rate_quality
{{< /code >}}

## Frequencies

Only for `run: custom_freq_synthesis`, which is the one run that is *told* a
frequency — an fmax synthesis looks for one, and a workflow is whatever it is.
The frequency is then either fixed, or one more thing to search:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
run:              custom_freq_synthesis

frequencies:
  explore:        No             # fixed: every design is synthesized at each of the frequencies below
  list:           [100, 200]
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
run:              custom_freq_synthesis

frequencies:
  explore:        Yes            # searched: each design gets one frequency, chosen like a parameter
  range:
    from:         50
    to:           500
    step:         10
{{< /code >}}

| Key | Default | Meaning |
|-----|---------|---------|
| `explore` | `No` | Whether the search chooses the frequency of each design itself. |
| `list` | *(empty)* | Fixed: the frequencies every design is synthesized at. Explored: the frequencies to choose from, instead of the range. |
| `range` | `50` to `500` by `10` | Explored: the frequencies the search may choose from. |

Saying nothing leaves the frequencies of `synth_settings.yml`
alone, the way every other setting of a run is left alone. Saying something
replaces them for the exploration only — the file you keep is never written to.

**Fixed** frequencies are not an axis: what is searched is the parameters, every
design is run at all of them, and a design is worth what its best one is worth.
**Explored** frequencies are an axis of the space like a parameter is, so the
same design at two frequencies counts as two designs, each with its own budget
and its own place on the front. Designs of one batch that were given different
frequencies are simply run as several jobs of that batch.

> [!NOTE]
> Exploring the frequency is what makes a fixed-frequency synthesis worth
> searching: the trade-off it is run for *is* the one between the frequency
> asked for and what the design costs at it. Add `frequency` to the objectives
> to make the search look for it.

## Simulations

An objective is not restricted to what a synthesis measures. A cycle count, an
error rate, an accuracy — those come out of a testbench, and the trade-off worth
searching is usually against one of them: the widest filter is not the best one,
the fastest one is not either, and what settles it is what the design *does*.

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
simulations:
  - TB_Example_FIR
{{< /code >}}

Every design of a batch is then simulated as well as synthesized, in the same
session, alongside its synthesis rather than after it. It stays **one design out
of the budget**: a budget of fifty is fifty designs, whatever number of jobs
each of them takes. A design the search gave two frequencies is simulated once —
what a testbench measures does not depend on what the synthesis was asked to
close timing at.

The simulated number does not become an objective by itself. It reaches the
search the way it reaches the charts, through a
[derived metric](/docs/reference/metrics/) that copies it onto the synthesis
result — or computes something out of both, which is where a runtime in
microseconds comes from:

{{< code lang=yaml filename="odatix_userconfig/derived_metrics.yml" >}}
derived_metrics:
  Cycles:
    from: simulation
  Runtime:
    type: operation
    op: "Cycles / Fmax"
    unit: us
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
objectives:
  - metric: Runtime
    goal: min
  - metric: LUT_count
    goal: min
{{< /code >}}

The derived metrics of the workspace are recomputed after every batch, before
anything is read: a metric a synthesis borrows from a simulation cannot be
computed when either job finishes, since the other may still be running.

> [!NOTE]
> Leaving `simulations` empty does **not** turn derived objectives off. The
> derivation still runs, so a workspace whose designs were simulated beforehand
> — simulations are fast, sweeping them is cheap, and only the synthesis is
> worth searching — gets the same objectives without running anything twice.
> Naming simulations here is for the case where a design has to be simulated to
> be known at all, which is what a large space amounts to.

A design whose simulation produced nothing comes back unmeasured, with the
objective that was missing named in the log, exactly like one whose synthesis
failed: the search is told the place leads nowhere and looks elsewhere.

## Objectives

An objective is a metric to `min` or to `max`:

{{< code lang=yaml >}}
objectives:
  - metric: Fmax
    goal: max
  - metric: LUT_count
    goal: min
  - Total_Power          # a bare name is a metric to minimize
{{< /code >}}

Any metric of the results file works, [derived metrics](/docs/reference/metrics/)
included — which is how a simulation result becomes an objective (see above).
`Fmax` is where an fmax synthesis puts its answer. So does any dimension a
record carries as a number — `frequency` in particular, the frequency a
`custom_freq_synthesis` ran at.

**Nothing says how the objectives compare to each other**, and nothing has to. A
smaller design that runs slower is not worse than a bigger one that runs faster;
it is another trade-off. So what an exploration returns is not one design but
every design that nothing beats on all objectives at once — the **Pareto front**,
which is the curve you would have drawn by hand from a full sweep.

> [!NOTE]
> A design synthesized at several frequencies has several records. It is worth
> what its best record is worth, "best" being your own objectives.
>
> A job whose tool flow has several steps (elaboration, synthesis, place and
> route) writes one record per step. Only the record of the last step the job
> reached measures the design: the records of the earlier steps are the same
> job seen on its way, and are never compared with it.

### Metric names

An objective or a constraint names a metric exactly as the results file does:
`Worst_Slack`, `LUT_count`, `Total_Power` for Vivado, the keys of
`_metrics.yml` for a workflow. The names a campaign can use are the metrics its
tool declares in `metrics.yml` for the run (see [Base metrics](/docs/results/metrics/)),
the metrics of its simulations, the [derived metrics](/docs/reference/metrics/)
of the workspace, and `frequency` for a `custom_freq_synthesis`.

`odatix dse -C` checks them, and so does every exploration before it starts: a
name nothing measures stops it with the list of the names that would do, and
the closest one.

{{< code lang=text >}}
error: The campaign names metric(s) that nothing it runs measures: "Slack" (did you
mean "Worst_Slack"?). Fix "objectives" or "constraints" in
"odatix_userconfig/dse_campaigns/counter.yml". The metrics it can name are: ...
{{< /code >}}

When what runs a design declares no metrics (a tool without a `metrics.yml`, a
workflow without a `_metrics.yml`), nothing is checked.

## Constraints

An objective is something to get as much of as possible. A constraint is a line
a design is either on the right side of or not:

{{< code lang=yaml >}}
constraints:
  - metric: Worst_Slack
    min: 0
  - metric: LUT_count
    max: 20000
  - metric: Total_Power
    min: 0.1
    max: 0.5              # both bounds: a range
{{< /code >}}

Each entry is a metric with a `min`, a `max`, or both — any metric an objective
could name, [derived metrics](/docs/reference/metrics/) included.

**"The slack has to be positive" is a constraint and not an objective**, and the
difference matters. Written as `goal: max`, it spends the budget pushing the
slack up long after it stopped being worth anything — a design with 4 ns to
spare is not the answer to a search that could have run it faster — and it
leaves designs that miss the timing on the front, since one that fails by a
nanosecond is still the smallest anybody found. Written as a constraint, a
design that misses it is not a trade-off: it is a design that does not work.

### What the search does with them

Designs that break a constraint are **not thrown away**. At the start of a
search there are often only those, and a search told that all of them are
equally bad has no idea which way to go. They are ranked instead:

- a design that meets every constraint beats one that does not, whatever the
  objectives say;
- between two that both break one, the one closer to meeting it wins — where
  "closer" adds up each violation as a share of the bound it broke;
- between two that meet them all, the constraints have nothing to say and the
  objectives decide, exactly as they do without any.

So the front is made of feasible designs as soon as the search has found any.
While it has not, the front holds the closest it got, `feasible: false` is
written in the archive next to it, and the log says so after every batch — an
exploration that never gets there is usually a constraint written the wrong way
round, and that is worth finding out before the budget is spent.

Getting closer to feasibility also counts as progress for `patience`: a batch
that finally meets the constraints replaces a front of infeasible designs with a
smaller one, and would otherwise be read as having achieved nothing.

> [!NOTE]
> A constrained metric that a run did not measure leaves the design unusable,
> exactly like a missing objective: there is no telling whether it is feasible,
> so it is reported as unmeasured rather than guessed at.

## Search

| Key | Default | Meaning |
|-----|---------|---------|
| `strategy` | `genetic` | `genetic`, `random`, `exhaustive` or `bayesian`. Also accepted: `nsga2`, `ga`, `evolutionary` for `genetic`; `bo`, `mobo`, `gp` for `bayesian`; `sweep`, `full`, `all` for `exhaustive`; `uniform` for `random`. Any other name stops the exploration with the list. |
| `mode` | `batch` | `batch` or `async` (see [below](#batch-or-async)). |
| `budget` | `50` | How many design points are evaluated at most, per architecture. |
| `batch` | `8` | How many design points are evaluated together, between two decisions (`async`: how many are kept running at once). |
| `patience` | `0` | Stop after this many batches that do not push the front any further out. `0`: never. In `async` mode, counted in designs: `patience` × `batch` designs in a row. |
| `improvement` | `0` | How much of the front a batch has to add for it to count as progress. `0.02`: 2%. |
| `seed` | — | Makes a search reproducible. Empty: a different search every time. |
| `mutation` | — | `genetic` only: how often a parameter is changed. Empty: one per design on average. |
| `tournament` | `2` | `genetic` only: how many design points a parent is picked out of. Larger is greedier. |
| `population` | — | `genetic` only: how many design points the search keeps to look around. Empty: four batches' worth. |
| `candidates` | — | `bayesian` only: how many candidates the acquisition compares before choosing one. Empty: `300`. |
| `samples` | — | `bayesian` only: how many Monte Carlo draws a candidate's value is averaged over. Empty: `12`. |
| `shortlist` | — | `bayesian` only: how many of the candidates, once screened by a cheap score, get the full expected-gain estimate. Empty: `24`. |
| `front_cap` | — | `bayesian` only: how many points of the front a candidate is scored against at most. Empty: 40 up to two objectives, 24 for three, 12 beyond. |
| `constraint_models` | `false` | `bayesian` only: model each constraint on its own instead of their total. |

### When a batch counts as progress

What `patience` counts is not batches that leave the front's designs unchanged,
but batches that do not make it reach any further. Asking whether the front
changed says yes to a design a hair better on one objective just as readily as
to one that opens up a whole region of trade-offs — so an exploration either
goes on for hours over rounding, or stops in the middle of getting somewhere.

So what is compared is the **hypervolume** of the front — the region of
trade-offs the answer now covers, measured against the worst of everything
evaluated so far. A batch counts when it grows it by more than `improvement`.
The value is written in the archive under `hypervolume`, which is also how two
runs of the same exploration are compared.

**`exhaustive`** walks the whole space in sweep order. It is what Odatix already
did, said as a search — which is the point: with a budget larger than the space,
`odatix dse --strategy exhaustive` does exactly the work of `odatix fmax` over
the whole architecture.

**`random`** samples the space uniformly. It is the baseline any search has to
beat, and on a space of a million designs it already says more in fifty
evaluations than a sweep that will never finish.

**`genetic`** keeps the designs that turned out well and looks around them. A new
design is made of the parameters of two designs already evaluated, with one
parameter changed now and then. Parents are drawn towards the front, and within
the front towards the designs whose neighbours are far away, so the search
spreads along the trade-off curve instead of piling into one end of it. Only the
best `population` designs are kept to look around — everything is still in the
archive, and nothing is ever evaluated twice, but a search that looked around
everything it had ever run would drift back towards sampling at random.

**`bayesian`** fits a model of each objective — a Gaussian process — instead of
only ranking what it has run, and proposes the design expected to grow the
front's hypervolume the most. It costs more thinking between two designs than
`genetic` does, which is worth it once a design costs an hour of synthesis: a
model tells the search *how much* a candidate is likely to teach it, not only
that it looks like something that worked before. Like `genetic`, the first
handful of designs are drawn at random — there is nothing yet to fit a surface
to. See [below](#batch-or-async) for what it changes about the batch itself.

When the campaign declares `constraints`, they get a model of their own: how far
a design is from meeting them varies over the space as smoothly as any metric
does, and what the model is then asked for is how likely a candidate is to be
feasible at all. That likelihood multiplies the expected gain, so a design the
model expects to be excellent *and* infeasible is worth what its chances are and
stops being proposed over and over. While nothing feasible has been found yet
there is no front worth growing, and the search ranks candidates by how close to
feasible the model puts them instead: until it has one design that works,
finding one is the whole of the search.

By default the constraints share one model, fit on their total: what the search
needs of it is the boundary between the designs that count and the ones that do
not, and that boundary is the same one whichever constraint puts a design on the
wrong side of it. `constraint_models: true` fits one model per constraint
instead, and a candidate has to satisfy all of them at once. That is the finer
picture — two constraints missed along two different axes add up to a surface
shaped like neither of them — and it costs one more model to fit per constraint
on every refit, which is why it is asked for and not assumed. It falls back to
the total on its own if a design is missing one of the constrained metrics.

### Batch or async

`mode: batch` is what Odatix has always done: a batch is proposed, all of it is
run, and only once every design in it is back does the search decide what to
run next. That works until one design in the batch takes far longer than the
others — ordinary in EDA synthesis, where two designs a parameter apart can
close timing five times slower than each other — and then every other slot sits
idle waiting for it, batch after batch.

`mode: async` removes the batch boundary: a new design starts the moment a slot
frees, instead of waiting for the rest of the batch to finish. `batch` still
says how many design points run at once — it now means how deep the queue is kept,
rather than how many are decided between two rounds. A straggler ties up its
own slot and nothing else.

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
search:
  strategy:       bayesian
  mode:           async
  batch:          8             # how many design points run at once
{{< /code >}}

Any strategy can run in `async` mode — it is what fixes `genetic`'s batches
going idle on a straggler just as much as it lets `bayesian` ask one question
at a time — but it is `bayesian` it was built for: a model refit after every
single design that comes back, rather than after a whole batch, is a search
that reacts to what it learns as soon as it learns it. A design still in
flight is not ignored while its outcome is unknown; it is fed back into the
model at its own predicted value, which is enough to keep two proposals made
moments apart from landing on top of each other.

In `async` mode, what finishes together is not a batch: a round of decisions
can be a single design. So `patience` is counted in designs there — the front
has to stay put for `patience` × `batch` designs in a row for the search to
stop.

Cancelling an `async` exploration does not wait for the designs still running:
the ones already finished are archived, and the daemon finishes the others,
whose results the next run of the campaign picks up (see
[starting from what is already measured](#starting-from-what-is-already-measured)).

## What is searched

The axes of a search are the parameters the architecture already declares:

- the **variables of a parameter domain** that describes its configurations with
  rules — the search moves along each of them, and the configuration a set of
  values stands for is resolved on the spot, without anything having been
  generated first;
- the **configurations of a domain holding only files** — nothing says how they
  relate, so the choice is which one to use;
- the **variables of the architecture itself** when they feed its commands (the
  [virtual parameter domains](/docs/reference/architecture/)). For a design
  generated by high-level synthesis every knob is there, which is the case an
  exploration is most needed for.

Variables declared with the same `group` share an axis: they are chosen together,
position by position, exactly as a sweep pairs them.

An architecture whose parameters describe a single design is not something to
search, and `odatix dse` says so rather than running it.

### What the space does not hold

An architecture may declare that some combinations of its parameter domains are
not designs at all — illegal, duplicated, or dominated by another one. Those
[exclusions](/docs/configurations/exclusions/) apply to a search exactly as they
apply to a sweep: a genome that names an excluded combination names no design,
and a `duplicate` folds onto the configuration it says is the canonical one
instead of being thrown away.

What a campaign decides is which of them its question applies:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/frequency.yml" >}}
exclusions:
  apply: [illegal, duplicate, dominated]   # default: [illegal, duplicate]
  ignore: [share-adder-with-static-branches]
  rules:
    - when: "$width == 8"
      kind: dominated
{{< /code >}}

A `dominated` exclusion is knowledge about an objective, not about a design, so
it is only applied when a campaign asks for it: the design a frequency-oriented
campaign rules out is one an area-oriented campaign wants. The line printed when
the exploration starts says how many combinations are taken out, and the budget
is compared against the designs that are left.

### Searching part of a space

An entry of `architectures` selects what is searched the same way every run
selects what it runs:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/fir_area_speed.yml" >}}
architectures:
  - Example_FIR_hls                          # every parameter domain is searched
  - AsteRISC/*                               # the same thing, said out loud
  - AsteRISC/* + Mul/*                       # the main domain and "Mul", those two only
  - AsteRISC/* + MEM/1024I_1024D + Mul/*     # with "MEM" fixed to one configuration
{{< /code >}}

A domain written `<domain>/*` is **searched**, one written `<domain>/<name>` is
**fixed** to that configuration for every design, and one that is not written at
all is **left out** of the designs entirely — exactly what running that same
entry with `odatix fmax` would do. An entry that names no domain at all says
nothing about them, so all of them are searched.

Each entry is searched separately, with its own budget and its own answer. A
campaign naming a single architecture keeps its [archive](#what-comes-out) under
its own name (`fir_area_speed.yml`); one naming several says which is which,
adding what the entry selected (`asterisc_mem_AsteRISC+MEM_1024I_1024D.yml`).

## Running one

The quickest exploration to watch is the workflow example: it needs no eda
tool, and a batch comes back in a few seconds.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix init --examples
$ odatix dse -p image_codec_rate_quality -b 10 -C   # what it would do, running nothing
$ odatix dse -p image_codec_rate_quality -b 10
{{< /code >}}

The other example, `fir_area_speed`, needs Vitis HLS to generate its rtl and
Vivado to synthesize it, and each design is an fmax synthesis: count hours.
Running `odatix dse` alone runs every campaign `dse_settings.yml` selects, both
of these in the examples.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix dse -C                          # what it would do, running nothing
$ odatix dse
$ odatix dse -p fir_power                # one campaign, whatever the settings file selects
$ odatix dse -a Example_FIR_hls -b 30    # one architecture, thirty evaluations
$ odatix dse --strategy random --seed 1  # a reproducible baseline
$ odatix dse --strategy bayesian --mode async   # one question at a time
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `-t/--tool`, `-f/--flow`, `--target` | What runs a design. Repeatable: naming several makes it something the search chooses between. `-T` is `--trust` for the other commands: its former use for `--target` here is deprecated. |
| `-p/--campaign` | Campaign to run. Repeatable; replaces the settings file's list. |
| `-a/--architecture` | Architecture to explore. Repeatable; replaces the campaign file's list. |
| `-r/--run` | What evaluating one design runs. |
| `-s/--strategy` | `exhaustive` for a space small enough to measure whole, `random` for a baseline or a first look at a large space, `genetic` for a large space of designs cheap to evaluate, `bayesian` for designs that take hours to evaluate. |
| `-m/--mode` | `batch` when designs take about as long as each other, `async` when some take far longer than others (see [batch or async](#batch-or-async)). |
| `-b/--budget`, `-B/--batch` | How many design points at most, and how many at a time. |
| `--seed` | Make the search reproducible. |
| `--no-reuse` | Search from nothing but what the exploration runs itself (see [starting from what is already measured](#starting-from-what-is-already-measured)). |
| `-o/--overwrite` | Evaluate again what is already done, instead of picking the search up. |
| `-y/--noask` | Do not stop for the confirmation. |
| `-j/--jobs` | Maximum number of parallel jobs (`auto`: the number of CPUs minus one). |
| `-E/--exit` | Exit the monitor, and close the session, once the exploration is over. |
| `--logsize` | Size of the log history per job in the monitor, the exploration's own log included. |
| `-d/--detach` | Let the exploration run without attaching the monitor to it. |
| `-S/--session` | Session it runs in. A new one, `dse-<pid>`, when not given. |
| `-i/--input` | Exploration settings file, instead of `dse_settings_file` of `odatix.yml`. |
| `-c/--config` | Workspace settings file, as for every command. It used to name the exploration settings file: one given there is refused, with a hint. |
| `-C/--check` | Say what the exploration would do, without running anything. |

### What it looks like while it runs

An exploration says what it is about to spend and asks once, in the terminal it
was typed in — `Continue? (Y/n)`, which `-y` answers in advance. Nothing runs
before that. It then runs like every other Odatix command: in the daemon, under
the monitor.

The search itself is a job — the first one, kept at the top of the monitor
whatever else is running. Its log is what the search has to say, and only that:
what each batch changed, what it could not measure, where it stopped. What
running a batch would print about itself stays out of it — those jobs are right
there underneath, and say it better. Its progress bar is how much of the
exploration is behind. The designs it decides to evaluate appear
underneath it, in the same session, and it takes none of the parallel job slots:
`-j 8` runs eight synthesis jobs, not seven and a search.

So the monitor can be closed and attached again (`odatix monitor`) without
stopping anything, and `-d` starts the exploration without opening it at all.

Each exploration runs in a session of its own. With `exit_when_done: Yes` (or
`-E`), the session closes once the exploration is over; otherwise it stays, with
its logs, until it is stopped: `odatix stop -S <session>`, or `odatix stop --all`
for every session of the workspace.

### Picking a search up

An exploration is long and gets interrupted. What it has evaluated is written to
its archive after every batch, and running it again reads that back: the designs
already evaluated count against the budget and are not proposed a second time.
An exploration of fifty designs stopped at forty has ten left to spend, and
`odatix dse -C` says so before anything runs:

```txt
[fir_area_speed] Exploring "Example_FIR_hls/*": 27 designs, 27 of them evaluated at most, ...
Its archive "results/dse/fir_area_speed.yml" already holds 20 design(s) evaluated: 7 left to run.
```

A campaign whose budget is spent runs nothing and asks nothing: raise `budget`
to search further.

Killing the search from the monitor leaves the batch it had already enqueued
running: those designs finish, and the next run of the exploration reads their
results instead of synthesizing them again.

The batches are numbered on from where the archive stopped, so `dse_batch`
still reads in order across a resume.

`-o/--overwrite` is how to start over rather than pick up.

Changing the objectives or the constraints of a campaign — a metric name fixed,
a constraint added — does not start it over either. The designs already
evaluated are read again from the results files, measured against what the
campaign looks for now, and the log says so. Nothing is run again. A design the
archive holds as unmeasured is always read again on a resume, in case its
results came in after the exploration stopped.

To keep both answers instead, copy the campaign file and change what the copy
looks for: the new name gives it an archive of its own, and it starts from the
same designs (see below).

### Starting from what is already measured

A workspace is rarely empty when an exploration starts. A sweep of one
parameter, a single `odatix synth`, a simulation, a campaign that was looking
for something else: each of those measured designs that are in the space about
to be searched. `reuse_results` — on by default — hands them to the search
before its first batch. They go into the front and into what the strategy
learns from, and are never run again.

```txt
6 design(s) of this space had already been measured: the search starts from
them, and will not run them again.
```

They do **not** count against the budget: it says how many design points the
exploration evaluates, and it evaluated none of these. In the archive they are
marked as reused, so an exploration started a second time does not count them
as its own either. No batch of the campaign found them, so their `dse_batch` is
`0`: the batch before the first.

What is taken is only what can be *placed* in the space. Every run records
where its design sits — one coordinate per axis, written next to the results —
and that is what a record is looked up by. Nothing is guessed from a
configuration name, so a result is left alone when its run predates that
recording, when its architecture has since gained or lost a parameter, when one
of its values is no longer on an axis, when the campaign fixes a domain to
something else, or when an exclusion takes that design out. Those results are
still read for the front the way they always were; they are simply not what the
search reasons from.

A design that was measured, but not for what this campaign is looking for — no
`LUT_count` in a record of a simulation, say — is not taken either: it is left
for the search to run.

Set `reuse_results: No`, or pass `--no-reuse`, to search from nothing but what
the campaign runs itself. `-o/--overwrite` implies it: evaluating again what is already done is
what it asks for.

## What comes out

The metrics themselves are exported exactly as any run exports them, into the
results file of the tool, and Odatix Explorer reads them like any other result.

On top of that, each campaign writes `results/dse/<campaign>.yml`: what it
evaluated, in order, and which of those designs are the answer.

{{< code lang=yaml filename="results/dse/fir_area_speed.yml" >}}
campaign: fir_area_speed
architecture: Example_FIR_hls
strategy: genetic
objectives:
  - metric: Fmax
    goal: max
  - metric: LUT_count
    goal: min
constraints:
  - metric: Worst_Slack
    min: 0
feasible: true          # whether the front meets the constraints
designs_in_space: 27
evaluated: 20            # run by this campaign: what the budget counts
reused: 4                # already measured, given to the search for free
measured: 23
front:
  - configuration: Example_FIR_hls+ii/1+partition/complete+taps/8taps
    parameters: {taps: 8, ii: 1, partition: complete}
    metrics: {Fmax: 210, LUT_count: 1204, Worst_Slack: 0.12}
    feasible: true
{{< /code >}}

`campaign` is the name of the search (the campaign, and what its entry selects
when it names several architectures), `architecture` the architecture or the
workflow it searched. `constraints`, `feasible` and the per-design `unmet` are
written only by a campaign that declared constraints.

It is rewritten after every batch, not at the end: an exploration is long and
will be interrupted, and what it knew when it stopped has to be on disk — which
is also what a later run reads to pick the search up where it left off.

`history` holds what the front was worth after each batch — how many design points
were on it and how much of the space it covered (its hypervolume) — which is
what says whether the next run needs a bigger budget or a smaller one. The
whole curve is measured again on every save, against the range of every
objective as it is known then, so that two batches can be compared at all.

### Marked in the results

The designs a campaign evaluated are also exported as a results source of their
own, `results/results_dse_<campaign>.yml`. It is an ordinary results file — the
same records, the same metrics, read by Odatix Explorer like any other source —
with these dimensions added to every record:

| Dimension | What it says |
| --- | --- |
| `dse` | the campaign that evaluated the design |
| `dse_batch` | which batch proposed it, so the search can be read in order |
| `dse_front` | `yes` for the designs nothing dominates: the answer |
| `dse_feasible` | whether it meets the constraints, when the campaign declared any |

Which is what makes *plot the area against the frequency, colored by whether it
is on the front* an ordinary chart on any page of the explorer, rather than a
feature. The file is rewritten whole after every batch: a design that a later
batch pushed off the front stops being marked as being on it.

Nothing in there is a new result — the numbers are the ones the run measured
and already exported — so deleting these files loses the marking, not the
results.

### The exploration page

Odatix Explorer has a page of its own for what the results cannot say: the
search itself. **Explorer → Exploration** picks a campaign of the workspace and
shows its trade-off curve drawn over the designs it beat, how the front grew
batch after batch, the front design by design, and the designs that produced
nothing and why.

It reads the archives directly, and it polls: an exploration is meant to be
watched while it runs.

## From the GUI

`odatix-gui` has the same exploration in two pages, under **Run jobs → Design
space exploration** or **Run → Design space exploration** in the top bar.

**`/dse`** is `odatix dse`. Its settings panel is `dse_settings.yml` (whether
to evaluate again what is done, parallel jobs, log size, exit when done), and
each campaign of `dse_campaigns/` is a card showing its run, its objectives and
its architectures:

- the switch of a card selects the campaign for the next exploration, which is
  what `campaigns:` of `dse_settings.yml` lists;
- **Edit** opens the campaign, the copy and delete buttons work on its file, and
  **New campaign** writes a new one, commented like the ones `odatix init`
  writes;
- **Explore** runs the same check as `odatix dse -C`, then shows what each
  selected campaign will spend — the designs left to run, the space, the
  strategy — with any error found. **Start** hands it to the daemon and opens
  the monitor on its session. The session is the one chosen in the header;
  **New session...** starts a new one for every exploration.

**`/dse_campaign?campaign=<name>`** edits one campaign: what runs a design (the
run, the tools, flows and targets, the simulations), its frequencies, whether
it starts from what is already measured, the objectives and the constraints
(with the metric names of the workspace suggested), the search, and the
architectures with what each entry fixes or searches. The metric names
suggested are the ones what the campaign runs measures, and saving warns about
a name nothing it runs measures. For a workflow, the tool, flow, target and
simulation fields are hidden: they say nothing to it. Saving writes the
campaign file; the `exclusions` block is not edited on the page, and is kept
as it is written.

Each card of **`/dse`** also says where its campaign is (designs evaluated out
of its budget, designs on the front, last run) and links to its results in the
explorer. A selection whose budgets are all spent cannot be started: raise the
`budget`, or switch on **Evaluate again what is already done**.

What an exploration found is shown in Odatix Explorer, on the
[exploration page](#the-exploration-page).

## Using it from Python

`odatix.dse.explore()` runs the exploration a workspace describes, from a
script, and returns what each campaign found:

{{< code lang=python filename="explore.py" >}}
from odatix.dse import explore

archives = explore(campaigns=["image_codec_rate_quality"], budget=10, batch=5, nb_jobs=4)
for archive in archives:
    print(archive.path, len(archive.front()), "design point(s) on the front")
    for evaluation in archive.front():
        print(evaluation.entry, evaluation.metrics)
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ cd my_workspace
$ python explore.py
{{< /code >}}

- The workspace is the one of the current directory; pass `workspace=` to give
  another one (`odatix.workspace.Workspace.open(path)`).
- The search runs in the script, which prints what it does and returns once
  every campaign is over. Its batches run in a session started for it and
  stopped at the end — `odatix monitor -S <session>` follows them meanwhile —
  or in the one given with `session=`.
- Nothing is asked: a script does not answer `Continue? (Y/n)`. Pass
  `ask_continue=True` to be asked all the same.
- A keyword is applied where it belongs: a setting of `dse_settings.yml`
  (`campaigns`, `nb_jobs`, `overwrite`, ...), a setting of `search:`
  (`strategy`, `mode`, `budget`, `batch`, `seed`, ...) or any other setting of
  a campaign file (`tool`, `architectures`, `objectives`, ...), applied to every
  campaign selected. Any other keyword raises a `TypeError` listing the ones
  accepted.
- A campaign that cannot run raises `odatix.dse.CampaignError`, with the message
  `odatix dse` would print.

## Where to go next

- [Architecture Exploration](/docs/features/architecture-exploration/) — how the
  parameters an exploration searches are described in the first place.
- [Metrics](/docs/reference/metrics/) — what an objective can be.
- [Run Settings Files](/docs/reference/run_settings/) — the file each evaluation
  runs from.
- [The Odatix GUI](/docs/gui/app/) — the app the exploration pages are part of.
