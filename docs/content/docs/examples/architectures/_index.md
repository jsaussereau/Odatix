---
title: "Architectures"
description: "Six example designs shipped with Odatix — from a four-language counter to a pipelined CORDIC — each isolating one mechanism of architecture exploration."
weight: 1
---

# Architecture Examples

An [architecture](/docs/features/architecture-exploration/) is a design plus the recipe that turns it into a family of configurations: where its sources live, which top level to implement, and which parameters to sweep. The six examples below are all shipped in a fresh workspace, and all of them run out of the box once an EDA tool is installed.

They are ordered by what they add, not by size. Read the [counter](/docs/examples/architectures/counter/) first if you want the shortest complete example; read the [Cordic](/docs/examples/architectures/cordic/) if you want to see everything at once.

{{< details title="What these examples demonstrate, together" >}}
- **Delimiter-based substitution with no markers in the RTL** — the existing parameter declaration is the delimiter, so sources stay synthesizable outside Odatix.
- **Four RTL languages plus Chisel** — Verilog, SystemVerilog, VHDL and Scala, with only the delimiters changing.
- **[Parameter domains](/docs/configurations/param_domains/)** — several parameters swept independently and combined automatically.
- **[Generated configurations](/docs/configurations/variables/)** — sweeps described by a variable and a template instead of a directory of files.
- **Multi-file designs and synthesis wrappers** — packages, submodules, and a top level whose only job is to register the boundary.
- **[Simulation](/docs/features/simulation/) with several tools** — each testbench reporting its own metrics.
{{< /details >}}

{{< toc >}}

## The examples

{{< doc-cards cols="2" >}}
{{< doc-card title="Cordic (VHDL & SystemVerilog)" link="/docs/examples/architectures/cordic/" icon="waves" accent="#2563eb" cta="Read the example" >}}
A pipelined CORDIC rotation core, described twice, swept over two parameter domains and simulated by four simulators that each report their own accuracy metrics.
{{< /doc-card >}}

{{< doc-card title="Counter (4 languages)" link="/docs/examples/architectures/counter/" icon="code" accent="#0ea5e9" cta="Read the example" >}}
The same up/down counter written in Verilog, SystemVerilog, VHDL and Chisel, to show that only the delimiters change — plus a variant parameterized on the command line.
{{< /doc-card >}}

{{< doc-card title="ALU (SystemVerilog & Chisel)" link="/docs/examples/architectures/alu/" icon="chip" accent="#7c3aed" cta="Read the example" >}}
A multi-file design with a package, a submodule and a synthesis wrapper — and delimiters that are not unique in the file.
{{< /doc-card >}}

{{< doc-card title="Multiplier & Shift Register" link="/docs/examples/architectures/mult_shift_register/" icon="gauge" accent="#0d9488" cta="Read the example" >}}
Two minimal designs swept over the same widths, one cheap and one expensive, chosen to make the shape of a trade-off curve visible.
{{< /doc-card >}}

{{< doc-card title="Sine ROM (Chisel)" link="/docs/examples/architectures/rom/" icon="blocks" accent="#f59e0b" cta="Read the example" >}}
A generated sine lookup table swept over address width and data width — two parameter domains whose configurations are themselves generated.
{{< /doc-card >}}

{{< doc-card title="Configuration generation" link="/docs/examples/architectures/config_generation/" icon="generate" accent="#db2777" cta="Read the example" >}}
A catalogue architecture that cannot be synthesized: ten settings files, one per way of generating a list of configurations.
{{< /doc-card >}}
{{< /doc-cards >}}

## At a glance

| Example | Languages | Parameters | Adds |
|---|---|---|---|
| [Cordic](/docs/examples/architectures/cordic/) | VHDL, SystemVerilog | 2 domains | simulation with four tools, testbench metrics |
| [Counter](/docs/examples/architectures/counter/) | Verilog, SystemVerilog, VHDL, Chisel | 1 domain | the same sweep in four languages |
| [ALU](/docs/examples/architectures/alu/) | SystemVerilog, Chisel | 1 domain | multiple source files, synthesis wrapper, ambiguous delimiters |
| [Multiplier & Shift Register](/docs/examples/architectures/mult_shift_register/) | SystemVerilog | 1 domain | two designs sharing one set of configuration files |
| [Sine ROM](/docs/examples/architectures/rom/) | Chisel | 2 domains | generated configurations, formatted names |
| [Configuration generation](/docs/examples/architectures/config_generation/) | — | 10 settings files | every variable type, side by side |

## Running them

{{< doc-card title="Tutorials" link="/tutorials/run_examples/" icon="tutorial" accent="#0d9488" cta="Browse the tutorials" >}}
Step-by-step instructions to run the examples, and understand how Odatix works.
{{< /doc-card >}}
