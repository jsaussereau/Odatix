---
title: "Adder tree (SystemVerilog package)"
description: "A pipelined adder tree whose parameters live in a SystemVerilog package of another file, swept over its width and over a parameter that changes its structure."
weight: 8
---

# Adder tree (SystemVerilog package)

The adder tree example sums `N_INPUTS` operands two by two. Its parameters are
not declared by the module but by a **SystemVerilog package**, in another file,
as in many real designs: the parameter domains replace values in that file,
never in the top level.

One of the parameters, `REGISTER_LEVELS`, does not change a width but the
**structure** of the design: a register after every level of the tree, or
none. The sweep shows what a pipeline costs and what it buys.

{{< details title="What this example demonstrates" >}}
- **Parameters in another file than the top level** — each [parameter domain](/docs/configurations/param_domains/) names the package with `param_target_file`.
- **A structural parameter** — a domain whose two values give two different circuits, with opposite trade-offs.
- **A design described with the [Python API](/docs/python_api/workspace/)** — its settings are what the detection of the sources gives, the way an [AI agent](/docs/ai_agents/) describes a design.
{{< /details >}}

{{< toc >}}

## What the design does

The operands are registered, added two by two over `log2(N_INPUTS)` levels,
and the sum is registered. The ports and constants name the package
explicitly (`tree_config_pkg::N_INPUTS`) rather than importing it, which every
synthesis tool accepts, Yosys included.

{{< details title="Interface" >}}
| Port | Direction | Width | Role |
|---|---|---|---|
| `clock` | in | 1 | Clock, rising edge |
| `reset` | in | 1 | Synchronous reset, active high |
| `i_operands` | in | `N_INPUTS * IN_WIDTH` | The operands, side by side |
| `o_sum` | out | `IN_WIDTH + log2(N_INPUTS)` | Their sum |
{{< /details >}}

### Parameters

| Parameter | Default | Effect |
|---|---|---|
| `N_INPUTS` | 8 | Number of operands, a power of two. Sets the number of adders (`N_INPUTS - 1`) and of levels. |
| `IN_WIDTH` | 8 | Width of each operand. |
| `REGISTER_LEVELS` | 1 | `1`: a register after every level (latency `log2(N_INPUTS) + 2` cycles, the critical path is one adder). `0`: none between the input and output registers (latency 2 cycles, the critical path crosses every level). |

`LEVELS` and `OUT_WIDTH` are computed from the others (`localparam`): they are
not swept.

## Files

{{< code lang=text filename="workspace" >}}
examples/adder_tree_sv/
├── tree_config_pkg.sv          # the parameters
└── adder_tree.sv               # the top level

odatix_userconfig/architectures/Example_Adder_Tree_sv/
├── _settings.yml               # sources, clock, reset, frequencies
├── N_INPUTS/_settings.yml      # 'N_INPUTS' parameter domain
└── REGISTER_LEVELS/_settings.yml
{{< /code >}}

## Architecture settings

{{< code lang=yaml filename="architectures/Example_Adder_Tree_sv/_settings.yml" >}}
rtl_path: examples/adder_tree_sv
top_level_file: adder_tree.sv
top_level_module: adder_tree

clock_signal: clock
reset_signal: reset

# The domains have their own delimiters
use_parameters: No
start_delimiter: ''
stop_delimiter: ''

fmax_synthesis:
  lower_bound: 50
  upper_bound: 800
fixed_freq_synthesis:
  list: [50, 100, 200]
{{< /code >}}

### Parameter domains in the package

{{< code lang=systemverilog filename="examples/adder_tree_sv/tree_config_pkg.sv" >}}
package tree_config_pkg;
  parameter int N_INPUTS = 8;          // number of operands, a power of two
  parameter int IN_WIDTH = 8;          // width of each operand
  parameter bit REGISTER_LEVELS = 1;   // register the output of every level of the tree
  localparam int LEVELS    = $clog2(N_INPUTS);
  localparam int OUT_WIDTH = IN_WIDTH + LEVELS;
endpackage
{{< /code >}}

{{< code lang=yaml filename="architectures/Example_Adder_Tree_sv/N_INPUTS/_settings.yml" >}}
use_parameters: Yes
param_target_file: tree_config_pkg.sv
start_delimiter: 'N_INPUTS = '
stop_delimiter: ;

variables:
  N_INPUTS:
    type: list
    settings:
      list: [4, 8, 16]
{{< /code >}}

`param_target_file` is relative to `rtl_path`. The `REGISTER_LEVELS` domain is
the same, with the values `[0, 1]`.

### Described from Python

These settings are what the detection of the sources gives. They were written
by this script:

{{< code lang=python filename="add_adder_tree.py" >}}
from odatix.workspace import Workspace, FrequencyBounds

ws = Workspace.open()
arch = ws.architectures.create("Example_Adder_Tree_sv")
arch.settings.rtl_path = "examples/adder_tree_sv"
arch.fill_from_sources()     # top level, clock and reset
arch.settings.fmax_synthesis = FrequencyBounds(lower_bound=50, upper_bound=800)
arch.save()

# The parameters of the package, not of the top level
for p in arch.detect_parameters(file="tree_config_pkg.sv"):
    print(p.name, p.value, p.relevance)   # N_INPUTS, IN_WIDTH, REGISTER_LEVELS first
arch.domains.create_from_parameter("N_INPUTS", [4, 8, 16], file="tree_config_pkg.sv")
arch.domains.create_from_parameter("REGISTER_LEVELS", [0, 1], file="tree_config_pkg.sv")
{{< /code >}}

## Running the sweep

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze -t verilator -a "Example_Adder_Tree_sv + N_INPUTS/* + REGISTER_LEVELS/*"
$ odatix fmax -t yosys_fpga -a "Example_Adder_Tree_sv + N_INPUTS/* + REGISTER_LEVELS/*"
{{< /code >}}

The 6 configurations, on a Lattice ECP5 (`yosys_fpga`):

| `N_INPUTS` | `REGISTER_LEVELS` | Fmax (MHz) | LUTs | Registers |
|---|---|---|---|---|
| 4 | 1 | 346 | 44 | 70 |
| 4 | 0 | 204 | 71 | 42 |
| 8 | 1 | 328 | 102 | 142 |
| 8 | 0 | 135 | 187 | 75 |
| 16 | 1 | 310 | 218 | 286 |
| 16 | 0 | 98 | 366 | 140 |

Pipelined, the tree keeps its Fmax as it grows, for twice the registers.
Without registers between the levels, the Fmax falls with every level added,
and the adders, chained, take more LUTs.

> [!NOTE]
> 16 operands of 8 bits take 142 I/Os, within the 197 of the ECP5-25k. A part
> with fewer pins cannot place the widest configurations.

## Where to go next

- [Cordic](/docs/examples/architectures/cordic/) — two parameter domains in the parameter list of the module, and simulations.
- [Use Odatix with AI agents](/docs/ai_agents/) — how an agent describes a design like this one.
- [All architecture examples](/docs/examples/architectures/) — the designs and what each one adds.
