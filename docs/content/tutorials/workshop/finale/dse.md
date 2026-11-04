---
title: "Let the search do the work"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 1
description: "The finale: write one campaign, let Odatix choose which designs to run, and watch a Pareto front appear while you learn how it works."
categories: ["Tutorial", "Synthesis"]
tags: ["workshop", "dse", "pareto", "bayesian", "campaign"]
featured_image: "/images/features/dse.svg"
next_tutorials: ["/tutorials/workshop/finale/two_levels", "/tutorials/own_designs"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| None for step 1; a synthesis tool for step 2 | 45 min | A Pareto front computed by a search you configured |

Everything so far was a **sweep**: Odatix ran every configuration asked of it.
That is the right thing to do with nine designs, and the wrong thing with
nine thousand — which is what five parameters already amount to, and it is
exactly then that the question is worth asking.

`odatix dse` runs the same synthesis, on the same architectures, with the same
parameters. It simply stops running all of them: it evaluates a few, looks at
what came out, and chooses what to try next from there.

## The principle

A **design space exploration** (DSE) answers a question with several sides at
once — *the most accurate, the smallest and the fastest CORDIC* — when no
design wins on all of them. There is no single best answer, but there is a
set of designs worth keeping: the **Pareto front**, the designs that no other
design beats on every objective at once. Everything else is dominated, and
evaluating it was wasted work.

A search finds that front without running the whole space. It loops:

1. **Evaluate** a few designs — synthesize them, simulate them, run a workflow:
   whatever the campaign says measures one design.
2. **Learn** from the results: which parameters, in which region, gave what.
3. **Choose** the next designs where the front is most likely to improve, and
   go back to 1 — until the **budget**, the number of designs it may evaluate,
   is spent.

What you write is the question: what one evaluation runs, the
**objectives** to minimize or maximize, the **constraints** a design must meet
to count at all, and the parameters it may vary. That question is a
**campaign**. How the designs are chosen is the **strategy**, and Odatix
ships several of them.

> [!IMPORTANT]
> Start the exploration of step 2 at the **beginning** of this part, not at the
> end. It improves its front while the rest of the page is explained, and that
> is the demonstration.

## Step 1 — See an exploration run, in thirty seconds

Before spending a synthesis on it, watch the mechanism on something that costs
nothing. Odatix ships a campaign exploring a **workflow** rather than a
synthesis — a small image codec whose four knobs describe 3150 encoders, with no
EDA tool involved and batches that take seconds.

Click on **Run** → **Design space exploration**. The page lists the campaigns
of the workspace, one card each:

{{< img src="/images/screenshots/workshop/gui-dse-campaigns.png" title="Design space exploration: the settings of the exploration, then one card per campaign" >}}

1. On the card **image_codec_rate_quality**, click **Edit**. In the
   **Search** section, set:
   - **Strategy**: `Bayesian`;
   - **Mode**: `Continuous (async)`;
   - **Budget**: `50`, and **Batch**: `2`.
2. **Save** and go back.
3. Switch the card on, and **Explore**, then **Start**.

{{< details title="In a terminal" >}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix dse -p image_codec_rate_quality --strategy bayesian --mode async -b 50 -B 2 -y
{{< /code >}}
{{< /details >}}

What these settings mean:

- **Bayesian**: the search fits a statistical model of the space to the designs
  measured so far — what it expects each untried design to give, and how sure
  it is — and evaluates next the design where that model expects the front to
  grow the most. It is the strategy for few, expensive evaluations, such as a
  synthesis.
- **Continuous (async)**: the search keeps **Batch** designs running at all
  times, and chooses a new one the moment one finishes, instead of waiting for
  the whole batch to finish before deciding. No slot sits idle behind the
  slowest design.
- **Budget** `50`: the search stops after fifty designs evaluated, out of 3150
  — under 2 % of the space.

The search picks the first designs, measures their bitrate and their quality,
and chooses the next ones from what it found — with the same search as the
CORDIC campaign below, so what you watch here is what runs there. A few
minutes. This is the whole idea, running in front of you, and it is
also the fallback for anyone whose tools are not cooperating today.

> [!NOTE]
> Every command runs on **your** architecture, the one you described in the
> common track. They are written for `My_Cordic_sv`; in VHDL, write
> `My_Cordic_vhdl` (and `TB_My_Cordic_vhdl` for a simulation) instead —
> nothing else changes.

## Step 2 — Write the campaign for the CORDIC

An exploration is asked two questions. **What is being looked for** is a
*campaign*: a card of the page. **How it is run** — how many jobs at once,
which campaigns to run — is the **Exploration settings** section above the
cards.

Click on **New campaign**, name it `cordic_accuracy_area`, and fill it in:

| Section | Field | Value |
|---|---|---|
| Evaluation | **Command** | `Fixed-frequency synthesis` |
| | **Tools** | `Yosys + nextpnr` |
| | **Flows** | `standard`, `abc9`, `timing` |
| | **Search the frequency too** | on, from `100` to `250`, step `10` |
| Objectives | **Add objective** three times | `snr` maximize, `LUT_count` minimize, `frequency` maximize |
| Constraints | **Add constraint** | `Worst_Slack` ≥ `0` |
| Search | **Strategy**, **Mode** | `Bayesian`, `Continuous (async)` |
| | **Budget**, **Batch**, **Seed** | `18`, `4`, `1` |
| Architectures | **Add architecture** | `My_Cordic_sv`, then `+ ITERATIONS/* + WIDTH/*` |

{{< img src="/images/screenshots/workshop/gui-dse-campaign.png" title="The campaign of the finale, in the campaign editor" >}}

**Save**, and go back to the exploration page.

{{< details title="What the page wrote" >}}
{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/cordic_accuracy_area.yml" >}}
---
# what evaluating one design runs
run:              custom_freq_synthesis
tool:             yosys_fpga
flow:             [standard, abc9, timing]
target:           ""
simulations:      []

# at what frequencies: the search chooses one per design
frequencies:
  explore:        Yes
  range:
    from:         100
    to:           250
    step:         10

# what makes a design better than another
objectives:
  - metric: snr
    goal: max
  - metric: LUT_count
    goal: min
  - metric: frequency
    goal: max

# a design that misses its frequency does not count
constraints:
  - metric: Worst_Slack
    min: 0

# how the search looks for it
search:
  strategy:       bayesian
  mode:           async
  budget:         18
  batch:          4
  patience:       0
  seed:           1

# architectures to explore, one search each
architectures:
  - My_Cordic_sv + ITERATIONS/* + WIDTH/*

# apply the "dominated" exclusions too (see the design space module)
exclusions:
  apply: [illegal, duplicate, dominated]
{{< /code >}}

Written by hand, the same file works the same.
{{< /details >}}

{{< details title="With another tool" >}}
Only **Tools**, **Flows**, the frequency range and the area objective change.
Below, the lines of the campaign file that differ. The
flows are the strategies of [How fast can it go?](/tutorials/workshop/modules/fmax/#step-6--compare-synthesis-strategies).

**Vivado**

{{< code lang=yaml filename="cordic_accuracy_area.yml (changes)" >}}
tool:             vivado
flow:             [standard, area, performance]
target:           ""
until:            synthesis
frequencies:
  explore:        Yes
  range:          {from: 100, to: 400, step: 25}
{{< /code >}}

**Quartus**

{{< code lang=yaml filename="cordic_accuracy_area.yml (changes)" >}}
tool:             quartus
flow:             [standard, area, performance]
target:           ""
until:            synthesis
# objectives: ALM_count instead of LUT_count
{{< /code >}}

**Design Compiler / Genus**

{{< code lang=yaml filename="cordic_accuracy_area.yml (changes)" >}}
tool:             design_compiler        # or genus
flow:             [standard, ultra_area, ultra_timing]   # genus: [standard, area, timing]
target:           ""
# no "until": there is no step to stop at
frequencies:
  explore:        Yes
  range:          {from: 25, to: 150, step: 25}   # fit it to your technology
# objectives: Cell_Area instead of LUT_count
{{< /code >}}

**LibreLane**

{{< code lang=yaml filename="cordic_accuracy_area.yml (changes)" >}}
tool:             librelane
flow:             ""
target:           ""
until:            synthesis
frequencies:
  explore:        Yes
  range:          {from: 20, to: 50, step: 5}
# objectives: Cell_Area instead of LUT_count
{{< /code >}}

On sky130 the CORDIC runs between 40 and 63 MHz, hence the range, and
`budget: 12` is enough to get a front.

{{< /details >}}

Each design is synthesized **once, at a frequency the search picks**, rather
than through an fmax search. That is cheaper — one synthesis per design instead
of a series — and it is also more accurate: an fmax search finds the fastest
clock *one* run of the tool meets, while the front is made of designs synthesized
for the frequency they are judged at. The frequency becomes one more axis of the
space and one more objective, and the constraint throws out the designs that do
not meet it.

With Yosys + nextpnr, every evaluation goes through placement and routing: the
front is made of routed designs, and an evaluation still takes about a minute.
With Vivado, Quartus or LibreLane, `until: synthesis` stops every evaluation
after synthesis, as `--until` does on the command line. It is what makes the
exploration fit the slot, at a price: the timing after synthesis is optimistic,
so the front is too.

Back on the exploration page:

1. Switch off **image_codec_rate_quality**, and switch on
   **cordic_accuracy_area**.
2. **Maximum number of parallel jobs**: `4`, then **Save all**.
3. **Explore**. Before it costs anything, Odatix resolves the whole campaign
   and says what it is about to do:

    {{< img src="/images/screenshots/workshop/gui-dse-check.png" title="Ready to explore: the campaign resolved, nothing run yet" >}}

    The number of designs in the space depends on the values your domains
    hold.
4. **Start**. The monitor opens: the exploration itself is the first line, and
   the syntheses it chooses appear below it, one after the other.

{{< img src="/images/screenshots/workshop/gui-dse-monitor.png" title="The monitor: the exploration on top, its syntheses below, and its log on the right" >}}

The log of the **exploration** line says, design after design, what the search
chose, what came out, and how the front grew.

{{< details title="In a terminal" >}}
`-C` resolves the campaign and runs nothing, then the second line starts it:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix dse -p cordic_accuracy_area -C
$ odatix dse -p cordic_accuracy_area -j 4 -y
{{< /code >}}
{{< /details >}}

> [!NOTE]
> `snr` as an objective is the derived metric of [Accuracy against
> cost](/tutorials/workshop/modules/accuracy/): the search optimizes a number measured
> in **simulation** against one measured in **synthesis**. If you skipped that
> module, remove the `snr` objective: `LUT_count` against `frequency` is a front
> too, and everything else on this page is unchanged.
>
> `simulations: []` because the simulations of your architecture already ran
> in the common track. Nothing is run twice: the derived metric reads the
> results on disk.

{{< details title="If the slot is shorter still" >}}
Lower the **Budget** (`8`) rather than the parallelism. A smaller budget still
produces a front — just a coarser one, which is exactly the trade-off the search
itself is about. A narrower frequency range (`from: 200`, `to: 350`) also helps:
fewer frequencies far from what the design can reach are worth trying.
{{< /details >}}

## Step 3 — What it is doing while it runs

On the card of the campaign, click **Results** — or, in the menu, **Explorer**
→ **Design space exploration**. It shows, campaign by campaign: the Pareto
front as it stands, how many design points were evaluated, measured and **reused**,
the progress batch after batch, and the failures. It refreshes by itself while
the search runs.

{{< img src="/images/screenshots/workshop/gui-dse-front.png" title="The exploration in Odatix Explorer: the front, and how the search progressed" >}}

Three things on that page are worth a minute each.

**Reused designs.** If you did [How fast can it go?](/tutorials/workshop/modules/fmax/),
some of these designs are already measured: its syntheses at 100 MHz are designs
of this very space. The search takes those results for
free and does not charge them to its budget — so the work of the module is not
redone, and the front starts off ahead.

**What the search is choosing between.** Not only the parameters: the three
**Flows** make the synthesis strategy one more axis of the space. The search can
decide that this configuration belongs on the front *with `abc9`* and that one
*with `timing`*, which is an
answer a sweep gives only by running everything.

**Why there are no gaps in the schedule.** `mode: async` starts a new design the
moment a slot frees instead of waiting for the slowest of the batch — and
synthesis runs differ wildly in duration, so a batch always has a straggler.
`mode: batch` is the classical generational behaviour, if you want to see the
difference.

{{< details title="Why a bayesian search" >}}
It models the space from what it has measured so far, and evaluates next where
that model expects the most gain. That is the right trade when every evaluation
is **expensive** and there are few of them — a synthesis, in other words: a
workshop budget is a handful of designs, and `bayesian` is the strategy that
spends them well. The other strategies, and when to prefer them, are in [Design
space exploration](/docs/reference/dse/).
{{< /details >}}

## Step 4 — Read the front

What the campaign found is in `results/dse/cordic_accuracy_area.yml`, named
after the campaign — so a second campaign on the same design, asking a different
question, keeps its own answer instead of overwriting this one.

In the Explorer, the front is the chart of [Accuracy against
cost](/tutorials/workshop/modules/accuracy/) with the points the search chose on it: x
`LUT_count`, y `snr`, **Color by** `flow`. Every point on the front is a design
nothing else beats on both axes at once, and the room now has the same chart
with different points on it — because a search is a search, not a sweep, and two
runs do not take the same path.

That is the honest end of the afternoon: not *the* answer, but a front, a budget
that produced it, and a campaign file anyone can re-run with a bigger budget
tonight.

## If something did not work

| Symptom | What to do |
|---|---|
| **Explore** says a metric name is unknown | An objective must be a metric the run reports, or a derived metric. `frequency`, `LUT_count` and `Worst_Slack` always work on an FPGA synthesis at a fixed frequency; `snr` needs [module B](/tutorials/workshop/modules/accuracy/). |
| **Explore** says `until` is not a step | The steps depend on the tool: `synthesis` exists for Vivado, Quartus and LibreLane. Yosys + nextpnr, Design Compiler and Genus have no step to stop at — remove the line. |
| `odatix dse -C` refuses the campaign file | `-i/--input` is the exploration settings file, `-p/--campaign` the campaign. A campaign given to `-c` is refused with that hint. |
| Nothing is evaluated | The budget may already be spent by reused results: `--no-reuse` ignores them, and `-o` runs the designs again. |
| Every design fails | The campaign runs the ordinary synthesis command: check it on one design first (`odatix synth --tool yosys_fpga --at 150 -a "My_Cordic_sv + ITERATIONS/12 + WIDTH/8"`). |
| The slot ends before the budget does | The exploration runs in the background: leave the monitor, and **Monitor** finds it again; the red cross of the **exploration** line ends it. The front found so far is already written. |

## That is the workshop

In three hours, this design went from RTL nobody had run to a measured
accuracy, an FPGA cost, an ASIC layout, a design space of your own shaping, and
a Pareto front computed by a search — without a single script written, and with
whatever tools each person had in the room.

The same material is yours to replay:

- [Run Odatix on your own designs](/tutorials/own_designs/) — start with one
  configuration of your RTL, then add the domains.
- [Design space exploration](/docs/reference/dse/) — constraints, several
  campaigns, workflows as objectives.
- [Troubleshooting](/docs/troubleshooting/) — when it is Monday and nobody is
  there to ask.
