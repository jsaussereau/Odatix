---
title: "Simulate your own RTL architectures"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 2
description: "Connect your own testbench to an Odatix design, run it across every configuration with any simulator, and export what it measures as metrics."
categories: ["Tutorial", "Simulation"]
tags: ["simulation", "own design"]
featured_image: "/images/tutorials/own-simulation.svg"
---

{{< toc >}}

This tutorial runs a design you already described in Odatix through a
simulator, on every one of its configurations. You write the testbench, and
nothing else: compiling, elaborating and running it is the job of the
[simulation templates](/docs/reference/simulation/#templates) Odatix provides.

| Template | Simulator | Languages |
|----------|-----------|-----------|
| `icarus` | Icarus Verilog | Verilog, part of SystemVerilog |
| `verilator` | Verilator 5 | Verilog, SystemVerilog |
| `ghdl` | GHDL | VHDL |
| `questa` | Questa, ModelSim | VHDL, Verilog, SystemVerilog, mixed |
| `xsim` | Vivado simulator | VHDL, Verilog, SystemVerilog, mixed |

## Prerequisites

- The `MyCounter` architecture of [Implement your own RTL
  architectures](/tutorials/own_designs/architecture/): the counter of
  `rtl/counter.v`, whose configurations `8bits`, `16bits` and `32bits` are
  built from the variable `width`.
- One of the simulators above in your `PATH`. Icarus Verilog and Verilator are
  free and packaged by most Linux distributions.

## Step 1 — Write a testbench

The testbench is an ordinary one, in the language of your choice. Odatix only
asks three things of it:

- it **ends by itself** (`$finish`, or `std.env.finish` in VHDL);
- it **reports a failure as an error** (`$error`, `$fatal`, or an `assert` of
  severity `error` in VHDL): the simulation is then failed;
- it takes the parameters of the configuration as **parameters (generics) of
  its top**, here `BITS`.

{{< code lang=systemverilog filename="tb/tb_counter.sv" linenos="true" >}}
module tb_counter #(
  parameter BITS = 8
);
  localparam int CYCLES = 1000;

  logic            clock = 0;
  logic            reset = 1;
  logic [BITS-1:0] o_value;
  logic [BITS-1:0] expected = 0;
  int              errors = 0;
  int              fd;

  counter #(.BITS(BITS)) dut (
    .clock     (clock),
    .reset     (reset),
    .i_init    (1'b0),
    .i_inc_dec (1'b1),
    .o_value   (o_value)
  );

  always #5 clock = ~clock;

  initial begin
    repeat (2) @(negedge clock);
    reset = 0;
    repeat (CYCLES) begin
      @(posedge clock);
      #1;
      expected = expected + 1;
      if (o_value !== expected) begin
        $error("got %0d, expected %0d", o_value, expected);
        errors++;
      end
    end

    // Read by Odatix: the cycles simulated, and what the testbench measured
    $display("odatix_cycles: %0d", CYCLES);
    fd = $fopen("results.yml", "w");
    $fdisplay(fd, "bits: %0d", BITS);
    $fdisplay(fd, "errors: %0d", errors);
    $fclose(fd);
    $finish;
  end
endmodule
{{< /code >}}

The last lines are optional. `odatix_cycles: <n>` tells Odatix how many cycles
were simulated, from which it computes the simulation speed. `results.yml` is
for [step 4](#step-4--report-your-own-figures).

## Step 2 — Attach it to the architecture

The testbench belongs to the design: add it to the architecture's settings.

{{< code lang=yaml filename="architectures/MyCounter/_settings.yml" >}}
testbench:
  top: tb_counter
  files: [tb/tb_counter.sv]
  parameters:
    BITS: ${width}
{{< /code >}}

| Key | |
|-----|---|
| `top` | The module or entity at the top of the testbench. Optional: Odatix guesses it from the files. |
| `files` | Its sources, relative to the workspace, like `rtl_path`. Glob patterns are accepted. |
| `parameters` | What its top is given. `${width}` is the value of the variable `width` the configuration was built from: `8` for `8bits`. A [parameter domain](/docs/configurations/param_domains/) works the same way, under its name. |

## Step 3 — Run it

Name a template and the configurations to run:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -s icarus -a "MyCounter/*"
{{< /code >}}

Or, to run it every time, in `sim_settings.yml`:

{{< code lang=yaml filename="sim_settings.yml" >}}
simulations:
  - icarus:
    - MyCounter/*
{{< /code >}}

Odatix checks the run first: a design or a testbench written in a language the
simulator does not compile (VHDL with `icarus`) is listed with the invalid
jobs, before anything starts. Then each configuration runs in its own work
directory, `work/simulations/icarus/MyCounter/<configuration>/`, where you find:

| File | |
|------|---|
| `odatix_sim.yml` | What Odatix told the simulation: the sources in compilation order, the testbench, the values of the configuration. |
| `log/` | What each command printed. |
| `sim_report.yml` | The outcome: `passed` or `failed`, errors and warnings, compile, elaboration and simulation times, cycles per second. |

The figures of `sim_report.yml` are exported to
`results/results_simulation.yml` as each job ends, and appear in the
[Explorer](/docs/features/explorer/).

Switching simulators is a matter of changing the name: `-s verilator`,
`-s questa` or `-s xsim` run the same testbench, unchanged.

## Step 4 — Report your own figures

The template reports how the simulation went. What the testbench measured
(`results.yml` above) needs a simulation of its own, which starts from the
template and adds a [metrics file](/docs/reference/metrics/):

{{< code lang=text filename="A simulation starting from a template" >}}
odatix_userconfig/simulations/TB_MyCounter/
├── _settings.yml
└── _metrics.yml
{{< /code >}}

{{< code lang=yaml filename="simulations/TB_MyCounter/_settings.yml" >}}
template: icarus
{{< /code >}}

{{< code lang=yaml filename="simulations/TB_MyCounter/_metrics.yml" >}}
metrics:
  bits:
    type: yaml
    settings:
      file: results.yml
      key: bits
    format: "%.0f"
  mismatches:
    type: yaml
    settings:
      file: results.yml
      key: errors
    format: "%.0f"
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix sim -s TB_MyCounter -a "MyCounter/*"
{{< /code >}}

Each result now holds the metrics of the template and those of
`_metrics.yml`. The testbench still comes from the architecture: a simulation
only runs a testbench of its own when it names its files (`testbench: files`
in its `_settings.yml`).

## Going further

- **No testbench yet.** Run a template on a design that has none: Odatix
  generates a minimal testbench, which drives the inputs with random values
  and fails on an unknown output. It checks that every configuration compiles
  and runs, and dumps a VCD. See [Generated testbench](/docs/reference/simulation/#generated-testbench).
- **Compilation order.** Odatix orders the sources itself, VHDL packages and
  SystemVerilog packages first. A `filelist.f` at the root of the RTL directory
  gives the order instead. See [Compilation order](/docs/reference/simulation/#compilation-order).
- **Your own scripts.** A simulation can run any command instead of a template:
  a Makefile, a `.do` script, a cocotb test. The placeholders `${vhdl_files}`,
  `${tb_top}` and the others give it what the templates get. See
  [What the simulation runs](/docs/reference/simulation/#what-the-simulation-runs).
- **A simulator of your own.** Copy one of the templates into a simulation of
  your workspace and change its `run.py`. See
  [Writing a template](/docs/reference/simulation/#writing-a-template).

## See also

- [Simulation settings](/docs/reference/simulation/) — every key of a simulation, and the templates.
- [Architecture settings](/docs/reference/architecture/#testbench) — the `testbench` of a design.
- [Cordic](/docs/examples/architectures/cordic/) — one testbench per language, run by five simulators.
