---
title: "Running the session"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 5
description: "For whoever gives the workshop: what to prepare, how long each run really takes, how to pace the time, and what to have ready when a tool lets someone down."
categories: ["Tutorial", "Workshop"]
tags: ["workshop", "teaching", "organization"]
featured_image: ""
next_tutorials: ["/tutorials/workshop/common/workspace"]
---

{{< toc >}}

This page is for the person **giving** the workshop. The participants' material
is the rest of the section, starting at [Hands-on
workshop](/tutorials/workshop/) — nothing in those pages addresses you, so they
can be handed out as they are.

What the room is going to do: the [common
track](/tutorials/workshop/common/describe/) together, then two or three of the
six modules each at their own pace, then the
[exploration](/tutorials/workshop/finale/dse/) together. The design is the CORDIC core
of `odatix init --cordic`, so there is no repository of yours to distribute.

Every participant describes that core to Odatix themselves, at the start of the
common track — `My_Cordic_sv` or `My_Cordic_vhdl`, their choice — and every
module and the finale then run on **that** description. `odatix init
--cordic-solution`, in another directory, gives the answer under names of its
own (`My_Cordic_sv_solution`, ...); a participant too far behind copies it
under their name (`cp -r ~/odatix_workshop_answer/odatix_userconfig/architectures/My_Cordic_sv_solution odatix_userconfig/architectures/My_Cordic_sv`,
and the simulation likewise) and catches up in a minute.

## What to prepare

**Hand out the workspace, not just the install.** A directory that already holds
`odatix init --cordic` saves fifteen minutes of downloads at the start.

**Put a results bundle in it**, made on the names the participants use:
replay the common track as a participant would, so that the bundle holds
`My_Cordic_sv` results. A complete `results/` directory from a full run
of every module is the fallback that keeps a participant in the session when a
tool, a license or a machine lets them down: they open `odatix-explorer` on it
and follow every analysis. The participants' pages refer to it as *the results
bundle*, and tell them to ask you for it.

**The OSS CAD Suite covers most of the room.** Every page is written for
Yosys + nextpnr: with Odatix and the [OSS CAD Suite](/install/oss_cad_suite/),
a participant runs the common track, module A, module B, module F and the
finale on their own laptop, Linux, macOS or Windows, without a license. Ask
them to install both before the session.

**One virtual machine covers the rest.** Odatix, the OSS CAD Suite, Vivado and
LibreLane in one image means every module is doable by everyone. Participants
who came with their own licensed tools work on their own machine: every module
has a tab per tool it accepts.

**Prepare LibreLane in the image.** Its first run downloads its tools through
Nix and its PDK through ciel — hundreds of megabytes, and not something to do
on conference Wi-Fi. Run `librelane --smoke-test` in the image before the
session, so the ASIC module starts on a warm install.

**Have a plan for the network.** USB sticks with the image, and the
[offline installation](/install/offline/) of Odatix, cost nothing to prepare
and save the session when the room's Wi-Fi collapses.

**A shared server is an option.** One machine holding the licenses, participants
over SSH, jobs in detached sessions: see [Access Odatix over
SSH](/tutorials/ssh/). Give each participant their own workspace directory, and
mind the parallelism — twenty people at `-j 8` on one server is not twenty
people getting results.

## How long the runs really take

Measured on a laptop with Yosys + nextpnr (OSS CAD Suite of October 2026), on
an ECP5 (`ecp5-25k-CABGA381-6`), every job through placement and routing:

| Run | Time |
|---|---|
| The nine syntheses of the common track, `--at 100`, `-j 4` | about 2 minutes |
| **One fmax search** (three in parallel) | **about a minute** |
| The exploration of the finale (18 designs, `-j 4`) | about 4 minutes |

Measured on the same laptop with Vivado 2024.2, on an Artix-7
(`xc7a100t-csg324-1`), with the CORDIC of the workshop:

| Run | Time |
|---|---|
| RTL analysis of the nine configurations, Verilator | about 10 seconds |
| The nine simulations of the common track, Verilator / GHDL | about 30 / 10 seconds |
| The nine syntheses of the common track, `--at 100 --until synthesis`, `-j 4` | about 12 minutes |
| **One fmax search**, `--until synthesis` (three in parallel) | **about 12 minutes** |
| One fmax search **through place and route** | about an hour |
| Twelve fixed-frequency syntheses, `--at 100 --until synthesis`, `-j 4` | about 10 minutes |
| The exploration of the finale (18 designs, `until: synthesis`, `-j 4`) | about 20 minutes |
| The 77 runs of the CORDIC model (optional part), `-j 8` | about 10 seconds |
| The exploration of the model, 60 of 391 designs | about 35 seconds |
| Five syntheses of its front, `--at 100 --until synthesis`, `-j 5` | about 4 minutes |

With the other tools the modules accept, on the same machine, four configurations each:

| Run | Time |
|---|---|
| fmax search, Quartus Pro 26.1 on Agilex 3, `--until synthesis` | about 15 minutes |
| fmax search, Design Compiler on AMS C35 (350 nm) | about 33 minutes |
| fmax search, Genus on AMS C35 | about 3 hours — out of reach of a module |
| fmax search, LibreLane on sky130 (synthesis), `--from 10 --to 150` | about 4 minutes |
| One LibreLane job at 40 MHz `--until route` | about 5 minutes |

Two consequences the participants' pages already follow, and that are worth
keeping if you adapt them:

- an fmax search is a series of syntheses, so the FPGA module runs **three** of
  them, not nine, and covers the rest of the design space with one
  fixed-frequency synthesis per design;
- a virtual machine sharing those same cores is routinely two to three times
  slower, so **time the runs on your image**, not on your own machine, and
  shrink the selections (`-a`, `--until`) until they fit.

Narrowing the `fmax_synthesis` bounds of the architecture (50–800 MHz by
default) cuts iterations off every search, and is the cheapest way to make the
module fit without changing what it teaches.

## What participants trip over

Found by running every page end to end, and already handled in the pages — worth
knowing so that you recognize them in the room:

- **A laptop on battery** saving energy runs synthesis several times slower.
  Ask for chargers, and time the runs plugged in.
- **The design space module changes the other modules.** Once `WIDTH/16` exists,
  every `WIDTH/*` selects four configurations instead of three, and the 16-bit
  one is the slowest. Fine, as long as nobody is surprised by a fourth job.
- **Two simulators on the same configuration** (Verilator in the common track,
  Questa in another module) make a derived metric ambiguous: Odatix refuses to
  choose, and `snr` is computed nowhere. The accuracy module says how to set
  **On Multiple Matches** to `first`.
- **Two `derived_metrics:` keys** in that file: the second silently replaces the
  first, and `snr` disappears from every result.
- **Design Compiler and Genus refuse `--until synthesis`**: their fmax search is
  a single step. Quartus accepts it, but its fmax after synthesis is the same for
  every configuration (the clock network's minimum pulse width) — meaningless
  before place and route. Its area metric is `ALM_count`.
- **LibreLane on sky130 runs the CORDIC at 40–63 MHz**, below the default
  lower bound of the search (50 MHz): without `--from 10`, the wider
  configurations fail with *No timing met*.
- **The ASIC targets are examples.** The Genus target is AMS C35 like the Design
  Compiler one; anyone with another library edits the technology script of the
  target before anything else.
- **A tool installed outside the `PATH`.** Quartus is found through
  `tool_install_path` in `target_quartus.yml` (the directory holding
  `qinit.sh`). A `PATH` entry written relative (`.local/bin/...`) only works
  from the home directory: the tool answers there, and nowhere else — the
  workspace included, where the Tools page then shows it as *not installed*.

## Pacing

{{< tabs >}}

{{% tab name="Three hours" %}}

| | Part | Who |
|---|---|---|
| 35 min | [Describe the design](/tutorials/workshop/common/describe/), [check it](/tutorials/workshop/common/analysis/) and [synthesize it](/tutorials/workshop/common/synthesis/), in `odatix-gui` — project yours and do it with the room | everyone, together |
| 40 min | [Simulate it while it synthesizes](/tutorials/workshop/common/simulate/), then [explore the results](/tutorials/workshop/common/explore/) | everyone, at their own pace, the synthesis running |
| 65 min | two or three modules, from [How fast can it go?](/tutorials/workshop/modules/fmax/) to [Shape your own design space](/tutorials/workshop/modules/design_space/) — [Accuracy against cost](/tutorials/workshop/modules/accuracy/) is the one the finale needs | each at their own pace |
| 45 min | [Let the search do the work](/tutorials/workshop/finale/dse/), then questions | everyone, exploration running |

{{% /tab %}}

{{% tab name="Ninety minutes" %}}

| | Part | Who |
|---|---|---|
| 40 min | [Describe the design](/tutorials/workshop/common/describe/) and [check it](/tutorials/workshop/common/analysis/), without its synthesis, then [simulate it](/tutorials/workshop/common/simulate/) and [chart it](/tutorials/workshop/common/explore/) | everyone, together |
| 40 min | [Let the search do the work](/tutorials/workshop/finale/dse/), on the workflow campaign of its step 1 | everyone |
| 10 min | what the modules would have added, and where the pages are | — |

No synthesis tool is needed for that variant: the exploration of step 1 runs a
workflow, in seconds per batch.

{{% /tab %}}

{{< /tabs >}}

Start the exploration of the finale **at the beginning** of the finale, not at
the end. It improves its front while you present how it works, and the room
watches its own search progress — which is the demonstration.

## Keeping the room busy

Waiting is part of hardware design, and a room watching a progress bar is a room
losing its afternoon. Three things that work:

- **Launch, then explain.** Every long run in the pages comes before the text
  that explains it. Say it out loud at the start: the command first, the slide
  after.
- **Project the Job Monitor.** Waiting becomes something to look at, and the
  parallelism of the daemon becomes obvious without a word.
- **Point the fast finishers at [Shape your own design
  space](/tutorials/workshop/modules/design_space/).** It needs no EDA tool, so it fits
  entirely inside somebody else's synthesis, and it ends on a result that
  changes the conclusion of the common track.

## When something lets a participant down

| What happened | What to say |
|---|---|
| No license, or a tool missing | The OSS CAD Suite needs none: Yosys + nextpnr is the default of every page. Every module names the other tools it accepts. |
| A machine too slow for the slot | One configuration instead of nine, and `--until synthesis`. The story is the same. |
| A failed job | Nothing is blocked: `odatix results` exports what succeeded, and the module goes on. |
| Nothing runs at all | The results bundle. Every analysis and every chart of every module can be followed on it. |
| Someone lost in the monitor | <kbd>d</kbd> detaches, `odatix monitor` re-attaches, `odatix stop` ends the session. |
| An unexplained symptom | [Troubleshooting](/docs/troubleshooting/) opens with a triage list, and `odatix_error.log` holds the trace to send you. |

## Adapting the material

Nothing in these pages is specific to a conference. The design, the testbench,
the configurations and the two exploration campaigns all come from
`odatix init --cordic`, so the only thing to decide for another audience is
which modules to offer.

- **Another design.** Swapping the CORDIC for one of yours is [Implement your
  own RTL](/tutorials/own_designs/architecture/); the module pages then apply
  unchanged, as long as the design has two parameters worth crossing and a
  testbench that reports a quality metric.
- **Another audience.** For a class, the common track plus the design space
  module fills two hours with no EDA tool at all. For a team already running
  synthesis, the finale is the part they came for.
- **More time.** Place and route (drop `--until synthesis`), the signoff step of
  LibreLane, and a second campaign asking a different question of the same
  design all extend the session without new material.

## Checklist

**The week before**

- [ ] The participants told to install Odatix and the OSS CAD Suite beforehand
- [ ] The image built, with Odatix, the OSS CAD Suite, Vivado and LibreLane
- [ ] `librelane --smoke-test` run once in the image
- [ ] A workspace with `odatix init --cordic` and a complete `results/` bundle
- [ ] Every run of the modules you plan to offer, timed on that image
- [ ] USB sticks with the image and the offline install

**The day of**

- [ ] The `_index.md` setup steps sent to the participants in advance
- [ ] Projector showing a terminal large enough for the Job Monitor
- [ ] A second machine, or a second terminal, to answer a question without
      losing your own run
- [ ] The exploration of the finale checked with `odatix dse -C` on the image
