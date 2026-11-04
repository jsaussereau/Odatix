---
title: "Shape your own design space"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 6
description: "Module F: add a parameter value with a rule, leave out the combinations that are not worth running, and see the conclusion change."
categories: ["Tutorial", "Design"]
tags: ["workshop", "parameter domains", "configurations", "exclusions"]
featured_image: "/images/features/architecture-exploration.svg"
next_tutorials: ["/tutorials/workshop/finale/dse"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| None — a free simulator for the last step | 25 min | A design space you described, not one you typed out |

This is the module that needs no license, no download and no luck, which makes
it the one to take while somebody else's synthesis is running. It is also the
part of Odatix you will use most on your own designs: everything else in the
workshop is the consequence of what the design space says.

So far the CORDIC has been swept over three widths and three stage counts. By
the end of this module it will have four widths, three of the twelve
combinations will be gone on purpose, and the conclusion of the common track
will have changed.

> [!NOTE]
> Every command runs on **your** architecture, the one you described in the
> common track. They are written for `My_Cordic_sv`; in VHDL, write
> `My_Cordic_vhdl` (and `TB_My_Cordic_vhdl` for a simulation) instead —
> nothing else changes.

## Step 1 — Describe the configurations instead of writing them

In the common track, your `WIDTH` domain listed its values: `4, 8, 12`. A
list is fine for three values; for thirty it is not. Replace it with the rule
that produces them, and extend it to 16 bits at the same time.

In `odatix-gui`, **Configure** → **RTL architectures** → your architecture →
**Edit configs**. In the `WIDTH` domain, open the variable `WIDTH`, set its
type to **Range**, with **From** `4`, **To** `16` and **Step** `4`, and click
**Save rules**. The configurations under the domain follow as you type: four
now, `16` the new one. In the file, that is one line changed:

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/WIDTH/_settings.yml" >}}
variables:
  WIDTH:
    type: range
    settings: {from: 4, to: 16, step: 4}
{{< /code >}}

Editing the file by hand does the same; `odatix generate --architecture
My_Cordic_sv` then writes the configurations out, and says which are new.

{{< code lang=bash filename="Terminal" prompt="true" fold="true" >}}
$ odatix ls -a --arch My_Cordic_sv

Architectures (1)
  My_Cordic_sv
    + ITERATIONS
      12  16  24
    + WIDTH
      4  8  12  16
{{< /code >}}

Twelve combinations now, from one rule — and for every module from
now on: a `WIDTH/*` in another page now selects four widths, not three, so
expect one more job there — and the 16-bit one is the slowest. `range` is one of the
[variable types](/docs/configurations/variables/): there are also lists, powers
of two, computed expressions and set operations, and a domain with several
variables says how they are named and written with
`configurations.name` and `configurations.template`. See [Configuration
generation](/docs/configurations/config_generation/).

> [!TIP]
> In `odatix-gui` → **RTL architectures**, each domain has a **Configuration
> rules** panel: what a rule produces appears among the configurations as you
> type it, before anything is written to disk. It is the fastest way to get a
> rule right.

## Step 2 — Leave out what is not worth running

Twelve combinations, and three of them are a waste of a synthesis: at 4 bits,
the common track measured the accuracy getting **worse** as stages are added
(1.84 dB, 0.42 dB, −1.68 dB). More stages at that width buy nothing and cost
latency, area and truncation noise.

Until now the only way to leave such a point out was to not write the sweep line
that produces it — in `sim_settings.yml`, then in `fmax_settings.yml`, then in
every campaign, and nowhere a search could read it. An **exclusion** says it
once, next to the design:

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/_settings.yml" >}}
exclusions:
  - id: narrow-datapath-many-stages
    when: "$WIDTH == '4' and $ITERATIONS != '12'"
    kind: dominated
    message: "4 bits cannot represent what 16 or 24 stages compute: the extra stages only add truncation noise, latency and area"
{{< /code >}}

> [!WARNING]
> A configuration name is a **string**: `$WIDTH == '4'`, not `$WIDTH == 4`. An
> expression that reads a name nothing defines is false rather than broken — so
> a rule with a typo in it silently leaves nothing out. The **Exclusions** tile
> of the architecture editor has a **Check against the configurations** button
> that says how many combinations each rule actually removes, and shows one of
> them.

### The three kinds, and why this one is not applied yet

Run anything on the full selection and answer `n` at the question: the job list
Odatix prints **before** asking is the cheapest dry run there is.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze --tool verilator -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*"
{{< /code >}}

Every combination of the space is still listed: the exclusion changed nothing.
That is correct, and it is the distinction worth taking away:

| `kind` | Means | Applied |
|---|---|---|
| `illegal` | the design does not work: the elaboration fails, the RTL asserts | always |
| `duplicate` | the design works and is the very same hardware as another one | always, by snapping to the canonical value |
| `dominated` | the design works and is its own, but another one beats it on everything you are looking for | only when a campaign asks for it |

`dominated` is knowledge about **an objective**, not about the design: it
depends on what you are looking for, so a plain sweep keeps the points and a
campaign chooses. Change the `kind` to `illegal` and the same command lists ten
combinations instead of twelve — then change it back, because those designs are
not illegal, they are just not interesting.

In a campaign, this turns it on ([finale](/tutorials/workshop/finale/dse/)):

{{< code lang=yaml filename="odatix_userconfig/dse_campaigns/cordic_accuracy_area.yml" >}}
exclusions:
  apply: [illegal, duplicate, dominated]
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" >}}
$ odatix dse -p cordic_accuracy_area -C

[odatix dse] [cordic_accuracy_area] Exploring "My_Cordic_sv/*+ITERATIONS/*+WIDTH/*": 390 designs, 18 of them evaluated at most, 4 at a time, by bayesian search. The frequency is searched too, between 100 and 400 MHz (13 values). What runs a design is searched too, out of vivado@standard, vivado@area, vivado@performance (3 combinations). Runs continuously: a new design starts the moment a slot frees, instead of waiting for the rest of the batch. 1 exclusion(s) (1 dominated) take 78 combination(s) out of the space. Only designs with Worst_Slack >= 0.0 count.
{{< /code >}}

Ten combinations instead of twelve, each at thirteen frequencies and with three
strategies: 390 designs instead of 468. `-C` checks a campaign without running anything — the
other free dry run. The campaign itself is written in the
[finale](/tutorials/workshop/finale/dse/).

## Step 3 — See the conclusion change

The three new configurations cost one simulation each. Run only them:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -s TB_My_Cordic_sv -a "My_Cordic_sv + ITERATIONS/* + WIDTH/16" -y -E
{{< /code >}}

Under twenty seconds, and the chart of the common track now says something
different. Up to 12 bits, extra stages were pure loss. At 16 bits they are not:

| width \ iterations | 12 | 16 | 24 |
|---|---|---|---|
| **4** | 1.84 | 0.42 | −1.68 |
| **8** | 28.66 | 26.71 | 24.28 |
| **12** | 53.61 | 51.69 | 49.03 |
| **16** | 69.86 | **75.82** | 73.24 |

The best point is no longer at the edge of the space — it is inside it, at 16
bits and 16 stages, and nothing in the first nine runs could have told you. One
value added to one domain moved the answer.

> [!NOTE]
> This is the argument for exploring rather than guessing, and the reason the
> [finale](/tutorials/workshop/finale/dse/) exists: the interesting region of a design
> space is rarely where you first looked, and it moves as soon as the space
> changes.

## If something did not work

| Symptom | What to do |
|---|---|
| `odatix generate` wrote nothing | The rule has to be in the domain's `_settings.yml`, under a root-level `variables:` key. Check the indentation: the `settings` of a variable is nested under it. |
| The rule produces names you did not expect | `odatix generate` lists what it would write before writing it, and the GUI shows the same thing live. |
| You edited a generated file by hand and want it back | `odatix generate -o` takes hand-edited configurations back to what their rule says; `odatix generate -C` deletes the ones no rule describes any more. |
| Your exclusion removes nothing | Almost always the quoting: `'4'`, not `4`. **Check against the configurations** in the GUI tells you in one click. |
| Your exclusion removes everything | `when` is the condition for **rejecting** a point, not for keeping it. A bare expression (`- "$a <= $b"`) means the opposite: what has to be true. |

## Next

- [Accuracy against cost](/tutorials/workshop/modules/accuracy/) — now that the space has
  a best point, what does it cost?
- [Let the search do the work](/tutorials/workshop/finale/dse/) — 390 designs is already
  more than a slot can sweep.
- [Exclusions](/docs/configurations/exclusions/) and [Parameter
  domains](/docs/configurations/param_domains/) — the references behind this
  module.
