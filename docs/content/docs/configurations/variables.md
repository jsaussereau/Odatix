---
title: "Variables"
description: "The complete reference for Odatix variables — every type, every setting, and the three places where a variable expands into runs: generated configurations, workflow sweeps and generated-RTL architectures."
weight: 2
---

# Variables

> [!IMPORTANT] Requires Odatix 3.4+

A **variable** is a named set of values declared at the root of a `_settings.yml`, under
`variables`. Odatix expands the cross-product of all variables and produces one run per
combination.

The declaration is always the same. What changes is **what the values are used for**:

| Where variables are declared | What Odatix does with them | Guide |
|------------------------------|----------------------------|-------|
| An architecture or a [parameter domain](/docs/configurations/param_domains/) with a `configurations` block | Writes one **parameter file** per combination, from `template`, named by `name`. | [Configuration generation](/docs/configurations/config_generation/) |
| A [workflow](/docs/reference/workflow/) | Substitutes `${var}` in task **commands** — a *virtual parameter domain*, no folder required. | [Virtual parameter domains](/docs/configurations/virtual_param_domains/) |
| An architecture with `generate_rtl: Yes` | Substitutes `${var}` in **`generate_command`**, running the RTL generation once per value. | [Virtual parameter domains](/docs/configurations/virtual_param_domains/) |

One page, one syntax: a `range` behaves identically whether it ends up in a parameter
file, on a simulation command line, or in a Chisel generation command.

{{< toc >}}

## Declaring a variable

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  <name>:
    type: <type>       # mandatory
    settings:          # mandatory for every type except "bool"
      ...
    unit: <string>     # optional — annotates the value in run names
    format: <printf>   # optional — how the value is rendered
    group: <label>     # optional — pair this variable with another
{{< /code >}}

Referencing a variable is done with `$name` or `${name}`. The two forms are equivalent;
use the braced form whenever the name is followed by a character that could be read as
part of it (`${var}bits`).

> [!TIP]
> Longer names are substituted first, so `$WIDTH` and `$WIDTH_OUT` can coexist without
> corrupting each other.

> [!NOTE]
> `variables` used to be declared inside `generate_configurations_settings`, next to
> `template` and `name`. Since variables are not specific to configuration generation,
> they now live at the root of the settings file. Existing files keep working: Odatix
> still reads the former location when the root key is absent, and moves the block to
> the root the next time it writes the file (a save from the GUI or from the
> [Python API](/docs/python_api/), for instance).


## Type summary

| `type` | Adds a dimension | Mandatory settings |
|--------|:---------------:|--------------------|
| `bool` | yes | *(none)* |
| `range` | yes | `from`, `to` (`step` optional) |
| `power_of_two` | yes | `from_2^` + `to_2^`, or `from` + `to` |
| `list` | yes | `list` |
| `multiples` | yes | `from`, `to`, `base` |
| `union` | yes | `sources` |
| `disjunctive_union` | yes | `sources` |
| `intersection` | yes | `sources` |
| `difference` | yes | `sources` (exactly two) |
| `function` | no | `op` |
| `conversion` | no | `source`, `from`, `to` |
| `format` | no | `source` (`format` optional) |

All generators (`bool` excepted) additionally accept `whitelist` and `blacklist`.

## Value generators

These types produce values of their own. Each one is a **dimension**: it multiplies the
number of generated runs.

### `bool`

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  enable_pipeline:
    type: bool
{{< /code >}}

Generates `{0, 1}`. The only type that needs no `settings`.

### `range`

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: range
    settings:
      from: 10
      to: 100
      step: 10      # optional, defaults to 1
{{< /code >}}

Generates `{10, 20, 30, …, 100}`. Bounds are **inclusive**. `step` must not be 0.

### `power_of_two`

{{< tabs groupId="var-pow2" >}}
{{< tab name="By exponent" >}}

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: power_of_two
    settings:
      from_2^: 5
      to_2^: 10
{{< /code >}}

Generates <code>{32, 64, 128, 256, 512, 1024}</code>.
{{< /tab >}}
{{< tab name="By value" >}}
{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: power_of_two
    settings:
      from: 32
      to: 1024
{{< /code >}}
Generates <code>{32, 64, 128, 256, 512, 1024}</code>.
{{< /tab >}}
{{< /tabs >}}

Both spellings give the same list. Use `from_2^` when the design's parameter *is* the
exponent, `from` when it is the size. With the `from` / `to` form, bounds must be
strictly positive, and a lower bound that is not itself a power of two is rounded **up**
so no generated value falls below it.

### `list`

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: list
    settings:
      list: [100, 225, 412, 803]
{{< /code >}}

The fallback for anything that is not a regular progression. Values need not be
numeric — `list: [balanced, aggressive]` is valid.

### `multiples`

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: multiples
    settings:
      base: 8
      from: 8
      to: 64
{{< /code >}}

Generates every multiple of `base` within `[from:to]` — `{8, 16, 24, …, 64}`. Equivalent
to a `range` with a matching step, but expressed in terms of the constraint that actually
matters (byte alignment, bus width, lane count).

### Filtering with `whitelist` / `blacklist`

Every generator above accepts two optional settings, applied **after** generation:

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: range
    settings:
      from: 1
      to: 10
      blacklist: [3, 7]     # keep everything except these
  other:
    type: range
    settings:
      from: 1
      to: 100
      whitelist: [8, 16, 32]  # keep only these
{{< /code >}}

Use them to punch a hole in an otherwise regular sweep (a value known to break the
design for example) without breaking it into several variables.

> [!TIP]
> For more complex filtering, use [operations between variables](/docs/configurations/variables/#set-operations-between-variables) instead of `whitelist` / `blacklist`.

## Set operations between variables

Four types take a `sources` list of other variables and combine their value sets. The
result is a dimension like any generator; the sources themselves generate **no** runs of
their own.

| `type` | Result |
|--------|--------|
| `union` | All values from every source. |
| `disjunctive_union` | Values in exactly one source (symmetric difference). |
| `intersection` | Values present in **all** sources. |
| `difference` | Values in the first source but not in the second. Exactly **two** sources are required, and order matters. |

{{< code lang=yaml filename="_settings.yml — intersection" >}}
variables:
  mult_3:
    type: multiples
    settings: { base: 3, from: 1, to: 50 }
  mult_4:
    type: multiples
    settings: { base: 4, from: 1, to: 50 }
  inter_var:
    type: intersection
    settings:
      sources: [mult_3, mult_4]
{{< /code >}}

`inter_var` → the common multiples of 3 and 4 in `[1:50]` = `{12, 24, 36, 48}`.

## Derived variables

These types compute a value from the variables already resolved for a combination. They
**do not add a dimension**: they ride along with the values they depend on, so they never
multiply the number of runs.

### `function` — compute an expression

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: multiples
    settings: { from: 0, to: 56, base: 8 }
  var_func:
    type: function
    settings:
      op: ${var}+7
{{< /code >}}

`var` → `{0, 8, …, 56}`, `var_func` → `{7, 15, …, 63}`.

The expression is evaluated in a sandbox containing only the current variable values and
the Python `math` module. `^` is accepted as the power operator (`op: 2^$var`), and the
usual arithmetic and comparison operators apply — `op: math.ceil(math.log2($depth))` is
valid.

> [!TIP]
> `function` is what to reach for whenever two parameters of a design are not
> independent: write the relationship once instead of maintaining two lists that must
> stay in step.
>
> When the relationship is not a value to compute but a combination to rule out,
> use a [constraint](/docs/configurations/config_generation/#constraints-between-variables)
> instead.

### `conversion` — change number base

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  mask_hex:
    type: conversion
    settings:
      source: ${mask}
      from: dec
      to: hex
{{< /code >}}

`from` and `to` each accept `bin`, `dec` and `hex`. The result is a string **without**
prefix (`ff`, not `0xff`), ready to be pasted into a source template or a command line.

### `format` — build a string

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  formatted_bits:
    type: format
    settings:
      source: "${bits}"
      format: "%02d"
{{< /code >}}

`source` is a template substituted with the current values, `format` an optional
printf-style format applied to the result. The classic use is zero-padding so that
generated names sort correctly — `04bits`, `06bits`, `08bits`, `10bits` instead of
`4bits`, `6bits`, `8bits`, `10bits` (see the [Sine ROM example](/docs/examples/architectures/rom/)).

## Optional per-variable keys

### `format` — render a value

Any variable — not only `type: format` ones — accepts a top-level `format` key holding a
printf-style format string applied wherever the variable is substituted:

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  ratio:
    type: list
    format: "%.2f"
    settings:
      list: [0.5, 1, 2]
{{< /code >}}

If the value cannot be formatted with the given string, Odatix warns and falls back to
the plain string value.

### `unit` — annotate the value in run names

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  max_speed:
    type: list
    unit: kmh
    settings:
      list: [35, 45, 55]
{{< /code >}}

The unit is appended to the value in the generated domain name — `max_speed/35kmh`,
`max_speed/45kmh` — reproducing by declaration what a folder-based domain would encode in
its file names. It applies where variables become parameter domains, i.e. workflows and
generated-RTL architectures.

### `group` — pair variables instead of crossing them

By default, every dimension is **cross-combined** with the others. Variables sharing the
same non-empty `group` label are instead **zipped**: matched position by position, so a
couple of parameters stays paired.

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  width:
    type: list
    group: shape
    settings:
      list: [8, 16, 32]
  depth:
    type: list
    group: shape
    settings:
      list: [64, 128, 256]
{{< /code >}}

Produces **three** runs — `8/64`, `16/128`, `32/256` — not nine. If grouped variables
have different value counts, pairing is truncated to the shortest one and Odatix warns.

## Where variables expand into runs

The declaration is shared; the effect depends on the context.

{{< tabs groupId="var-context" >}}
{{% tab name="Generated configurations" %}}
With a `configurations` block, a run resolves one parameter file per
combination. `template` and `name` are mandatory here.

{{< code lang=yaml filename="architectures/ALU/_settings.yml" >}}
configurations:
  name: "config_${var}"
  template: "parameter BITS = $var;"

variables:
  var:
    type: power_of_two
    settings: { from: 8, to: 64 }
{{< /code >}}

Full guide: [Configuration generation](/docs/configurations/config_generation/).
{{% /tab %}}
{{% tab name="Workflows" %}}
In a workflow, variables need neither `template` nor `name`: they become **virtual
parameter domains**, substituted into task commands.

{{< code lang=yaml filename="workflows/traffic/_settings.yml" >}}
use_parameters: No

tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed}

variables:
  max_speed:
    type: list
    unit: kmh
    settings:
      list: [35, 45, 55]
{{< /code >}}

Selectable like any domain: `+ max_speed/45kmh`, or `+ max_speed/*`.

Full guide: [Virtual parameter domains](/docs/configurations/virtual_param_domains/).
{{% /tab %}}
{{% tab name="Generated RTL" %}}
For an architecture that generates its RTL (Chisel, HLS…), the same `${...}`
placeholders are filled in `generate_command`, running the generation once per value.

{{< code lang=yaml filename="architectures/Example_Counter_Chisel_CLI/_settings.yml" >}}
generate_rtl: Yes
generate_command: "sbt 'runMain example.Counter --width ${width} --o=rtl'"
generate_output: "rtl"

use_parameters: No

variables:
  width:
    type: list
    unit: bits
    settings:
      list: [4, 8, 16, 32]
{{< /code >}}

Gives `Example_Counter_Chisel_CLI+width/4bits`, `…+width/8bits`, and so on.

Full guide: [Virtual parameter domains](/docs/configurations/virtual_param_domains/).
{{% /tab %}}
{{< /tabs >}}

> [!NOTE]
> A `${name}` that matches a **file-based** parameter domain is substituted with the
> content of its selected parameter file, and a name matching neither a variable nor a
> domain is left untouched — so environment variables such as `$HOME` still reach the
> shell.

> [!NOTE]
> In an architecture, variables only expand into runs when `generate_command` actually
> references them. An architecture whose variables exist to
> [generate configurations](/docs/configurations/config_generation/)
> (a `configurations` block) keeps that sole meaning.

## See also

- [Configuration generation](/docs/configurations/config_generation/) — writing parameter files from variables
- [Virtual parameter domains](/docs/configurations/virtual_param_domains/) — variables as domains for workflows and generated RTL
- [Parameter domains](/docs/configurations/param_domains/) — file-based domains
- [Configuration generation example](/docs/examples/architectures/config_generation/) — a catalogue architecture demonstrating each type
