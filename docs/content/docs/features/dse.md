---
title: "Design Space Exploration"
description: "Search a design space too large to sweep: odatix dse evaluates configurations batch after batch and returns the Pareto front of the best trade-offs."
layout: "doc-features"
badge: "Design Space Exploration"
badgeColor: "#4f46e5"
cta: true
weight: 8
features:
  - title: "Pareto front"
    description: "Declare the objectives to minimize or maximize, and get every configuration no other one beats on all of them at once."
  - title: "Search strategies"
    description: "Genetic, Bayesian (Gaussian process), random or exhaustive — in batches, or asynchronously when some designs take far longer than others."
  - title: "Constraints and budget"
    description: "Rule out the designs that miss a constraint, cap the number of evaluations, stop when the front no longer grows."
  - title: "Resumable campaigns"
    description: "The archive is written after every batch: an interrupted exploration picks up where it stopped, and results already measured are reused for free."
---

## Search instead of sweeping

[Architecture exploration](/docs/features/architecture-exploration/) runs every
configuration an architecture describes. That is the right thing to do with
forty of them, and the wrong thing with forty thousand — which is what four or
five parameters already amount to.

`odatix dse` runs the same jobs, on the same architectures, with the same
parameters. It just stops running all of them: it evaluates a batch of
configurations, reads what came out, and chooses the next batch from there,
until a budget is spent. What it returns is the **Pareto front**: every
configuration that no other one beats on all the objectives at once — the
trade-off curve you would have drawn from a full sweep, for a fraction of the
runs.

{{< img src="/images/features/dse.svg" shadow="false" >}}

## When you need it

- **A space too large to sweep.** A handful of parameter domains multiply into
  thousands of configurations; a search finds the interesting ones in a few
  dozen evaluations.
- **Expensive evaluations.** When one design costs an hour of synthesis, the
  `bayesian` strategy models each objective and only runs what it expects to
  teach it the most.
- **Several conflicting objectives.** Frequency against area, quality against
  rate, power against throughput: the answer is the whole trade-off curve, not
  one point.
- **Hard constraints.** Timing met, a resource budget, a simulation that must
  pass — designs that miss them do not count, and the search learns to avoid
  them.
- **Non-RTL spaces.** A campaign can search a [workflow](/docs/features/workflows/)
  just as well as an architecture.

## How it works

An exploration is a **campaign**: a file of `odatix_userconfig/dse_campaigns/`
saying what evaluating one design runs (`fmax_synthesis`,
`custom_freq_synthesis` or `workflow`, with which tool, flow and target), the
objectives, the constraints, the search strategy and its budget, and the
architectures to search.

The axes of the search are the parameters the architecture already declares:
the variables of rule-based parameter domains, the configurations of file-based
domains, and the virtual variables feeding its commands. The tool, flow, target
and clock frequency can be searched as well. [Exclusions](/docs/configurations/exclusions/)
apply exactly as they do to a sweep.

The search runs as a job of the monitor, its batches underneath it. After every
batch, `results/dse/<campaign>.yml` is rewritten with what was evaluated and
which configurations form the front, so an interrupted exploration picks up
where it stopped. The metrics themselves land in the usual results files.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | The parameter domains and generation rules are the space being searched — nothing to redeclare. |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) | Search for the best frequency/area trade-offs, each design at its own maximum frequency. |
| [Fixed-frequency synthesis](/docs/features/rtl_synthesis/) | Let the search choose the clock constraint of each design as one more axis. |
| [Simulation](/docs/features/simulation/) | Run every design through its testbenches and use their metrics as objectives or constraints. |
| [Workflows](/docs/features/workflows/) | Search anything that runs from a shell, hardware or not. |
| [Explorer](/docs/features/explorer/) | The **Exploration** page draws the front as it grows, batch after batch. |

## Using it

### From the configuration files and the CLI

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/core_area_speed.yml" >}}
run:              fmax_synthesis
tool:             vivado

objectives:
  - metric: Fmax
    goal: max
  - metric: LUT_count
    goal: min

constraints:
  - metric: Worst_Slack
    min: 0

search:
  strategy:       genetic        # genetic, random, exhaustive or bayesian
  budget:         40             # configurations evaluated at most
  batch:          8              # evaluated together, between two decisions

architectures:
  - My_Core
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix dse -p core_area_speed -C              # what it would do, running nothing
$ odatix dse -p core_area_speed
$ odatix dse --strategy bayesian --mode async   # one question at a time
{{< /code >}}

The `image_codec_rate_quality` campaign of the examples searches a workflow and
needs no EDA tool: it is the quickest one to try. Every key of a campaign, the
strategies and what comes out are on the
[design space exploration reference](/docs/reference/dse/).

### From the GUI

`odatix-gui` → **Run jobs → Design space exploration** (`/dse`) lists the
campaigns as cards, with how much of their budget is spent and how many design points are on their front. **Edit** opens a campaign in a form — objectives, constraints, search and architectures, with the metric names of the workspace suggested — and **Explore** checks the selection before handing it to the daemon. 
What an exploration found is on the **Exploration** page of Odatix Explorer.

## Where to go next

- **Tutorials** — [Workshop: let the search do the work](/tutorials/workshop/dse/)
- **Reference** — [Design space exploration](/docs/reference/dse/) · [Exclusions](/docs/configurations/exclusions/)
- **Related features** — [Architecture exploration](/docs/features/architecture-exploration/), which defines the space · [Results exploration](/docs/features/explorer/), where the front is drawn.
