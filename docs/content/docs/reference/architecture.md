---
title: "Architecture Settings"
description: "Every key of architectures/<design>/_settings.yml — sources, top level, parameter replacement, generated RTL, frequency bounds and parameter domains."
weight: 3
---

# `architectures/<design>/_settings.yml`

A **design** is a directory under `arch_path` (default
`odatix_userconfig/architectures/`) holding one `_settings.yml`, one parameter
file per configuration, and optionally one sub-directory per
[parameter domain](/docs/configurations/param_domains/).

{{< code lang=text filename="A design directory" >}}
odatix_userconfig/architectures/Example_ALU_sv/
├── _settings.yml     # this page
├── 08bits.txt        # a configuration
├── 16bits.txt        # another one
└── Mul/              # a parameter domain
    ├── _settings.yml
    ├── Fast.txt
    └── Off.txt
{{< /code >}}

{{< toc >}}

## Sources and top level

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `rtl_path` | path | Yes, unless `generate_rtl` | Source directory copied into every job's work directory. |
| `top_level_file` | path | Yes | Top-level source file, relative to `rtl_path` (or to `generate_output` in a generation flow). |
| `top_level_module` | string | Yes | Name of the top-level module or entity. |
| `clock_signal` | string | Yes | Name of the main clock signal, used to write the timing constraint. |
| `reset_signal` | string | Yes | Name of the main reset signal. |

{{< code lang=yaml filename="architectures/Example_ALU_sv/_settings.yml" >}}
rtl_path: "examples/alu_sv"

top_level_file:   "alu_top.sv"
top_level_module: "alu_top"

clock_signal: "i_clk"
reset_signal: "i_rst"
{{< /code >}}

## Parameter replacement

Odatix produces a configuration by replacing the text **between two delimiters**
with the content of that configuration's parameter file. The delimiters
themselves are kept.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `use_parameters` | bool | Yes | Enable replacement from `<configuration>.txt`. |
| `start_delimiter` | string | If `use_parameters` | Text marking the start of the replaced block. |
| `stop_delimiter` | string | If `use_parameters` | Text marking its end. |
| `param_target_file` | path | Conditionally | File the replacement is applied to. Defaults to the top level; **mandatory** with `generate_rtl`. |

{{< code lang=yaml filename="_settings.yml" >}}
use_parameters:  Yes
start_delimiter: "#("
stop_delimiter:  ")("
{{< /code >}}

The parameter file holds the exact replacement text, nothing else:

{{< code lang=verilog filename="architectures/Example_ALU_sv/16bits.txt" >}}
  parameter BITS = 16
{{< /code >}}

> [!TIP]
> `odatix replace` applies the same replacement outside of any job, so a new
> design's delimiters can be checked in a second instead of at the end of a
> synthesis. See [Generation and replacement](/docs/commands/#generation-and-replacement).

Set `use_parameters: No` for a design with no configuration file — for instance
one swept through [variables](/docs/configurations/virtual_param_domains/) on a
generation command line.

## Generated RTL (Chisel, HLS, generators)

When the RTL does not exist yet and has to be produced from a higher-level
description, replacement targets the **source** and a command generates the RTL
inside the work directory.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `generate_rtl` | bool | No | Enable the generation flow. |
| `design_path` | path | Yes, in a generation flow | Directory copied into the work directory before generation. |
| `generate_command` | string | If `generate_rtl` | Command executed to produce the RTL. Accepts `${...}` placeholders filled from parameter domains and [variables](/docs/configurations/virtual_param_domains/). |
| `generate_output` | path | No | Directory the command writes its RTL to, relative to the work directory. |
| `design_path_whitelist` | list of globs | No | Only these patterns are copied from `design_path`. |
| `design_path_blacklist` | list of globs | No | These patterns are excluded from the copy. |

{{< code lang=yaml filename="architectures/Example_ALU_chisel/_settings.yml" >}}
design_path: "examples/alu_chisel"

generate_rtl:     Yes
generate_command: "sbt 'runMain ALUTop --o=rtl'"
generate_output:  "rtl"

top_level_file:   "ALUTop.sv"      # relative to generate_output
top_level_module: "ALUTop"
clock_signal:     "clock"
reset_signal:     "reset"

use_parameters:    Yes
param_target_file: "src/main/scala/ALUTop.scala"
start_delimiter:   "new ALUTop("
stop_delimiter:    ")"
{{< /code >}}

> [!IMPORTANT]
> With `generate_rtl`, `param_target_file` is **mandatory**: the top level does
> not exist when parameters are replaced, so the replacement must target the
> source that produces it.

## Extra file copy

A hook to drop one additional file into the copied RTL tree — a memory
initialization file, a generated package, a licence.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `file_copy_enable` | bool | No | Enable the copy. |
| `file_copy_source` | path | If enabled | File to copy. |
| `file_copy_dest` | path | If enabled | Destination inside the copied RTL tree. |

## Testbench

The testbench of the design. Any [simulation
template](/docs/reference/simulation/#templates) runs the design with it, so a
run can simulate the design with any simulator without a simulation of its own.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `testbench.top` | string | No | Module or entity at the top of the testbench. Guessed from its files when empty. |
| `testbench.files` | path or list | Yes | Its sources, relative to the workspace (like `rtl_path`). Glob patterns are accepted. |
| `testbench.parameters` | mapping | No | Parameters (generics) given to its top. Values may use the [simulation placeholders](/docs/reference/simulation/#placeholders-available-in-commands). |

{{< code lang=yaml filename="architectures/Example_Cordic_vhdl/_settings.yml" >}}
testbench:
  top: tb_cordic
  files: [examples/cordic_tb/tb_cordic.vhdl]
  parameters:
    WIDTH: ${width}
    ITERATIONS: ${iterations}
{{< /code >}}

`${width}` is the value of the parameter domain `width` of the configuration
under test: the testbench receives the configuration it runs on, without
reading the RTL. The files are copied into the `testbench/` directory of each
simulation job, headers and subdirectories included.

A simulation naming its own testbench files runs its own; otherwise the
architecture's comes first (see [which testbench runs](/docs/reference/simulation/#testbench)).
Files that match nothing, or a testbench in a language the simulator does not
compile, are reported when the run is checked.

## Frequency settings

Two blocks, one per synthesis job type. Both are optional at the root of the
file, but an [fmax search](/docs/features/rtl_fmax_synthesis/) needs bounds from
somewhere.

{{< code lang=yaml filename="_settings.yml" >}}
fmax_synthesis:
  lower_bound: 100          # MHz, start of the binary search
  upper_bound: 900          # MHz, end of it

fixed_freq_synthesis:
  lower_bound: 100
  upper_bound: 500
  step: 50                  # -> 100, 150, 200, ... 500
  list: [125, 333]          # explicit frequency points
  list_append: true         # add "list" to the range instead of replacing it
{{< /code >}}

| Key | Block | Type | Description |
|-----|-------|------|-------------|
| `lower_bound` | both | int (MHz) | Lowest frequency considered. |
| `upper_bound` | both | int (MHz) | Highest frequency considered. |
| `step` | `fixed_freq_synthesis` | int (MHz) | Increment between two frequency points. |
| `list` | `fixed_freq_synthesis` | list of int | Explicit frequency points. |
| `list_append` | `fixed_freq_synthesis` | bool (default `false`) | `true` merges `list` with the range; `false` makes `list` the whole set. |

`--from`, `--to`, `--step` and `--at` override these for one run.

> [!NOTE]
> `fixed_freq_synthesis` used to be called `custom_freq_synthesis`. The former
> name is still read, at the root and in the rules of `overrides`, and
> `odatix migrate` rewrites it.

### Overrides

Everything above applies to every job the design produces. What applies to only
some of them goes in the `overrides` section: an **ordered list of rules**, each
saying which jobs it applies to and what those jobs should use instead.

A rule selects jobs on three axes, and an axis it does not name it does not
restrict:

| Selector | Selects on | Example |
|----------|------------|---------|
| `tools` | The EDA tool running the job, optionally one of its flows | `vivado`, `genus@power_opt`, `[vivado, genus]` |
| `targets` | The synthesis target | `xc7a100t-csg324-1`, `xc7a*` |
| `configurations` | The configuration | `32bits`, `*bits` |

Each takes one name, a list of names, or shell-style patterns. A tool named
alone covers all of its flows; `tool@flow` covers that flow only, and
`*@power_opt` that flow of whichever tool declares it.

The rest of a rule is settings — any key of this file, not just the ones below.

{{< code lang=yaml filename="_settings.yml" >}}
fmax_synthesis:                       # applies to every job
  lower_bound: 50
  upper_bound: 500

overrides:
  - targets: xc7a100t-csg324-1        # ... except on this target
    fmax_synthesis:
      lower_bound: 250
      upper_bound: 900
    fixed_freq_synthesis:
      list: [50, 100, 200]

  - targets: xc7a100t-csg324-1        # ... and on this configuration of it
    configurations: 32bits
    fmax_synthesis:
      lower_bound: 280
      upper_bound: 950

  - tools: vivado@power_opt           # ... and whatever the target, in this flow
    constraints:
      - odatix_userconfig/constraints/floorplan.tcl @ pnr
{{< /code >}}

Rules apply **in order**, on top of the top level of the file: the last rule
matching a job has the last word on the keys it names, and says nothing about
the keys it does not. Two exceptions, which are what the keys mean rather than a
special case of the ordering:

- `constraints` **add up**: every matching rule's files are read, after the ones
  declared at the top level, not instead of them.
- a frequency `list` can ask to be added to the one of the level above it, with
  `list_append`, instead of replacing it.

Bounds that are too wide cost synthesis runs; bounds that are too narrow make a
search stop at an edge. Setting them per target is what keeps a large campaign
fast.

> [!NOTE]
> The legacy root keys `fmax_lower_bound` and `fmax_upper_bound` are still read,
> but deprecated in favour of the `fmax_synthesis` block. `odatix migrate`
> rewrites them that way (see [Commands](/docs/commands/#migration)).

## Configuration generation

Instead of writing the parameter files by hand, a design (or a domain) can
generate them from a rule.

| Key | Type | Description |
|-----|------|-------------|
| `configurations` | mapping | How the configurations are built: `name` and `template`. |
| `variables` | mapping | The value sets the rule is applied to. A root key, since variables are not specific to generation. |

{{< code lang=yaml filename="_settings.yml" >}}
configurations:
  name: "config_${var}"
  template: "parameter BITS = $var;"

variables:
  var:
    type: power_of_two
    settings:
      from: 8
      to: 1024
{{< /code >}}

Every variable type (`bool`, `range`, `list`, `power_of_two`, `multiples`,
`function`, `conversion`, `format`, set operations) is documented on
[Variables](/docs/configurations/variables/). A `variables` block written inside
`generate_configurations_settings`, where it used to be declared, is still read.
Variables declared without a `configurations` block and referenced in a
`generate_command` become
[virtual parameter domains](/docs/configurations/virtual_param_domains/) instead.

## Exclusions

Combinations of the parameter domains of the design that are not part of its
design space. Written once here, they apply to every sweep, every search and the
configuration preview of the GUI alike. See
[Exclusions](/docs/configurations/exclusions/).

| Key | Type | Description |
|-----|------|-------------|
| `exclusions` | list or mapping | The rules. A mapping also says what to `apply` and what to `ignore`. |
| `exclusions[].when` | expression | The combination the rule is about. |
| `exclusions[].require` | expression | What such a point has to be instead. The point is only rejected when this does not hold. |
| `exclusions[].kind` | `illegal`, `duplicate` or `dominated` | What kind of exclusion it is. `illegal` by default; `dominated` is only applied when a campaign asks for it. |
| `exclusions[].message` | string | Why, shown when a point is left out. |
| `exclusions[].id` | string | How a campaign turns this one rule off. |

{{< code lang=yaml filename="_settings.yml" >}}
exclusions:
  - id: overlap-single-port
    when: "$Overlap == 'On' and $p_rf_sp == 1"
    kind: illegal
    message: "a single port register file cannot serve both accesses in one cycle"
{{< /code >}}

## Parameter domain settings

A sub-directory of a design is a **parameter domain**. Its `_settings.yml` only
declares how *its* block is replaced — everything else is inherited from the
design.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `start_delimiter` | string | Yes | Start of the block this domain replaces. |
| `stop_delimiter` | string | Yes | End of it. |
| `param_target_file` | path | If not the top level | File this domain writes into. |
| `use_parameters` | bool | No (default `Yes`) | Disable to make the domain values available as placeholders only. |
| `configurations` | — | No | Same as above, scoped to the domain. |
| `attributes` | mapping | No | How to read values off the name or the content of the configurations of this domain, so that [exclusions](/docs/configurations/exclusions/) can be written about hand-written ones (`defaults`, `from_name`, `from_content`, `values`). |

{{< code lang=yaml filename="architectures/AsteRISC/DMEM/_settings.yml" >}}
start_delimiter: "  // <dmem>"
stop_delimiter:  "  // </dmem>"
{{< /code >}}

Each domain must replace a **distinct** block of the target file. See
[Parameter domains](/docs/configurations/param_domains/) for the full picture.

## In the GUI

**RTL Architectures** (`/architectures`) edits this file field by field, and
lists the configurations of each parameter domain — written as files or
described by the rules of the domain, which the **Configuration rules** panel
of that domain edits. See [The Odatix GUI](/docs/gui/app/).

## See also

- Feature: [Architecture exploration](/docs/features/architecture-exploration/) — what this file is for.
- Tutorial: [Implement your own RTL](/tutorials/own_designs/architecture/).
- [Simulation settings](/docs/reference/simulation/) — how a testbench extends a design.
- [Run settings files](/docs/reference/run_settings/) — selecting these designs for a run.
