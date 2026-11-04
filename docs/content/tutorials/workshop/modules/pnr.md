---
title: "Place and route after synthesis"
date: 2026-10-31
author: "Jonathan Saussereau"
weight: 5
description: "Module E: take the netlists an ASIC synthesis wrote, place and route them with a second tool, and see how far the synthesis estimate was from the implemented design."
categories: ["Tutorial", "PNR"]
tags: ["workshop", "pnr", "innovus", "design compiler", "genus", "asic"]
featured_image: "/images/features/pnr.svg"
next_tutorials: ["/tutorials/workshop/modules/design_space", "/tutorials/workshop/finale/dse"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| Design Compiler or Genus, **and** Innovus | 30–40 min | Three configurations placed and routed, next to what their synthesis estimated |

A synthesis estimates: its area counts no wire, its timing guesses the
interconnect. Only place and route says what a design really achieves. In a
commercial ASIC flow, that is two tools — one synthesizes, the other implements
— and `odatix pnr` is the job that chains them: it starts from a synthesis that
already ran, never from the RTL.

> [!IMPORTANT]
> This module needs an ASIC synthesis tool and Innovus, each with its license,
> and the AMS C35 1.8 V library, whose setup scripts Odatix ships. Without them,
> [ASIC with open-source tools](/tutorials/workshop/modules/asic/) goes down to a layout
> with no license at all.

> [!NOTE]
> Every command runs on **your** architecture, the one you described in the
> common track. They are written for `My_Cordic_sv`; in VHDL, write
> `My_Cordic_vhdl` instead — nothing else changes.

## Step 1 — Enable the same target on both tools

A place and route job keeps the target of its synthesis: both target files must
enable `AMS_c35_1V8`, and only it.

{{< code lang=yaml filename="odatix_userconfig/targets/target_innovus.yml" >}}
targets:
  - AMS_c35_1V8

target_settings:
  AMS_c35_1V8:
    script_copy_enable: Yes
    script_copy_source: $eda_tools_path/innovus/technology/AMS_c35_1V8/technology_setup.tcl
{{< /code >}}

`technology_setup.tcl` is where LEF, MMMC and power nets of the library are
declared — the part of a place and route flow that belongs to the foundry, not
to Odatix. The one shipped for AMS C35 is enough for the workshop. In
`target_design_compiler.yml` or `target_genus.yml`, keep `AMS_c35_1V8` enabled
as well, and comment out every other target.

## Step 2 — Synthesize the netlists

Place and route reads three **handoff files** from each synthesis job:
`result/netlist.v`, `result/design.sdc` and `result/design.sdf`. Three
configurations at 100 MHz are enough for the module:

{{< tabs >}}

{{% tab name="Design Compiler" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t design_compiler -a "My_Cordic_sv + ITERATIONS/12 + WIDTH/*" --at 100 --until netlist -y
{{< /code >}}

A Design Compiler synthesis stops once area, timing and power are known; the
netlist is exported by its last step, `netlist`, hence `--until netlist`. A
synthesis already run by the common track resumes from where it stopped, and
only writes the netlist.
{{% /tab %}}

{{% tab name="Genus" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t genus -a "My_Cordic_sv + ITERATIONS/12 + WIDTH/*" --at 100 -y
{{< /code >}}

The Genus flow always writes the netlist: nothing to add.
{{% /tab %}}

{{< /tabs >}}

> [!IMPORTANT]
> A synthesis whose handoff files are missing cannot be a source, whatever its
> status says.

## Step 3 — Start the place and route

In `odatix-gui`: **Run jobs** → **Run place & route**. The page lists the tools
that can place and route — Innovus — then the synthesis jobs actually present
in the work directory: tick the three of step 2. There is no selector to write;
you pick from what exists.

From the terminal, the same thing:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix pnr -t innovus --from-tool design_compiler -j 3 -y
{{< /code >}}

(`--from-tool genus` with Genus.) The run is a series of resumable steps —
`init`, `place`, `cts`, `route`, `signoff` — each its own process. Watch them
go by in the Job Monitor; while they run, read on.

{{< details title="Which synthesis jobs a run takes" >}}
Without the GUI, the sources are the selectors of
`odatix_userconfig/pnr_settings.yml`:

{{< code lang=yaml filename="odatix_userconfig/pnr_settings.yml" >}}
sources:
  - custom_freq_synthesis/design_compiler/AMS_c35_1V8/My_Cordic_sv/*@100MHz
{{< /code >}}

`*` works at every level, and `--from-type`, `--from-tool` and `--from-flow`
narrow the selection from the command line. A selection that matches no
completed synthesis stops the run and lists the sources there are.
{{< /details >}}

> [!TIP]
> `odatix pnr -t innovus --until init` stops after the floorplan: the quickest
> check that the technology setup is right, before spending minutes on routing.
> Run it again without `--until`, and it continues from there.

## Step 4 — Compare the estimate with the implementation

Each tool exports into its own file: `results/results_design_compiler.yml` (or
`results_genus.yml`) for the synthesis, `results/results_innovus.yml` for the
place and route, whose records name the synthesis they come from
(`source_type`, `source_tool`). Both name their metrics alike — `Cell_Area`,
`Total_Power`, `Worst_Slack` — so the same column holds both.

In **Explorer**:

1. **Columns**
2. **Data**: tick your synthesis tool and `innovus`
3. **Axes** → Y metric: `Cell_Area`
4. **Style** → **Color by**: `tool`

The two bars of each configuration are the estimate and the result. Switch the
Y metric to `Worst_Slack`: the gap is now the interconnect the synthesis did not
see — and it grows with the width, because so does the wiring.

> [!NOTE]
> If you did [Accuracy against cost](/tutorials/workshop/modules/accuracy/), the Innovus
> records already carry `snr`: derived metrics are recomputed at the end of
> every run. The accuracy-against-area chart now exists in post-route area too.

## If something did not work

| Symptom | What to do |
|---|---|
| No sources found | Step 2 did not write the handoff files: with Design Compiler, rerun it with `--until netlist`. |
| `init` stops on "no technology_setup.tcl" | `target_innovus.yml` brings in no technology script for this target: see step 1. |
| Innovus is not offered | It does not answer in this terminal: check `innovus -version`, and the **Tools** page. |
| A license error, in the job log | Nothing Odatix can fix: take [ASIC with open-source tools](/tutorials/workshop/modules/asic/) instead. |
| Too slow for the slot | One configuration (`WIDTH/8`), and `--until place`. |

## Next

- [Shape your own design space](/tutorials/workshop/modules/design_space/) — the last
  module, and one that needs no tool at all.
- [Let the search do the work](/tutorials/workshop/finale/dse/) — the finale.
- [Place & route a synthesized design](/tutorials/run_examples/pnr/) — the full
  tutorial, including adapting the flow to your own PDK.
