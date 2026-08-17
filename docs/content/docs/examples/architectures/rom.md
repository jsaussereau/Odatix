---
title: "Sine ROM (Chisel)"
description: "A generated sine lookup table swept over address width and data width — two parameter domains whose configurations are themselves generated, with formatted names."
weight: 5
---

# Sine ROM (Chisel)

The ROM example sweeps a **generated** sine lookup table over two independent dimensions: how many entries it has, and how wide each entry is. It sits between the [counter](/docs/examples/architectures/counter/) and the [Cordic](/docs/examples/architectures/cordic/) in complexity, and it is the example to read to understand [parameter domains](/docs/configurations/param_domains/) whose configurations are **not written by hand**.

Everything about it is generated twice over: the ROM content is computed in Scala at elaboration time, and the configuration list is computed by Odatix from a variable declaration.

{{< details title="What this example demonstrates" >}}
- **[Parameter domains](/docs/configurations/param_domains/) with generated configurations** — `generate_configurations` inside a domain, so no `.txt` file is written by hand.
- **[Configuration generation](/docs/configurations/config_generation/) applied to real work** — `list` and `range` variables, plus a `format` variable that only exists to make the run names sort correctly.
- **Substitution into a generator, not into RTL** — the values land in a Scala source, and the SystemVerilog does not exist yet when they do.
- **A design whose size is data, not logic** — a genuinely two-dimensional cost surface, since depth and width multiply.
- **`use_parameters: No` at the top level** — the main configuration declares nothing; both parameters live in domains.
{{< /details >}}


{{< toc >}}

## What the design does

`Rom` is a synchronous lookup table holding one period of a sine wave. The Chisel generator computes the content at elaboration time and hands it to the module as a plain Scala sequence:

{{< code lang=scala filename="examples/rom_chisel/src/main/scala/rom.scala" >}}
  // Derived parameters
  val depth = 1 << addr_bits
  val max_val = (1 << data_bits) - 1

  // ROM content generation
  val rom_content = quadrant match {
    ...
    case Quadrant.FULL =>
      // 0 to 2*Pi
      (0 until depth).map { i =>
        val angle = (2 * math.Pi) * i / (depth - 1)
        val value = (math.sin(angle) * max_val).round.toInt
        value
      }
  }
{{< /code >}}

The module itself is a registered read: the address is registered on input, the looked-up value on output.

{{< details title="Interface" >}}
| Port | Direction | Width | Role |
|---|---|---|---|
| `clock` | in | 1 | Clock, rising edge (implicit Chisel clock) |
| `reset` | in | 1 | Reset (implicit Chisel reset) |
| `i_addr` | in | `ADDR_BITS` | Table index |
| `o_data` | out | `DATA_BITS` | Sample, signed in `FULL` mode, unsigned otherwise |

Latency is 2 cycles: one for the registered address, one for the registered output. The input register is optional (`REGISTER_INPUT`), and left enabled here.
{{< /details >}}

{{< details title="Quadrant modes" >}}
`QUADRANT` selects how much of the period is stored:

| Mode | Stored range | Output type |
|---|---|---|
| `QUARTER` | 0 to π/2 | unsigned |
| `HALF` | 0 to π | unsigned |
| `FULL` | 0 to 2π | signed |

Storing a quarter period and reconstructing the rest by symmetry is the classic way to divide a sine table by four. The example fixes `QUADRANT` to `FULL` and does not sweep it — but it is the obvious third domain to add.
{{< /details >}}

### Parameters

| Parameter | Swept values | Effect |
|---|---|---|
| `addr_bits` | 4, 6, 8, 10, 12, 14, 16 | Address width. The table holds 2^`addr_bits` entries, so this sets the **angular resolution** — and the size doubles with every bit. |
| `data_bits` | 8 to 14 | Sample width. Sets the **amplitude quantization** of the stored sine. |

The two are a genuine trade-off, and not redundant: total storage is `2^addr_bits × data_bits` bits, so the two axes cost very differently. Adding one address bit doubles the ROM; adding one data bit grows it by about 10%. Whether that buys anything depends on which error dominates — angular or amplitude — which is exactly what a two-dimensional sweep is for.

> [!TIP]
> This is the same shape of question as the [Cordic](/docs/examples/architectures/cordic/)'s `WIDTH` vs `ITERATIONS`, on a design that stores its answers instead of computing them. Running both and comparing area at equal accuracy is the classic ROM-versus-CORDIC argument.

## Files

{{< code lang=text filename="workspace" >}}
examples/
└── rom_chisel/
    ├── build.sbt
    └── src/main/scala/
        ├── rom.scala              # the ROM and its content generator
        └── counter.scala

odatix_userconfig/
└── architectures/
    └── Example_Rom_Chisel/
        ├── _settings.yml          # main architecture settings
        ├── addr/                  # 'addr' parameter domain
        │   ├── _settings.yml      # generates 08bits.txt … 32bits.txt
        │   └── (generated)
        └── data/                  # 'data' parameter domain
            ├── _settings.yml      # generates 08bits.txt … 14bits.txt
            └── (generated)
{{< /code >}}

## Architecture settings

The main settings declare a generated design and **no parameters at all**:

{{< code lang=yaml filename="architectures/Example_Rom_Chisel/_settings.yml" >}}
# Source files
design_path: "examples/rom_chisel"
design_path_whitelist: ['project', 'src', 'build.sbt']
design_path_blacklist: []

# Generate the rtl (from chisel for example)
generate_rtl: Yes
generate_command: "sbt 'runMain synthetix.Rom --o=rtl'"  # requires sbt and firtool
generate_output: "rtl"

# Generated design settings
top_level_file: "rom.sv"
top_level_module: "rom"
clock_signal: "clock"
reset_signal: "reset"

# Delimiters for parameter files
use_parameters: No
{{< /code >}}

`use_parameters: No` is the same choice the [Cordic](/docs/examples/architectures/cordic/) makes: **both** parameters live in their own [parameter domain](/docs/configurations/param_domains/), so Odatix sweeps them independently and combines them automatically instead of requiring one file per (depth, width) pair.

## The parameter domains

Each domain declares its delimiters, its target file — and how to **generate** its configurations.

{{< code lang=yaml filename="architectures/Example_Rom_Chisel/addr/_settings.yml" >}}
start_delimiter: "  val addr_bits = "
stop_delimiter: " // Address width"
param_target_file: "src/main/scala/rom.scala"

generate_configurations: Yes
generate_configurations_settings:
  template: "${bits}"
  name: "${formatted_bits}bits"

variables:
  bits:
    type: list
    settings:
      list: [4, 6, 8, 10, 12, 14, 16]

  formatted_bits:
    type: format
    settings:
      source: $bits
      format: "%02d"
{{< /code >}}

{{< code lang=yaml filename="architectures/Example_Rom_Chisel/data/_settings.yml" >}}
start_delimiter: "  val data_bits = "
stop_delimiter: " // Data width"
param_target_file: "src/main/scala/rom.scala"

generate_configurations: Yes
generate_configurations_settings:
  template: "${bits}"
  name: "${formatted_bits}bits"

variables:
  bits:
    type: range
    settings:
      from: 8
      to: 14

  formatted_bits:
    type: format
    settings:
      source: $bits
      format: "%02d"
{{< /code >}}

Four things are happening here.

### The delimiters are the trailing comments

{{< code lang=scala filename="examples/rom_chisel/src/main/scala/rom.scala" >}}
object Rom extends App {
  // Parameters
  val data_bits = 8 // Data width
  val addr_bits = 8 // Address width
  val quadrant = Quadrant.FULL // Quadrant type
  val register_input = true // Register input signal
{{< /code >}}

`  val addr_bits = ` … ` // Address width` brackets exactly one value, and the comment doubles as the closing delimiter. The Scala file stays a perfectly ordinary generator that runs on its own — which is the property every substitution scheme in Odatix tries to preserve.

### The substitution happens before elaboration

`param_target_file` points at the **Scala** source. The SystemVerilog does not exist yet: Odatix patches the generator, then runs `generate_command`, and the emitted `rom.sv` already contains the right table. This is why the ROM contents — computed from `addr_bits` and `data_bits` in Scala — always match the parameters of the run.

### `template` versus `name`

`template` is the text written **into the source** — here just the bare number, `${bits}`, because the Scala line already has `val addr_bits = ` in front of it.

`name` is the label of the generated configuration, used in run selectors and in result files.

### The `format` variable exists for sorting

`formatted_bits` computes nothing. It only pads the value to two digits so the configurations are named `04bits`, `06bits`, `08bits`, `10bits`, … instead of `4bits`, `6bits`, `8bits`, `10bits`.

Without it, any alphabetical ordering — directory listings, legends, axis ticks in the [Explorer](/docs/features/explorer/) — puts `10bits` before `4bits`. It is a small thing that makes every plot downstream readable, and it is worth copying into your own domains.

> [!INFO]
> The two domains use different variable types for the same purpose: `list` for `addr` (because the values are not evenly spaced — 4, 6, 8, … 16 skips odd widths) and `range` for `data` (8 to 14, every value). See [Variables](/docs/configurations/variables/) for the full set of types.

## Running the sweep

The two domains are combined with `+`, and `*` expands every value:

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado -a "Example_Rom_Chisel + addr/* + data/*"
{{< /code >}}

With 7 address widths and 7 data widths, that is 49 syntheses — the full cost surface.

A single point, or a slice along one axis:

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado -a "Example_Rom_Chisel + addr/12bits + data/10bits"
$ odatix fmax -t vivado -a "Example_Rom_Chisel + addr/12bits + data/*"
{{< /code >}}

> [!WARNING]
> `addr/16bits` is a **65 536-entry** table. At 14 data bits that is roughly 900 kbit of ROM, which will either be mapped to block RAM, inferred as a large LUT structure, or simply refuse to fit, depending on the target. Start the sweep at the small end.

> [!WARNING]
> Like the other Chisel examples, this one needs **sbt** and **firtool** installed.

## Where to go next

- [Variables](/docs/configurations/variables/) — the full variable-type reference, and the [dedicated example](/docs/examples/architectures/config_generation/) that walks through every one of them.
- [Parameter domains](/docs/configurations/param_domains/) — the mechanism that combines `addr` and `data`.
- [Cordic](/docs/examples/architectures/cordic/) — the same two-dimensional trade-off, computed instead of stored.
- [All architecture examples](/docs/examples/architectures/) — the six designs and what each one adds.
