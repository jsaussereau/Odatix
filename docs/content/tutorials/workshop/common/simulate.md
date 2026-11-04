---
title: "Simulate it while it synthesizes"
date: 2026-10-25
author: "Jonathan Saussereau"
weight: 5
description: "The common track, second half: while the synthesis runs, create the simulation of the CORDIC in odatix-gui and run it on the nine configurations."
categories: ["Tutorial", "Simulation"]
tags: ["workshop", "simulation", "testbench", "cordic"]
featured_image: "/images/features/simulation.svg"
next_tutorials: ["/tutorials/workshop/common/explore"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Verilator **or** GHDL | 25 min | Nine configurations simulated, their accuracy measured |

A **simulation** runs a testbench on each configuration of an architecture, and
turns what the testbench measures into metrics. The synthesis of [the previous
page](/tutorials/workshop/common/synthesis/) is still running: leave it, this
page needs nothing but your simulator.

> [!NOTE]
> The architecture is synthesizing, but editing next to it is safe: each job
> works on its own copy, made when it started.

## Step 1 — Look at what the testbench measures

The testbench is in `examples/cordic_tb/`, one per language. It drives the core
through its ports only, sweeps 512 vectors over a full turn, and compares them
with a floating-point reference.

It takes the configuration it tests from two parameters of its own, with the
same names as those of the core:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=systemverilog filename="examples/cordic_tb/tb_cordic.sv" >}}
module tb_cordic #(
  parameter int WIDTH = 16,
  parameter int ITERATIONS = 12
);
  ...
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=vhdl filename="examples/cordic_tb/tb_cordic.vhdl" >}}
entity tb_cordic is
  generic (
    WIDTH : integer := 16;
    ITERATIONS : integer := 12
  );
end entity tb_cordic;
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

It writes its measurements to a file of its own, `results.yml`, in the
directory it runs in:

{{< code lang=yaml filename="results.yml (width 8, iterations 12)" >}}
latency_cycles: 13
snr_db: 28.662130
enob: 4.856248
status: OK
...
{{< /code >}}

> [!TIP]
> `snr_db`, `enob` and `latency_cycles` are the keys you will turn into metrics
> at step 3.

## Step 2 — Create the simulation

Click on **RTL architectures**, then **Create new simulation**, at the bottom
of the page.

1. Type the name at the top: `TB_My_Cordic_sv` (or `TB_My_Cordic_vhdl`).
2. **Template** → **Starts from**: `verilator` for SystemVerilog, `ghdl` for
   VHDL.
3. **Testbench** → **Top**: `tb_cordic`.
4. **Testbench** → **Files**: `examples/cordic_tb/tb_cordic.sv` (or `.vhdl`).
   The folder button browses the workspace.
5. **Testbench** → **Parameters**: `WIDTH: ${WIDTH}` and
   `ITERATIONS: ${ITERATIONS}`, one per line.
6. **Architectures** → **Add an architecture**: your `My_Cordic_sv` (or
   `_vhdl`) is added.
7. Click **Save all**.

{{< img src="/images/screenshots/workshop/gui-sim-settings.png" title="The new simulation: the verilator template, and the testbench with its two parameters" >}}

The **template** is the simulator, ready to use: it compiles the design and the
testbench, runs them, and reports how it went. There is no script to write.
Other templates are `icarus`, `questa` and `xsim`.

> [!TIP] On Windows
> Verilator builds a C++ simulator, and the OSS CAD Suite for Windows has no
> C++ compiler. Unless you installed one (see [Verilator simulations on
> Windows](/install/oss_cad_suite/#verilator-simulations-on-windows)), start
> from `icarus` instead: it simulates the same testbench, with the same
> results to the last digit.

`${WIDTH}` is the value of the variable `WIDTH` the configuration was made
from: for `ITERATIONS/12 + WIDTH/8`, the testbench gets `WIDTH = 8` and
`ITERATIONS = 12`.

> [!IMPORTANT]
> Whichever simulator it is, it has to work in your terminal before Odatix can
> drive it: `verilator --version` or `ghdl --version`.

## Step 3 — Turn the measurements into metrics

Click **Edit metrics**, at the top of the simulation. The metrics already listed
come from the template (whether the simulation passed, how long it took). Add
the ones of the testbench:

| Metric | Type | File | Key | Unit | Format |
|---|---|---|---|---|---|
| `snr` | YAML | `results.yml` | `snr_db` | `dB` | `%.2f` |
| `enob` | YAML | `results.yml` | `enob` | `bits` | `%.2f` |
| `latency` | YAML | `results.yml` | `latency_cycles` | `cycles` | `%.0f` |

For each one:

1. **Add new metric**, and type its name over the provisional one.
2. Set its type to **YAML**, then fill in the file and the key.
3. Open the card with its arrow for the unit and the format.

{{< img src="/images/screenshots/workshop/gui-sim-metric.png" width="70%" align="center" title="The snr metric: the key snr_db of results.yml, in dB" >}}

Then click **Save all**.

> [!NOTE]
> The simulation goes into two files of the workspace,
> `odatix_userconfig/simulations/TB_My_Cordic_<language>/_settings.yml` and
> `_metrics.yml`: one line per field of the forms. You can also edit them by hand.

## Step 4 — Run the simulation

Click on **Run** → **Simulations**:

1. Switch on your simulation, then, inside it, your architecture: nine
   configurations.
2. **Run jobs**, then **Start**.

{{< img src="/images/screenshots/workshop/gui-sim-select.png" title="The simulation, its architecture and the nine configurations it runs on" >}}

The simulations run next to the synthesis, on the same daemon. With Verilator,
the nine take about half a minute, most of it compiling; with GHDL, about ten
seconds.

{{< img src="/images/screenshots/workshop/gui-sim-monitor.png" title="Nine simulations, all passed" >}}

Each result goes into `results/results_simulation.yml` as soon as its job is
over.

The next page opens Odatix Explorer on these results — and on those of the
synthesis, which should be about done by now — and puts the accuracy and the
cost of the nine configurations on charts.
