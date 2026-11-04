---
title: "The algorithm before the RTL"
date: 2026-10-28
author: "Jonathan Saussereau"
weight: 3
description: "Module C: sweep a bit-accurate Python model of the CORDIC as a workflow, find the number of stages worth paying for at each width, and check the model against the RTL."
categories: ["Tutorial", "Workflows"]
tags: ["workshop", "workflows", "fixed point", "bit-accurate model", "cordic"]
featured_image: "/images/features/workflows.svg"
next_tutorials: ["/tutorials/workshop/modules/asic", "/tutorials/workshop/finale/dse"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Python 3, nothing else | 20 min | The accuracy of 77 configurations before any RTL, and a model checked against the RTL |

Nobody in signal processing chooses a word length by synthesizing it. The
width of a datapath, the number of stages of an iterative algorithm, the
rounding of each operator: all of it is settled on a **fixed-point model**,
in Python or MATLAB, long before the RTL exists — because a model runs in a
fraction of a second where a simulation takes a minute and a synthesis ten.

That model is a script, with arguments, that writes numbers to a file. Which is
exactly what an Odatix **workflow** runs: any command, once per configuration,
in parallel, with its metrics on the same charts as everything else. No clock,
no target, no EDA tool.

## Step 1 — Look at the model

The workspace already holds one, next to the RTL it models:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 examples/workflow_cordic_model/cordic_model.py --width 8 --iterations 12
max_error_lsb  : 6.691247
rms_error_lsb  : 2.551285
mean_error_lsb : 2.288469
snr_db         : 28.66213
enob           : 4.856979
latency_cycles : 13
{{< /code >}}

`cordic_model.py` computes what `cordic.sv` computes, **bit for bit**: the same
guard bits, the same arctangent table, an arithmetic shift that truncates the
way `>>>` does, the same saturation on the output. It then measures the result
the way the testbench of the common track does — same 512 vectors, same
floating-point reference — and writes `results.yml`. The 28.66 dB above is the
number the simulation gave for width 8 and 12 stages.

The workflow that runs it is two short files:

{{< code lang=yaml filename="odatix_userconfig/workflows/cordic_model/_settings.yml" >}}
sources:
  path: examples/workflow_cordic_model   # copied into every run directory

progress:
  file: progress.txt
  regex: "Progress: ([0-9]+)"

use_parameters: No

tasks:
  - name: main
    commands:
      - python3 cordic_model.py --width ${WIDTH} --iterations ${ITERATIONS}

variables:
  WIDTH:
    type: range
    settings: {from: 4, to: 16, step: 2}
  ITERATIONS:
    type: range
    settings: {from: 4, to: 24, step: 2}
{{< /code >}}

Each `variables` entry is a parameter domain declared inline, with no folder
and no file per value, and each `${...}` in the command is replaced by the
value of the configuration. `_metrics.yml`, next to it, reads `results.yml` with
the **same metric names** as the simulations — `snr`, `enob`, `rms_error` —
which is what step 4 relies on.

> [!NOTE]
> The variables are called `WIDTH` and `ITERATIONS`, like the parameter domains
> of the architecture you described. That is a choice, not a coincidence: a
> model and the RTL that share their axes share their charts.

## Step 2 — Sweep it

Seven widths and eleven stage counts, 77 configurations — eight times the
design space of the common track:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -W "cordic_model + WIDTH/* + ITERATIONS/*" -y -E
{{< /code >}}

About ten seconds on a laptop. Each configuration runs in its own directory
under `work/workflows/`, and its metrics are in `results/results_workflow.yml`
the moment it is over.

## Step 3 — Find the stages worth paying for

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

1. Chart type **Lines**
2. **Axes** → x: `ITERATIONS`, y: `snr`
3. **Style** → **Color by**: `WIDTH`

One curve per width, and every curve has the same shape: it climbs, peaks, and
goes down. Up to the peak, each stage refines the angle; past it, the angle is
already finer than the datapath can represent, and every further stage only
truncates once more.

{{< details title="What you should see" >}}
SNR in dB:

| width \ iterations | 4 | 6 | 8 | 10 | 12 | 16 | 20 | 24 |
|---|---|---|---|---|---|---|---|---|
| **4** | **10.2** | 7.3 | 4.8 | 3.0 | 1.8 | 0.4 | −0.5 | −1.7 |
| **6** | 20.7 | **21.8** | 19.4 | 17.4 | 15.9 | 14.0 | 13.2 | 11.8 |
| **8** | 22.8 | 31.5 | **32.0** | 30.3 | 28.7 | 26.7 | 25.9 | 24.3 |
| **10** | 22.9 | 34.6 | 42.4 | **42.5** | 41.6 | 39.3 | 38.5 | 36.8 |
| **12** | 23.0 | 34.9 | 46.5 | 53.5 | **53.6** | 51.7 | 50.8 | 49.0 |
| **14** | 23.0 | 34.9 | 46.9 | 58.3 | 64.7 | 64.2 | 62.9 | 61.1 |
| **16** | 23.0 | 34.9 | 46.9 | 58.7 | 69.9 | **75.8** | 74.9 | 73.2 |

(The odd stage counts in between are not swept; the peak of width 14 is at 13
or 14 stages.)
{{< /details >}}

The rule of thumb falls out of the chart: **about as many stages as bits**. And
it says something unflattering about the design space of the whole workshop.
Its stage counts, 12, 16 and 24, are all at or past the peak for widths 4, 8 and
12: two of every three designs synthesized today pay for stages that make them
*less* accurate. Width 8 with 8 stages reaches 32.0 dB, better than the
28.7 dB of 12 stages, with a third fewer of them — and that design is not in
the space at all.

That is what a model is for: ten seconds told us which part of the space is
worth an hour of synthesis.

## Step 4 — Check the model against the RTL

A model is worth what its agreement with the RTL is worth. Here the two share
nine configurations — widths 4, 8, 12 and stages 12, 16, 24 — and their SNRs
are the table of [the common
track](/tutorials/workshop/common/explore/#step-2--chart-the-accuracy),
to the last digit: 1.84, 28.66, 53.61 at 12 stages, and so on.

Explorer reads both files at once, and they share their axes: on the chart of
step 3, switched to **Scatter**, each point of the simulation lies exactly on a
point of the model.

This is the check that makes a model usable. A model that agrees on nine points
spread over the space can be trusted on the 68 others, and on whatever the next
question is; a model that does not is a bug report, either in the model or in
the RTL, found before anyone synthesized anything.

> [!TIP]
> A workflow can also run the reference model of a testbench, a MATLAB script
> (`matlab -batch`), a C++ golden model or a training run: anything that runs
> from a shell and writes a number to a file.

## Step 5 — Take the answer back to the RTL

Add the stage counts the model asks for to your architecture — the one you
described in the common track. They are two more values in the list of its
`ITERATIONS` domain:

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/ITERATIONS/_settings.yml (changed)" >}}
variables:
  ITERATIONS:
    type: list
    settings:
      list: [8, 10, 12, 16, 24]
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix generate --architecture My_Cordic_sv -y
$ odatix sim -s TB_My_Cordic_sv -a "My_Cordic_sv + ITERATIONS/8 + WIDTH/8" -y -E
{{< /code >}}

In VHDL, `My_Cordic_vhdl` and `TB_My_Cordic_vhdl`. The simulation gives the
32.0 dB the model predicted, and the new stage counts are now part of the space
every module and the [finale](/tutorials/workshop/finale/dse/) work on. [Shape your
own design space](/tutorials/workshop/modules/design_space/) goes further: values added
with a rule, and combinations left out before they cost anything.


## If something did not work

| Symptom | What to do |
|---|---|
| `cordic_model` is not listed | The workspace was created before the example was shipped: run `odatix init -y --cordic` in a new directory, and copy `odatix_userconfig/workflows/cordic_model` and `examples/workflow_cordic_model` from it. |
| Every job fails | `python3` must be on the `PATH` of the terminal Odatix was started from. Run the command of step 1 by hand: it prints the error. |
| The progress bar stays at 0 % | Harmless: the model writes `progress.txt` only at the end, and runs too fast for anything in between. |
| `snr` does not appear | Re-export the metrics without running anything: `odatix results workflow`. |

## Next

- [Search the model, synthesize the front](/tutorials/workshop/finale/two_levels/) —
  the follow-up, after the finale: an exploration of the model chooses the few designs
  worth running as RTL.
- [Run a Workflow](/tutorials/run_examples/workflows/) — the other workflow
  examples, one feature each.
- [Create your own workflow](/tutorials/own_designs/workflows/) — your model,
  your arguments, your metrics.
- [Custom workflows](/docs/features/workflows/) — what else a workflow does:
  task graphs, per-platform commands, several results per run.
