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
> synthesis. See [Configurations](/docs/configurations/#test-a-replacement-on-its-own).

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

## Frequency settings

Two blocks, one per synthesis job type. Both are optional at the root of the
file, but an [fmax search](/docs/features/rtl_fmax_synthesis/) needs bounds from
somewhere.

{{< code lang=yaml filename="_settings.yml" >}}
fmax_synthesis:
  lower_bound: 100          # MHz, start of the binary search
  upper_bound: 900          # MHz, end of it

custom_freq_synthesis:
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
| `step` | `custom_freq_synthesis` | int (MHz) | Increment between two frequency points. |
| `list` | `custom_freq_synthesis` | list of int | Explicit frequency points. |
| `list_append` | `custom_freq_synthesis` | bool (default `false`) | `true` merges `list` with the range; `false` makes `list` the whole set. |

`--from`, `--to`, `--step` and `--at` override these for one run.

### Per-target and per-configuration overrides

A key whose name is a **target** holds settings that apply to that target only;
inside it, a key whose name is a **configuration** narrows it further. The most
specific definition wins.

{{< code lang=yaml filename="_settings.yml" >}}
fmax_synthesis:                  # applies to everything
  lower_bound: 50
  upper_bound: 500

xc7a100t-csg324-1:               # ... except on this target
  fmax_synthesis:
    lower_bound: 250
    upper_bound: 900
  custom_freq_synthesis:
    list: [50, 100, 200]

  32bits:                        # ... and this configuration of that target
    fmax_synthesis:
      lower_bound: 280
      upper_bound: 950
{{< /code >}}

Bounds that are too wide cost synthesis runs; bounds that are too narrow make a
search stop at an edge. Setting them per target is what keeps a large campaign
fast.

> [!NOTE]
> The legacy root keys `fmax_lower_bound` and `fmax_upper_bound` are still read,
> but deprecated in favour of the `fmax_synthesis` block.

## Configuration generation

Instead of writing the parameter files by hand, a design (or a domain) can
generate them from a rule.

| Key | Type | Description |
|-----|------|-------------|
| `generate_configurations` | bool | Enable generation for this design or domain. |
| `generate_configurations_settings` | mapping | The rule: `template`, `name`, and `variables`. |

{{< code lang=yaml filename="_settings.yml" >}}
generate_configurations: Yes
generate_configurations_settings:
  template: "parameter BITS = $var;"
  name: "config_${var}"
  variables:
    var:
      type: power_of_two
      settings:
        from: 8
        to: 1024
{{< /code >}}

Every variable type (`range`, `list`, `power_of_two`, `multiples`, `function`,
set operations) is documented on
[Configuration generation](/docs/configurations/config_generation/). Variables
declared without `generate_configurations` and referenced in a
`generate_command` become
[virtual parameter domains](/docs/configurations/virtual_param_domains/) instead.

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
| `generate_configurations` / `generate_configurations_settings` | — | No | Same as above, scoped to the domain. |

{{< code lang=yaml filename="architectures/AsteRISC/DMEM/_settings.yml" >}}
start_delimiter: "  // <dmem>"
stop_delimiter:  "  // </dmem>"
{{< /code >}}

Each domain must replace a **distinct** block of the target file. See
[Parameter domains](/docs/configurations/param_domains/) for the full picture.

## In the GUI

**RTL Architectures** (`/architectures`) edits this file field by field, lists
the configurations with an editor for each parameter file, and exposes the
**Configuration Generator** for the generation rules. See
[The Odatix GUI](/docs/gui/app/).

## See also

- Feature: [Architecture exploration](/docs/features/architecture-exploration/) — what this file is for.
- Tutorial: [Implement your own RTL](/tutorials/own_designs/synthesis/).
- [Simulation settings](/docs/reference/simulation/) — how a testbench extends a design.
- [Run settings files](/docs/reference/run_settings/) — selecting these designs for a run.
