---
title: "Hands-on workshop"
weight: 4
description: "A one-and-a-half to three-hour guided session taking a signal processing design from RTL to a Pareto front, with the tools each participant actually has."
---

In one session you are going to take a signal processing design from plain RTL
to a Pareto front: simulate it, measure its accuracy, implement it on an FPGA
and on an ASIC technology, model it in Python, shape its design space, and let an automated
exploration find the designs worth keeping — without writing a script, and with
whatever tools you have on your own machine.

The design is one that ships with Odatix: a **pipelined CORDIC rotation core**,
swept over its datapath width and its number of rotation stages. It simulates in
seconds, synthesizes in minutes, and trades accuracy against area and latency —
the kind of two-dimensional trade-off worth drawing a chart of.

Everything stays yours afterwards: the workspace, the results, and these pages,
to replay at your own pace on your own designs.

## How the session is organized

{{< img src="/images/diagrams/workshop-flow.svg" title="Three parts: a 75-minute common track on free tools, then two or three independent modules of your choice, then a 45-minute finale running an automated exploration" shadow="false" >}}


## Before you start

Fifteen minutes, best done before you sit down — not in the room.

### 1. Install Odatix

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m venv odatix_venv
$ source odatix_venv/bin/activate
$ pip install odatix
$ odatix -v
{{< /code >}}

Other ways to install it, offline included, are on the
[installation pages](/install/).

### 2. Install OSS CAD Suite

One download holds every tool the common track runs, free and without a
license, on Linux, macOS and Windows: **Yosys** and **nextpnr**, which
synthesize, place and route the design for a Lattice FPGA, and the simulators
**Verilator** (SystemVerilog) and **GHDL** (VHDL). Extract it and put its `bin`
directory on the `PATH`: [Install the OSS CAD Suite](/install/oss_cad_suite/)
says how, step by step.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ yosys -V
$ nextpnr-ecp5 --version
$ verilator --version
$ ghdl --version
{{< /code >}}

### 3. Optionally, your own synthesis tool

Every page is written for Yosys + nextpnr (`yosys_fpga` in Odatix), and every
step that synthesizes has a tab for **Vivado**, **Quartus**, **Design
Compiler**, **Genus** or **LibreLane** too. Take one of them if you have it and
would rather see its numbers: the commands only change by `--tool`.

### 4. Check what Odatix finds

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

The **Tools** page says, tool by tool, whether Odatix finds it and what it
answers — the fastest way to know which modules you will be able to run. Close
it with <kbd>Ctrl</kbd>+<kbd>C</kbd>. It is also where the common track
starts: if it opens here, you are ready.

> [!IMPORTANT]
> A tool has to work in your terminal **before** Odatix can drive it:
> `yosys -V`, `vivado -version`, `quartus_sh --version`, `dc_shell -version`,
> `vsim -version`. If one of them does not answer, source the setup script of
> your installation in that terminal (see [Install supported EDA
> tools](/install/eda_tools/#install-vivado)), and start Odatix from there.


### Part 1 — The common track

Everyone, together, in SystemVerilog or VHDL — your choice. In the graphical
interface, you describe the design to Odatix yourself and read the files the interface
wrote, check it with an RTL analysis, and start its synthesis; while it runs,
you write the simulation, run it, and chart the accuracy
and the cost of nine configurations. A free
simulator is all it strictly needs: the synthesis runs with whichever tool you
have, and the room reaches the same charts at the same time.

{{< tutorial-cards pages="common/workspace,common/describe,common/analysis,common/synthesis,common/simulate,common/explore" cols="3" >}}

### Part 2 — The modules, your pick

Choose the ones that match your interests and the tools you have at hand —
inside a module, every step has a tab per tool it accepts, so a module is never
tied to one vendor. Two or three fit in the slot. They are independent of each
other and of the order you take them in — nobody is waiting for a neighbour to
finish, and skipping one costs you nothing later.

| Module | What it adds | Tools |
|---|---|---|
| A — [How fast can it go?](/tutorials/workshop/modules/fmax/) | The maximum frequency of each configuration | Yosys + nextpnr, or Vivado, Quartus, Design Compiler, Genus |
| B — [Accuracy against cost](/tutorials/workshop/modules/accuracy/) | Simulation and synthesis results merged into one set: the accuracy of each design next to its cost | None, no new run |
| C — [The algorithm before the RTL](/tutorials/workshop/modules/workflow/) | A bit-accurate Python model swept as a workflow, checked against the RTL | Python 3 |
| D — [ASIC with open-source tools](/tutorials/workshop/modules/asic/) | A routed sky130 layout | LibreLane |
| E — [Place and route after synthesis](/tutorials/workshop/modules/pnr/) | The netlists of a synthesis placed and routed by another tool | Design Compiler or Genus, and Innovus |
| F — [Shape your own design space](/tutorials/workshop/modules/design_space/) | Rules and exclusions instead of lists | None |

Module B is the one the finale needs: it is what makes the accuracy a metric of
the synthesis results, and every result the other modules add is merged the
same way.

{{< tutorial-cards pages="modules/fmax,modules/accuracy,modules/workflow,modules/asic,modules/pnr,modules/design_space" cols="3" >}}

### Part 3 — The finale

Everyone again, on one exploration — the part that uses everything the modules
produced.

{{< tutorial-cards pages="finale/dse" cols="3" >}}

### Optional — After the finale

For those who finish early, or at home, once module C is done: two chained
explorations — the model chooses, the RTL confirms.

{{< tutorial-cards pages="finale/two_levels" cols="3" >}}

> [!TIP]
> Short of time, or following these pages on your own? [Create a
> workspace](/tutorials/workshop/common/workspace/), the two pages of the common
> track and the finale, with nothing in
> between, make a 90-minute session that still goes from RTL to a Pareto front.

## After the workshop

- [Run Odatix on your own designs](/tutorials/own_designs/) — the same thing,
  with your RTL.

> [!TIP]
> Giving this workshop to a room of your own? [Running the session](/tutorials/workshop/running_the_session/) has what to prepare, how long each run really takes, and how to pace the time.
