---
title: "Configuration Generation"
description: "A catalogue architecture that cannot be synthesized: ten settings files, one per way of generating a list of configurations, from a plain range to set operations between variables."
weight: 6
---

# Configuration Generation

`Example_Config_Generation` is not a design. It has no RTL, no clock, no top level — and it is stated plainly at the top of its own settings file:

{{< code lang=yaml filename="architectures/Example_Config_Generation/_settings.yml" >}}
###################################################################
#              THIS EXAMPLE CANNOT BE SYNTHETIZED                 #
# ITS ONLY PURPOSE IS GIVE SOME CONFIGURATION GENERATION EXAMPLES #
###################################################################

rtl_path: ""

top_level_file: ""
top_level_module: ""
rtl_file_format: ""

clock_signal: ""
reset_signal: ""

# Delimiters for parameter files
use_parameters: Yes
start_delimiter: "  // <main>"
stop_delimiter: "  // </main>"
{{< /code >}}

It is a **catalogue**: ten sub-directories, each a self-contained `_settings.yml` demonstrating one way of turning a variable declaration into a list of configurations. Read it as a reference alongside the [configuration generation](/docs/configurations/config_generation/) documentation, and copy the block you need into a real architecture.

{{< details title="What this example demonstrates" >}}
- **The four value generators** — `range`, `power_of_two`, `list`, `multiples`.
- **Derived variables** — `function`, which computes a value from another variable.
- **Set operations between variables** — `union`, `disjunctive_union`, `intersection`, `difference`.
- **Multi-parameter templates** — one generated configuration writing several parameters at once.
- **The `template` / `name` split** — what gets written into the source, and what the configuration is called.
{{< /details >}}


{{< toc >}}

## How generation works

Every sub-directory follows the same shape:

{{< code lang=yaml >}}
start_delimiter: "  // test parameters begin"
stop_delimiter: "  // test parameters end"

generate_configurations: Yes
generate_configurations_settings:
  template: "parameter VALUE = $var;"   # what is written into the source
  name: "config_${var}"                 # what the configuration is called

variables:
  var:
    type: <generator>
    settings:
      ...
{{< /code >}}

- **`variables`** declares one or more named value sets. Each has a `type` and its own `settings`.
- **`template`** is the text substituted between the delimiters, with `$var` / `${var}` replaced by the value.
- **`name`** is the label of the generated configuration — what appears in run selectors, result files and [Explorer](/docs/features/explorer/) legends.

Odatix takes the cross-product of the variables, then writes one configuration per combination.

> [!TIP]
> `$var` and `${var}` are the same thing. Use the braced form whenever the name is immediately followed by a character that could be read as part of it — `${var}bits`, `${var_func}` — which is most of the time.

## The value generators

### `range` — every integer from A to B

{{< code lang=yaml filename="architectures/Example_Config_Generation/01_Range/_settings.yml" >}}
generate_configurations: Yes
generate_configurations_settings:
  template: "parameter VALUE = $var;"
  name: "config_${var}"

variables:
  var:
    type: range
    settings:
      from: 10
      to: 100
      step: 10
{{< /code >}}

Generates `config_10`, `config_20`, … `config_100` — ten configurations. `step` defaults to 1; the `data` domain of the [ROM example](/docs/examples/rom/) uses `from: 8, to: 14` with no step at all.

### `power_of_two` — exponentially spaced values

The natural sweep for memory depths, FIFO sizes, cache lines. It comes in two spellings, and they generate the **same list**:

{{< tabs groupId="cfg-pow2" >}}
{{< tab name="By exponent" >}}
```yaml
variables:
  var:
    type: power_of_two
    settings:
      from_2^: 5
      to_2^: 10
```
Generates `32, 64, 128, 256, 512, 1024`.
{{< /tab >}}
{{< tab name="By value" >}}
```yaml
variables:
  var:
    type: power_of_two
    settings:
      from: 32
      to: 1024
```
Generates `32, 64, 128, 256, 512, 1024`.
{{< /tab >}}
{{< /tabs >}}

Use whichever form matches how you think about the parameter: `from_2^` when the design's parameter *is* the exponent, `from` when it is the size.

### `list` — an explicit set of values

{{< code lang=yaml filename="architectures/Example_Config_Generation/03_List/_settings.yml" >}}
variables:
  var:
    type: list
    settings:
      list: [100, 225, 412, 803]
{{< /code >}}

The fallback for anything that is not a regular progression: benchmark sizes, a set of technology corners, values known to be interesting. Note that the values need not be numeric — `list: [balanced, aggressive]` is perfectly valid.

### `multiples` — every multiple of a base

{{< code lang=yaml filename="architectures/Example_Config_Generation/04_Multiples/_settings.yml" >}}
variables:
  var:
    type: multiples
    settings:
      base: 8
      from: 8
      to: 64
{{< /code >}}

Generates `8, 16, 24, 32, 40, 48, 56, 64`. Equivalent to a `range` with a matching step, but expressed in terms of the constraint that actually matters — byte alignment, bus width, lane count — so the intent survives in the file.

## Derived and combined variables

The remaining types do not produce values of their own: they **compute** them from other variables.

### `function` — compute from another variable

{{< code lang=yaml filename="architectures/Example_Config_Generation/05_Function/_settings.yml" >}}
generate_configurations_settings:
  template: "parameter VALUE_START = $var;\n parameter VALUE_END = ${var_func};"
  name: "config_${var}..${var_func}"

variables:
  var:
    type: multiples
    settings:
      from: 0
      to: 56
      base: 8
  var_func:
    type: function
    settings:
      op: ${var}+7
{{< /code >}}

`var` walks `0, 8, 16, … 56`, and `var_func` is always `var + 7`. The configurations are named `config_0..7`, `config_8..15`, `config_16..23`, and each writes **two** parameters — a start and an end address, expressed as an aligned base and its inclusive last byte.

A `function` variable is **not** a second dimension: it does not multiply the number of configurations, it rides along with the variable it depends on.

> [!TIP]
> `function` is what to reach for whenever two parameters of a design are not independent. Writing the relationship once in the settings is better than maintaining two lists that have to stay in step.

### The set operations

Four types take a `sources` list of other variables and combine their value sets.

{{< tabs groupId="cfg-sets" >}}
{{< tab name="union" >}}
```yaml
variables:
  var_1:
    type: list
    settings: { list: [50, 60] }
  var_2:
    type: list
    settings: { list: [10, 100] }
  union_var:
    type: union
    settings:
      sources: [var_1, var_2]
```
All values from either source: `10, 50, 60, 100`.

Use it to merge several regular progressions into one sweep — for instance a fine `range` over the interesting region plus a coarse `list` of far-away points.
{{< /tab >}}
{{< tab name="disjunctive_union" >}}
```yaml
variables:
  var_1:
    type: list
    settings: { list: [50, 60] }
  var_2:
    type: list
    settings: { list: [10, 50, 100] }
  union_var:
    type: disjunctive_union
    settings:
      sources: [var_1, var_2]
```
The symmetric difference — values in exactly one source: `10, 60, 100`.

`50` is in both, so it is dropped.
{{< /tab >}}
{{< tab name="intersection" >}}
```yaml
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
```
Values present in every source — here the multiples of 12: `12, 24, 36, 48`.

The readable way to express a value that must satisfy two independent alignment constraints at once.
{{< /tab >}}
{{< tab name="difference" >}}
```yaml
variables:
  mult_3:
    type: multiples
    settings: { base: 3, from: 1, to: 50 }
  mult_4:
    type: multiples
    settings: { base: 4, from: 1, to: 50 }
  diff_var:
    type: difference
    settings:
      sources: [mult_4, mult_3]
```
Values in the first source but not in the others — multiples of 4 that are not multiples of 3: `4, 8, 16, 20, 28, 32, 40, 44`.

Order matters here, unlike the other three.
{{< /tab >}}
{{< /tabs >}}

> [!INFO]
> Only the **combined** variable is used in `template` and `name`. `var_1`, `var_2`, `mult_3`, `mult_4` are intermediate value sets and generate no configurations of their own.

## Several parameters in one configuration

The last sub-directory puts it together: two independent dimensions, each with a derived companion, all written by a single multi-line template.

{{< code lang=yaml filename="architectures/Example_Config_Generation/10_Multiple_Parameters/_settings.yml" >}}
generate_configurations: Yes
generate_configurations_settings:
  template: "\n  parameter p_dmem_depth_pw2  = $dmem_depth,\n  parameter p_imem_depth_pw2  = $imem_depth,\n"
  name: "DMEM_${dmem_depth_pw2}-IMEM_${imem_depth_pw2}"

variables:
  dmem_depth:
    type: range
    settings:
      from: 8
      to: 10
  dmem_depth_pw2:
    type: function
    settings:
      op: 2^$dmem_depth
  imem_depth:
    type: range
    settings:
      from: 8
      to: 10
  imem_depth_pw2:
    type: function
    settings:
      op: 2^$imem_depth
{{< /code >}}

This is the pattern from a real CPU configuration, and it shows the `template` / `name` split at its most useful:

- The **source** wants the exponents — the design's parameters are `p_dmem_depth_pw2` and `p_imem_depth_pw2`, expressed as powers of two — so `template` writes `8`, `9`, `10`.
- The **name** should be readable by a human looking at a plot legend, so it writes the actual depths: `DMEM_256-IMEM_256`, `DMEM_256-IMEM_512`, … `DMEM_1024-IMEM_1024`.

Two `range` variables of three values each give **nine** configurations; the two `function` variables add none, they only relabel.

> [!TIP]
> Escaped newlines (`\n`) inside `template` are how a single configuration writes several lines. Watch the trailing comma in the example: the template is designed to sit inside an existing parameter list, between delimiters that leave the rest of the list intact.

## When to generate, and when not to

Generation is the right answer when the configuration list is **derivable** — a regular progression, a constrained set, or two parameters tied by a formula. It keeps the intent in the file, and adding a value means changing one number.

Hand-written `.txt` files stay the better answer when the list is short, irregular, and unlikely to change — the seven `04bits.txt … 64bits.txt` files of the [counter](/docs/examples/counter/) are clearer as files than as a generator.

And when the design already accepts the parameter on its command line, neither is needed: see [virtual parameter domains](/docs/configurations/virtual_param_domains/) and the CLI variant of the counter.

## Where to go next

- [Variables](/docs/configurations/variables/) — the full reference for every variable type shown here, plus the ones this example does not cover (`bool`, `conversion`, filtering, `group`).
- [Configuration generation](/docs/configurations/config_generation/) — how those variables become parameter files.
- [Sine ROM](/docs/examples/rom/) — generation used for real, inside two parameter domains, with a `format` variable for readable names.
- [Parameter domains](/docs/configurations/param_domains/) — how generated configurations combine across dimensions.
