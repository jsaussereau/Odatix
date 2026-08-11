---
title: "Place & Route"
description: "Chain two EDA tools: place & route a netlist another tool synthesized, with Innovus, IC Compiler II or a tool of your own, and get post-route numbers."
layout: "doc-features"
badge: "Implementation"
badgeColor: "#0d9488"
cta: true
weight: 5
aliases:
  - /docs/pnr/
features:
  - title: "Two tools, one flow"
    description: "Synthesize with one tool, implement with another — Design Compiler + Innovus, Genus + ICC2, or your own pair."
  - title: "Post-route numbers"
    description: "Real interconnect instead of estimates, next to the synthesis figures in the same results files."
  - title: "Selectable sources"
    description: "Pick which synthesis jobs get implemented with a wildcard selector, from the settings file or the command line."
  - title: "Resumable steps"
    description: "init, place, cts, route and signoff run as separate processes, so a run picks up where the last one stopped."
---

> [!IMPORTANT] Requires Odatix 4.0+

## From netlist to implemented design

`odatix pnr` is the one job type that **chains two EDA tools**. It does not start
from your RTL: it starts from a synthesis job that has already run and succeeded,
and places & routes it with another tool.

That is exactly what a Design Compiler + Innovus or a Genus + ICC2 flow is — two
commands instead of one:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t design_compiler                      # synthesize
$ odatix pnr  -t innovus --from-tool design_compiler   # implement
{{< /code >}}

The point is post-route numbers. A synthesis reports estimated timing and area;
only place & route says what the design really achieves, with real interconnect.

<!-- ![Post-route Fmax against cell area for a counter on sky130A, one point per configuration](/images/screenshots/pnr.png) -->

## When you need it

- **Signing off an ASIC design point.** Synthesis estimates are enough to compare
  configurations; they are not enough to commit to one.
- **Quantifying the estimation gap.** Both runs export into the same results
  files, so Explorer can put the estimate and the implemented result side by
  side, per configuration.
- **Implementing only what deserves it.** Screen a whole design space with
  synthesis, then place & route the handful of configurations that survived.
- **Bringing your own back end.** Any tool that can read a netlist, an SDC and an
  SDF can be wrapped as a place & route tool.

> [!NOTE]
> `pnr` is also the name of a *step* inside the FPGA flows of Vivado. There,
> place & route happens within the same tool and the same job, so no `odatix pnr`
> run is involved. The `pnr` **command** is for the case where the netlist
> crosses from one tool to another. See [Steps](/docs/reference/tools/#steps).

## How it works

A place & route job takes a completed **fmax** or **custom frequency** synthesis
job as its input, and reads three handoff files that synthesis wrote in its
result directory:

| File | Content |
|------|---------|
| `result/netlist.v` | The synthesized gate-level netlist. |
| `result/design.sdc` | The timing constraints it was synthesized under. |
| `result/design.sdf` | The delays back-annotated from synthesis. |

> [!IMPORTANT]
> A synthesis job can only feed a place & route run if its flow actually wrote
> those three files. A flow that never writes them cannot be a source, whatever
> its status says.

The place & route tool reaches them through the `$source_netlist`, `$source_sdc`
and `$source_sdf` variables, plus `$source_work_path` pointing at the synthesis
job directory itself — so a tool of your own can read anything else that run left
behind.

A place & route flow is split into ordered, resumable
[**steps**](/docs/reference/tools/#steps) — `init`, `place`, `cts`, `route`,
`signoff` for both shipped tools. Each runs as its own process and hands the
design over through a saved design database, so a run can stop partway and a
later one picks up where it left off instead of starting over.

Odatix ships two place & route tool definitions, **Innovus** and **IC Compiler
II**. Both declare `pnr` as their only job type, so they never appear as a target
for `odatix fmax` or `odatix synth`.

> [!WARNING]
> These two definitions are a **starting point, not a validated flow**. The steps
> run the usual sequence, but the technology setup — LEF, QRC, MMMC, NDM
> libraries, power intent — is design and foundry specific and lives in the
> technology script your target file brings in. Adjust them to your PDK before
> trusting the numbers.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Custom-frequency synthesis](/docs/features/rtl_synthesis/) · [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) | Where the source jobs come from — a place & route run has nothing to do without one. |
| [Architecture exploration](/docs/features/architecture-exploration/) | The source selector accepts wildcards, so a whole set of configurations is implemented in one command. |
| [Explorer](/docs/features/explorer/) | Compare post-route reality against the synthesis estimate that predicted it. |
| [Tools](/docs/tools/add_tools/) | Adding a place & route tool is declaring `pnr_steps` in a `tool.yml`. |

## Using it

### From the configuration files and the CLI

Which synthesis jobs to implement is declared in
`odatix_userconfig/pnr_settings.yml`, using a selector per entry:

{{< code lang=text filename="Selector grammar" >}}
<source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]
{{< /code >}}

`*` is accepted at every level. `<source_type>` is `fmax_synthesis` or
`custom_freq_synthesis`; the trailing frequency only applies to the latter.

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
nb_jobs: 8

sources:
  - custom_freq_synthesis/design_compiler/gf22/Example_ALU_sv/08bits@100MHz
  - fmax_synthesis/genus/gf22/Example_Counter_sv/*
  - custom_freq_synthesis/*/*/*/*        # everything that can be implemented
{{< /code >}}

The command line narrows the same selection without editing the file, and steps
control how far a run goes:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix pnr -t innovus --from-tool design_compiler
$ odatix pnr -t innovus --from-type fmax_synthesis
$ odatix pnr -t icc2    --from-tool genus --from-flow fast
$ odatix pnr -t innovus --until route          # stop after routing
$ odatix pnr -t innovus --rerun-from place     # redo placement onwards
{{< /code >}}

| Option | Meaning |
|--------|---------|
| `--from-type` | Only the synthesis jobs of this type (`fmax_synthesis` or `custom_freq_synthesis`). |
| `--from-tool` | Only the jobs run with this eda tool. |
| `--from-flow` | Only the jobs run with this flow of `--from-tool`. |

Every key is on the
[run settings reference](/docs/reference/run_settings/#sources--place--route-inputs);
every option, including the shared runtime ones, on the
[commands reference](/docs/commands/).

### From the GUI

`odatix-gui` → **Run** → **Place & Route** lists the tools that declare a `pnr`
job type, then the sources actually available in your work directory — so you
pick from what exists rather than guessing a selector. Choosing a step on the
tool's card runs up to that step. The page writes `pnr_settings.yml` and
enqueues into the same daemon as the CLI.

## Where to go next

- **Tutorial** — [Place & route a synthesized design](/tutorials/run_examples/pnr/).
- **Reference** — [Run settings files](/docs/reference/run_settings/#sources--place--route-inputs) · [Tool definitions](/docs/reference/tools/#steps) · [Target files](/docs/reference/targets/)
- **Guides** — [Tools and flows](/docs/tools/) · [Results & export](/docs/results/) · [Commands](/docs/commands/)
- **Related feature** — [Automated RTL synthesis](/docs/features/rtl_synthesis/), where the source jobs come from.
