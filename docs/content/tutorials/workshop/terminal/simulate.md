---
draft: true
title: "Simulate it while it synthesizes"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 4
description: "The terminal variant of the common track, part 4: attach the testbench to the architecture, describe a simulation from a template, turn its measurements into metrics, and run it with odatix sim."
categories: ["Tutorial", "Design"]
tags: ["workshop", "terminal", "simulation", "cordic"]
featured_image: "/images/features/simulation.svg"
next_tutorials: ["/tutorials/workshop/common/explore"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Verilator **or** GHDL | 20 min | Nine simulated configurations |

[Simulate it while it synthesizes](/tutorials/workshop/common/simulate/) writes the simulation in
the interface. Here it is in files: read its [step 1](/tutorials/workshop/common/simulate/#step-1--look-at-what-the-testbench-measures)
first, which shows what the testbench measures, then take these steps in place
of its steps 2 to 5.

## Step 1 — Attach the testbench to the architecture

The testbench belongs to the design, not to a simulator: it is declared in the
architecture, with the value each of its parameters gets from the
configuration. Add this block at the end of your `_settings.yml`:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_sv/_settings.yml (added)" >}}
# The testbench, and what each configuration gives it
testbench:
  top: tb_cordic
  files: [examples/cordic_tb/tb_cordic.sv]
  parameters:
    WIDTH: ${WIDTH}
    ITERATIONS: ${ITERATIONS}
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=yaml filename="odatix_userconfig/architectures/My_Cordic_vhdl/_settings.yml (added)" >}}
# The testbench, and what each configuration gives it
testbench:
  top: tb_cordic
  files: [examples/cordic_tb/tb_cordic.vhdl]
  parameters:
    WIDTH: ${WIDTH}
    ITERATIONS: ${ITERATIONS}
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

`${WIDTH}` is the value of the variable `WIDTH` the configuration was made from
— the variable of your parameter domain, not the parameter of the RTL. For the
configuration `ITERATIONS/12 + WIDTH/8`, the testbench gets `WIDTH = 8` and
`ITERATIONS = 12`.

> [!NOTE]
> Editing the architecture while it synthesizes is safe: each job works on its
> own copy, made when it started.

## Step 2 — Describe the simulation

A simulation is a directory of `odatix_userconfig/simulations/`. Its
`_settings.yml` names the simulator that runs it — a **template**, so there is
no script to write:

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/simulations/TB_My_Cordic_sv
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/simulations/TB_My_Cordic_sv/_settings.yml" >}}
template: verilator
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/simulations/TB_My_Cordic_vhdl
{{< /code >}}

{{< code lang=yaml filename="odatix_userconfig/simulations/TB_My_Cordic_vhdl/_settings.yml" >}}
template: ghdl
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

The template compiles the design and the testbench of the architecture, in its
own language, and runs it. The other templates are `icarus`, `questa` and
`xsim`: with Questa or xsim, both languages, and even the SystemVerilog
testbench on the VHDL core.

## Step 3 — Turn the measurements into metrics

What the testbench measures becomes a metric through `_metrics.yml`, next to
`_settings.yml`, one entry per key of its `results.yml`. The file is the same
in both languages:

{{< code lang=yaml filename="odatix_userconfig/simulations/TB_My_Cordic_<language>/_metrics.yml" >}}
metrics:
  snr:
    type: yaml
    settings:
      file: results.yml
      key: snr_db
    unit: "dB"
    format: "%.2f"

  enob:
    type: yaml
    settings:
      file: results.yml
      key: enob
    unit: "bits"
    format: "%.2f"
{{< /code >}}

Read an entry as: *the metric `snr` is the key `snr_db` of the YAML file
`results.yml`, in dB*. The name of the metric is yours; the key is the
testbench's.

Add `latency` yourself, from `latency_cycles`, in cycles.

{{< details title="The answer" >}}
{{< code lang=yaml filename="_metrics.yml (added, under metrics:)" >}}
  latency:
    type: yaml
    settings:
      file: results.yml
      key: latency_cycles
    unit: "cycles"
    format: "%.0f"
{{< /code >}}
{{< /details >}}

> [!IMPORTANT]
> Keep the metric names `snr`, `enob` and `latency`: the modules chart and
> optimize them by those names.

## Step 4 — Run the simulation

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix sim -s TB_My_Cordic_sv -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y -E
[...]
<font color="#555753">[odatix sim]</font> 9/9 jobs over: 9 succeeded, 0 failed, 0 running, 0 queued
<font color="#555753">[odatix sim]</font> <font color="#34E2E2">note: 9/9 jobs succeeded</font>
{{< /code >}}

About half a minute, most of it Verilator compiling.

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix sim -s TB_My_Cordic_vhdl -a "My_Cordic_vhdl + ITERATIONS/* + WIDTH/*" -y -E
[...]
<font color="#555753">[odatix sim]</font> 9/9 jobs over: 9 succeeded, 0 failed, 0 running, 0 queued
<font color="#555753">[odatix sim]</font> <font color="#34E2E2">note: 9/9 jobs succeeded</font>
{{< /code >}}

About ten seconds.

{{% /tab %}}

{{< /tabs >}}

The simulations run next to the synthesis, on the same daemon: the monitor
shows the jobs of this command, and `odatix monitor` lists every session of the
workspace, the synthesis included.

Each result is in `results/results_simulation.yml` the moment its job is over:

{{< code lang=yaml filename="results/results_simulation.yml (width 8, iterations 12)" >}}
  metrics:
    sim_status: passed      # from the template: the simulation ran through
    snr: 28.66              # dB
    enob: 4.86              # bits
    latency: 13             # cycles
{{< /code >}}

`sim_status` and the compile and run times come from the template; the rest is
your `_metrics.yml`.

## Next

Read the accuracy and the cost of your nine configurations in [Explore the
results](/tutorials/workshop/common/explore/): everything before it, you have
just done by hand.
