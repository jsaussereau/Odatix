---
draft: true
title: "Check the RTL in ten seconds"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 2
description: "The terminal variant of the common track, part 2: odatix analyze elaborates the nine configurations with Verilator or GHDL, and catches a wrong delimiter before it costs a synthesis."
categories: ["Tutorial", "Design"]
tags: ["workshop", "terminal", "analysis", "cordic"]
featured_image: "/images/features/analysis.svg"
next_tutorials: ["/tutorials/workshop/terminal/synthesis"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Verilator **or** GHDL | 5 min | Nine configurations checked |

The architecture of [the previous page](/tutorials/workshop/terminal/describe/) has nine
configurations, and none has been run yet.

## Step 1 — Run the analysis

Before running anything long, have a tool elaborate every configuration and say
whether it holds up. That is `odatix analyze`, and on a free simulator it costs
seconds — the cheapest way to catch a wrong delimiter before it costs a
synthesis.

`-a` selects what to run: the architecture, then each domain, `*` standing for
every value. `-y` skips the confirmation and `-E` closes the monitor when the
jobs are done.

{{< tabs >}}

{{% tab name="SystemVerilog" %}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix analyze --tool verilator -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y -E
<font color="#555753">[odatix analyze]</font> <font color="#34E2E2">note: 9/9 analysis jobs over: the report below says what they found</font>

<font color="#34E2E2">========================================================================</font>
<font color="#34E2E2"><b> RTL ANALYSIS</b></font>  1 design, 1 tool: verilator
<font color="#34E2E2">========================================================================</font>

 <font color="#8AE234">✓</font> 9 passed

<font color="#555753"> Every finding of every design: odatix-explorer, RTL analysis page.</font>
{{< /code >}}

{{% /tab %}}

{{% tab name="VHDL" %}}

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix analyze --tool ghdl -a "My_Cordic_vhdl + ITERATIONS/* + WIDTH/*" -y -E
<font color="#555753">[odatix analyze]</font> <font color="#34E2E2">note: 9/9 analysis jobs over: the report below says what they found</font>

<font color="#34E2E2">========================================================================</font>
<font color="#34E2E2"><b> RTL ANALYSIS</b></font>  1 design, 1 tool: ghdl
<font color="#34E2E2">========================================================================</font>

 <font color="#8AE234">✓</font> 9 passed

<font color="#555753"> Every finding of every design: odatix-explorer, RTL analysis page.</font>
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

## Step 2 — Read what it found

Nine passed: the delimiters are right, and every configuration elaborates.
Here is what the same command says when they are not — `stop_delimiter: ','`
for `ITERATIONS`, so that the replacement eats the `)` closing the parameter
list:

{{< code lang=bash filename="Terminal (with a wrong delimiter)" fold="true" ansi="true" >}}
<font color="#34E2E2">========================================================================</font>
<font color="#34E2E2"><b> RTL ANALYSIS</b></font>  1 design, 1 tool: verilator
<font color="#34E2E2">========================================================================</font>

 <font color="#EF2929">✗</font> 1 failed

 Findings         verilator
 Syntax error         1

 <font color="#EF2929">✗</font> Failed (1)
   My_Cordic_sv  syntax error, unexpected input, expecting IDENTIFIER or IDENTIF…  rtl/cordic.sv:29
{{< /code >}}

A syntax error at a line of the RTL you never touched: the sign of a
delimiter. Fix the `_settings.yml` of the domain ([step 3 of the previous page](/tutorials/workshop/terminal/describe/#step-3--describe-what-changes)) and run the analysis again —
nothing else needs to be redone.

{{< details title="Check it with every tool of the session at once" >}}
Simulators and synthesizers do not accept the same subset of the language: a
construct one of them takes without a word, another rejects or reads
differently. Name every tool the design will meet, and the same check runs on
each of them, one line per tool in the report:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze --tool verilator icarus yosys -a "My_Cordic_sv + ITERATIONS/* + WIDTH/*" -y -E
$ odatix analyze --tool ghdl -a "My_Cordic_vhdl + ITERATIONS/* + WIDTH/*" -y -E
{{< /code >}}

All of them come with the OSS CAD Suite. Add your own synthesis tool if you
have one (`vivado`, `quartus`, `design_compiler`, `genus`), and keep only the
tools installed on your machine — a tool that cannot start is
reported as such, not as a fault of the design. Every finding, per
configuration, is on the **RTL analysis** page of Odatix Explorer
(`odatix-explorer analysis`).
{{< /details >}}

> [!TIP]
> This is the command to reach for whenever something later fails on *every*
> configuration: it tells a broken design from a broken tool setup in seconds.

## If something did not work

| Symptom | What to do |
|---|---|
| Every analysis fails on a syntax error | A delimiter. The value of `ITERATIONS` ends with the line: `stop_delimiter: '\n'`. Compare with the answer: `ITERATIONS/_settings.yml` of `My_Cordic_sv_solution` (see [Create a workspace](/tutorials/workshop/common/workspace/#step-3--choose-your-language)). |
| The analysis says the tool is not found | `verilator --version` or `ghdl --version` must answer in the terminal Odatix was started from. |
