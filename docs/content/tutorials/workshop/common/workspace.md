---
title: "Create a workspace"
date: 2026-10-26
author: "Jonathan Saussereau"
weight: 1
description: "The first step of the common track: create the workshop workspace, find the CORDIC sources in it, and choose the language you will work in — SystemVerilog or VHDL."
categories: ["Tutorial", "Workspace"]
tags: ["workshop", "workspace", "init", "cordic"]
featured_image: "/images/tutorials/workspace.svg"
next_tutorials: ["/tutorials/workshop/common/describe"]
---

| Tools needed | Time | What you leave with |
|---|---|---|
| Odatix | 5 min | A workspace holding the CORDIC sources, and a language chosen |

## Step 1 — Create the workspace

Create a new directory for the session and move into it. For example:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p ~/odatix_workshop && cd ~/odatix_workshop
{{< /code >}}

Create a new Odatix workspace, with the material of the workshop:

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix init --cordic

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝

<font color="#555753">[odatix init]</font> <font color="#34E2E2">note: This command will create all the configuration files needed by Odatix in the current directory.</font>
<font color="#555753">[odatix init]</font> Would you like to continue? (Y/n) y
<font color="#555753">[odatix init]</font> <font color="#8AE234">Your directory can now be used by Odatix!</font>
<font color="#555753">[odatix init]</font> The sources of the CORDIC are in examples/cordic_sv, examples/cordic_vhdl and examples/cordic_tb: describe it as My_Cordic_sv or My_Cordic_vhdl
<font color="#555753">[odatix init]</font> New to Odatix? Follow <font color="#729FCF">https://odatix.readthedocs.io/en/latest/docs/getting-started/</font>
{{< /code >}}

`--cordic` copies the sources of the design and what the modules run besides
it — two workflows and their exploration campaigns — but **no description of
the design**: that part is yours to write.

**Stay in this directory for the whole session.** Every command of every page
is run from there.

## Step 2 — Find the design

The design of the workshop is a **pipelined CORDIC rotation core**, written
twice — once in SystemVerilog, once in VHDL, with the same ports, the same
parameters and the same results bit for bit. Its sources, and a testbench in
each language, are in `examples/`:

{{< code lang=text filename="Workspace" >}}
examples/
├── cordic_sv/
│   └── cordic.sv          # the core, SystemVerilog
├── cordic_vhdl/
│   └── cordic.vhdl        # the core, VHDL
└── cordic_tb/
    ├── tb_cordic.sv       # its testbench, SystemVerilog
    └── tb_cordic.vhdl     # its testbench, VHDL
{{< /code >}}

That is all you start from: RTL, with no Odatix file of any kind next to it.
`odatix ls` confirms it — no architecture, no simulation yet, only the
workflows of the optional pages:

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix ls
<b>Architectures (0)</b>
  none

<b>Simulations (0)</b>
  none

<b>Workflows (3)</b>
  cordic_model  cordic_model_wide  image_codec
{{< /code >}}
The next two pages have you describe it to Odatix yourself.


## Step 3 — Choose your language

Everything in the common track is written twice, in a tab per language. Pick **one**:

> [!IMPORTANT]
> We highly recommend you to use the SystemVerilog version of the design. It works with the free tools Verilator and Yosys_FPGA, and you can run the whole workshop without any commercial tool.

| | SystemVerilog | VHDL |
|---|---|---|
| Sources | `examples/cordic_sv/cordic.sv` | `examples/cordic_vhdl/cordic.vhdl` |
| Your architecture | `My_Cordic_sv` | `My_Cordic_vhdl` |
| Free analysis and simulation | Verilator | GHDL |
| Synthesis | **Yosys + nextpnr**, LibreLane, Vivado, Quartus, Design Compiler, Genus | **Yosys + nextpnr**, Vivado, Quartus, Design Compiler, Genus |

The OSS CAD Suite holds both simulators and the synthesis and pnr tool for Yosys_FPGA (see [Before you
start](/tutorials/workshop/#2-install-oss-cad-suite)).

## Optionally, get the answer

{{< details title="The answer, in a directory of its own" >}}
The complete description exists, and you can have it next to your workspace —
not in it, so that it never gets in the way of yours:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p ~/odatix_workshop_answer && cd ~/odatix_workshop_answer
$ odatix init -y --cordic-solution
$ cd ~/odatix_workshop
{{< /code >}}

It holds `My_Cordic_sv_solution` and `My_Cordic_vhdl_solution`, with their
simulations `TB_My_Cordic_sv_solution` and `TB_My_Cordic_vhdl_solution`: try
first, and open them when you are stuck, or to compare once you are done. The
whole workshop runs on the description **you** write, never on these.
{{< /details >}}
