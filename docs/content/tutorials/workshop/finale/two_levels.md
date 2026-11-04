---
title: "Search the model, synthesize the front"
date: 2026-10-28
author: "Jonathan Saussereau"
weight: 2
description: "Optional, after the finale and module C: an exploration of the bit-accurate model finds the accuracy/cost front among 391 designs in half a minute, and only the few designs an application needs are simulated and synthesized as RTL."
categories: ["Tutorial", "Workflows"]
tags: ["workshop", "workflows", "dse", "multi-fidelity", "pareto", "cordic"]
featured_image: "/images/features/workflows.svg"
next_tutorials: ["/tutorials/own_designs", "/tutorials/run_examples"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Python 3; a simulator and a synthesis tool for step 4 | 25 min | A front found on the model, confirmed on the RTL, at a fraction of the cost |

[The algorithm before the RTL](/tutorials/workshop/modules/workflow/) used the model to
answer one question. This page uses it the way a design team would: as the
**first of two levels** of an exploration.

- Level 1, the model: a fraction of a second per design. Search the whole space
  with it, for accuracy against an estimated cost.
- Level 2, the RTL: minutes per design. Simulate and synthesize only what level
  1 kept, and only the part of it the application needs.

Neither level is new by itself. Chaining them — and being able to check that
the cheap level told the truth — is what turns days of synthesis into minutes.

> [!IMPORTANT]
> Do [The algorithm before the RTL](/tutorials/workshop/modules/workflow/) first: this
> page relies on the model it introduces.

> [!NOTE]
> Every command runs on **your** architecture, the one you described in the
> common track. They are written for `My_Cordic_sv`; in VHDL, write
> `My_Cordic_vhdl` (and `TB_My_Cordic_vhdl` for a simulation) instead —
> nothing else changes.

## Step 1 — Give the model a cost

An exploration needs at least two objectives that pull against each other. The
model already measures the accuracy; it also estimates what the core costs,
from its adders:

{{< code lang=python filename="examples/workflow_cordic_model/cordic_model.py" >}}
def adder_bits(width, iterations):
    # each stage adds on x and y (width + 2 bits each) and on the angle (32 bits)
    return iterations * (2 * (width + 2) + 32)
{{< /code >}}

No synthesis is involved, so it is only an estimate. On an FPGA, though, one
adder bit is about one LUT, and on the nine designs of the workshop it lands
within 7 % of the LUT count of Vivado. Step 4 checks it on new designs.

## Step 2 — Search 391 designs

The `cordic_model_wide` workflow runs the same model on every width from 4 to
20 bits and every stage count from 2 to 24: 391 designs. The campaign that
searches it is shipped:

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/cordic_model_front.yml" >}}
run:              workflow     # what evaluates a design is the model
tool:             ""
flow:             ""
target:           ""

objectives:
  - metric: snr
    goal: max
  - metric: adder_bits
    goal: min

constraints:
  - metric: snr                # below 20 dB, not a trade-off but a failure
    min: 20

search:
  strategy:       bayesian
  mode:           async
  budget:         60
  batch:          8
  seed:           1

architectures:
  - cordic_model_wide
{{< /code >}}

It is the campaign of the [finale](/tutorials/workshop/finale/dse/), with
`run: workflow` instead of a synthesis: the search does not care what a design
costs to evaluate, only what it measures.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix dse -p cordic_model_front -y -E
{{< /code >}}

About half a minute on a laptop. Open the result on **Explorer →
Exploration**, campaign `cordic_model_front`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

The front is a long staircase, from 20 dB at 192 adder bits to almost 100 dB at
1400, and it is made only of designs with **fewer stages than bits** — the rule
of thumb of the previous page, found here by a search that was never told about
it.

{{< details title="Did the search miss anything?" >}}
On a model this fast, it can be checked: sweeping all 391 designs takes under a
minute. The exact front holds 64 designs. After 60 evaluations, the search has
found 33 of them, plus 2 a hair away from it: the shape of the trade-off, and
the designs on it, at a sixth of the cost.

Which is also the honest limit of this example: with two parameters and a
model this fast, the sweep would have done. The search starts paying for itself
when the model has more knobs — rounding mode, width of the angle path, input
scaling — or when one evaluation is a system simulation of several minutes
rather than a fraction of a second.
{{< /details >}}

## Step 3 — Keep what the application needs

A front of 35 designs is still 35 syntheses, and nobody needs all of it. Say
the application asks for **between 44 and 54 dB** — about seven to eight
effective bits. A short script, shipped next to the model, reads the front from
the archive of the exploration, keeps that window, adds the configurations of
`My_Cordic_sv` that do not exist yet, and prints the selection:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 examples/workflow_cordic_model/front_to_rtl.py --snr-min 44 --snr-max 54
4 designs of the front between 44 and 54 dB:
  added odatix_userconfig/architectures/My_Cordic_sv/ITERATIONS/8.txt
  width 12,  8 stages:  46.47 dB,  480 adder bits
  added odatix_userconfig/architectures/My_Cordic_sv/ITERATIONS/9.txt
  width 12,  9 stages:  51.14 dB,  540 adder bits
  added odatix_userconfig/architectures/My_Cordic_sv/WIDTH/13.txt
  width 13,  9 stages:  52.55 dB,  558 adder bits
  added odatix_userconfig/architectures/My_Cordic_sv/WIDTH/16.txt
  width 16,  9 stages:  53.01 dB,  612 adder bits

Selection, for odatix sim and odatix synth:
  -a "My_Cordic_sv + ITERATIONS/8 + WIDTH/12" "My_Cordic_sv + ITERATIONS/9 + WIDTH/12" "My_Cordic_sv + ITERATIONS/9 + WIDTH/13" "My_Cordic_sv + ITERATIONS/9 + WIDTH/16"
{{< /code >}}

In VHDL, add `--architecture My_Cordic_vhdl`: the script writes into the
architecture it is given, and prints the selection for it.

Four designs out of 391, and three of them are not in the design space of the
workshop at all: nobody would have synthesized them.

> [!NOTE]
> The script only writes files a run would read anyway: `ITERATIONS/8.txt`
> holds `8`, as in [step 5 of the previous
> page](/tutorials/workshop/modules/workflow/#step-5--take-the-answer-back-to-the-rtl).
> Delete them to get the original nine designs back.

## Step 4 — Confirm on the RTL

Run the four designs through the simulation of the common track and a
synthesis — plus `ITERATIONS/12 + WIDTH/12`, the design the workshop would have
picked for that window, as the reference:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -s TB_My_Cordic_sv -y -E -a "My_Cordic_sv + ITERATIONS/8 + WIDTH/12" "My_Cordic_sv + ITERATIONS/9 + WIDTH/12" "My_Cordic_sv + ITERATIONS/9 + WIDTH/13" "My_Cordic_sv + ITERATIONS/9 + WIDTH/16" "My_Cordic_sv + ITERATIONS/12 + WIDTH/12"
$ odatix synth --tool vivado --at 100 --until synthesis -j 5 -y -E -a "My_Cordic_sv + ITERATIONS/8 + WIDTH/12" "My_Cordic_sv + ITERATIONS/9 + WIDTH/12" "My_Cordic_sv + ITERATIONS/9 + WIDTH/13" "My_Cordic_sv + ITERATIONS/9 + WIDTH/16" "My_Cordic_sv + ITERATIONS/12 + WIDTH/12"
{{< /code >}}

The simulation takes seconds, the five syntheses about four minutes at `-j 5`.
With another synthesis tool, change `--tool` as in [How fast can it
go?](/tutorials/workshop/modules/fmax/); the area metric is then `ALM_count` or
`Cell_Area`, and the estimate of step 1 is only meant for an FPGA.

{{< details title="What you should see" >}}
Vivado 2024.2, `xc7a100t-csg324-1`, 100 MHz, after synthesis:

| Design | SNR, model | SNR, RTL | Adder bits | LUT_count |
|---|---|---|---|---|
| width 12, 8 stages | 46.47 | 46.47 | 480 | 520 |
| width 12, 9 stages | 51.14 | 51.14 | 540 | 580 |
| width 13, 9 stages | 52.55 | 52.55 | 558 | 604 |
| width 16, 9 stages | 53.01 | 53.01 | 612 | 680 |
| width 12, 12 stages (reference) | 53.61 | 53.61 | 720 | 760 |
{{< /details >}}

Three things to read in that table:

1. **The accuracy is exact.** The model is bit-accurate, and the simulation of
   the RTL gives the same SNR to the last digit, on designs the model was never
   compared on before.
2. **The cost is right where it matters.** The estimate is off by 5 to 10 %,
   but it puts the designs in the same order as Vivado does: the front of the
   model is the front of the RTL.
3. **The answer is not the obvious one.** Width 13 with 9 stages reaches
   52.6 dB on 604 LUTs; the design the workshop would have picked reaches
   53.6 dB on 760. One decibel less for a fifth less area — found by
   running five syntheses, not 391.

To see it, add the accuracy to the synthesis results as in [Accuracy against
cost](/tutorials/workshop/modules/accuracy/) (`derived_metrics.yml`, then
`odatix results derived`), and chart `LUT_count` against `snr`.

{{< details title="And if the model had been wrong?" >}}
Then step 4 is where it shows, on five designs, in minutes — not after a month
of decisions made on it. A model that disagrees with its RTL on an SNR is a bug
in one of them; one whose cost estimate puts the designs in the wrong order is
an estimate to fix before the next exploration. Either way, the check is the
same five commands, and it is worth running every time the model changes.
{{< /details >}}

## If something did not work

| Symptom | What to do |
|---|---|
| `cordic_model_front` is not found | The workspace predates the example: run `odatix init -y --cordic` in a new directory, and copy `odatix_userconfig/dse_campaigns/cordic_model_front.yml`, `odatix_userconfig/workflows/cordic_model_wide` and `examples/workflow_cordic_model` from it. |
| `front_to_rtl.py` finds no archive | Run it from the workspace, after the exploration: it reads `results/dse/cordic_model_front.yml`. |
| `front_to_rtl.py` finds no design in the window | Your front differs (another seed, a smaller budget): widen the window, or look at **Explorer → Exploration** for where it lies. |
| `snr` is not on the synthesis results | The derived metrics of [Accuracy against cost](/tutorials/workshop/modules/accuracy/) are not set up in this workspace. |

## Next

- [Design space exploration](/docs/reference/dse/#exploring-a-workflow) — every
  setting of a campaign, workflow campaigns included.
- [Create your own workflow](/tutorials/own_designs/workflows/) — your model as
  level 1, your RTL as level 2.
