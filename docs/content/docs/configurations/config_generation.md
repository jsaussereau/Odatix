---
title: "Configuration Generation"
description: "Generate parameter configurations automatically from compact YAML rules — ranges, powers of two, lists, functions and set operations."
weight: 4
---

# Configuration Generation

> [!IMPORTANT] Requires Odatix 3.4+

Odatix can **generate configurations automatically** instead of you writing one parameter file per variant. With a few YAML rules, it produces customized parameter combinations using ranges, powers of two, lists, computed functions and set operations.

{{< toc >}}

## Syntax

To enable generation, add the following to an architecture `_settings.yml` (or a [parameter domain](/docs/configurations/param_domains/) `_settings.yml`):

{{< code lang=yaml filename="_settings.yml" >}}
generate_configurations: Yes
generate_configurations_settings:
  template: "parameter VALUE = $var;"
  name: "config_${var}"
  variables:
    # one or more variable definitions (see below)
{{< /code >}}

| Field | Purpose |
|-------|---------|
| `generate_configurations` | Turns generation on. |
| `template` | How generated values are written into the configuration file. |
| `name` | Naming convention for each generated configuration. |
| `variables` | How values are generated (ranges, lists, functions…). |

## Variable definition methods

### Range

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: range
    settings:
      from: 10
      to: 100
      step: 10
{{< /code >}}

Generates `{10, 20, 30, …, 100}`.

### Power of two

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: power_of_two
    settings:
      from_2^: 5
      to_2^: 10
{{< /code >}}

Generates `{2^5 … 2^10}` = `{32, 64, 128, 256, 512, 1024}`. You can also give the bounds directly with `from: 32` / `to: 1024`.

### Explicit list

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: list
    settings:
      list: [100, 225, 412, 803]
{{< /code >}}

### Multiples of a base

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: multiples
    settings:
      base: 8
      from: 8
      to: 64
{{< /code >}}

Generates `{8, 16, 24, …, 64}`.

### Computed values (functions)

Reference another variable with `$name` and compute a new one:

{{< code lang=yaml filename="_settings.yml" >}}
generate_configurations: Yes
generate_configurations_settings:
  template: "parameter VALUE_START = $var;\n parameter VALUE_END = ${var_func};"
  name: "config_${var}..${var_func}"
  variables:
    var:
      type: multiples
      settings: { from: 0, to: 56, base: 8 }
    var_func:
      type: function
      settings:
        op: ${var}+7
{{< /code >}}

`var` → `{0, 8, 16, …, 56}`, `var_func` → `{7, 15, 23, …, 63}`, producing `config_0..7`, `config_8..15`, …

## Operations between variables

Variables can be combined with set operations via `sources`:

| `type` | Result |
|--------|--------|
| `union` | All values from every source. |
| `disjunctive_union` | Values in exactly one source (symmetric difference). |
| `intersection` | Values present in **all** sources. |
| `difference` | Values in the first source but not the others. |

{{< code lang=yaml filename="_settings.yml — intersection example" >}}
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

`inter_var` → common multiples of 3 and 4 in `[1:50]` = `{12, 24, 36, 48}`.

## Combining multiple parameters

Several generated variables can be combined so Odatix produces the full cross-product of configurations:

{{< code lang=yaml filename="_settings.yml" >}}
generate_configurations: Yes
generate_configurations_settings:
  template: "\n  parameter p_dmem_depth_pw2 = $dmem_depth,\n  parameter p_imem_depth_pw2 = $imem_depth,\n"
  name: "DMEM_${dmem_depth_pw2}-IMEM_${imem_depth_pw2}"
  variables:
    dmem_depth:
      type: range
      settings: { from: 8, to: 10 }
    dmem_depth_pw2:
      type: function
      settings: { op: 2^$dmem_depth }
    imem_depth:
      type: range
      settings: { from: 8, to: 10 }
    imem_depth_pw2:
      type: function
      settings: { op: 2^$imem_depth }
{{< /code >}}

Produces `DMEM_256-IMEM_256`, `DMEM_256-IMEM_512`, … `DMEM_1024-IMEM_1024` (nine configurations).

## Generate

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix generate
{{< /code >}}

Odatix lists every configuration it will create and asks for confirmation before writing the parameter files.

## See also

- [Parameter domains](/docs/configurations/param_domains/)
- [Configuration reference](/docs/reference/)
