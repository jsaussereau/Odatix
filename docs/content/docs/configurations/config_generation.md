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

| Field | Where | Purpose |
|-------|-------|---------|
| `generate_configurations` | root | Turns generation on. |
| `template` | `generate_configurations_settings` | How generated values are written into the configuration file. |
| `name` | `generate_configurations_settings` | Naming convention for each generated configuration. |
| `variables` | root | How values are generated (ranges, lists, functions…). |

> [!NOTE]
> `template` and `name` are specific to configuration generation, and live inside
> `generate_configurations_settings`. `variables` is a general mechanism, also used to
> sweep [workflows and generated-RTL architectures](/docs/configurations/virtual_param_domains/),
> so it is declared at the **root** of the settings file.
>
> Declaring it the former way, inside `generate_configurations_settings`, still works:
> Odatix reads it there when the root key is absent, and moves it to the root the next
> time it writes the file.

## Variables

Every value set is declared as a variable with a `type` and its `settings`:

| Family | Types |
|--------|-------|
| Generators (each adds a dimension) | `bool`, `range`, `power_of_two`, `list`, `multiples` |
| Set operations between variables | `union`, `disjunctive_union`, `intersection`, `difference` |
| Derived values (add no dimension) | `function`, `conversion`, `format` |

The [Variables](/docs/configurations/variables/) page is the exhaustive reference: every
type, its settings, the `whitelist` / `blacklist` filters and the optional `format`,
`unit` and `group` keys. The rest of this page shows how those variables turn into
parameter files.

### A typical example

{{< code lang=yaml filename="_settings.yml" >}}
variables:
  var:
    type: range
    settings:
      from: 10
      to: 100
      step: 10
{{< /code >}}

Generates `{10, 20, 30, …, 100}` — hence ten configurations `config_10` … `config_100`.

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

Variables can also be combined with set operations (`union`, `intersection`…) so that a
generated configuration list follows several constraints at once — see
[Variables](/docs/configurations/variables/#set-operations-between-variables).

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

- [Variables](/docs/configurations/variables/) — the exhaustive variable reference
- [Parameter domains](/docs/configurations/param_domains/)
- [Virtual parameter domains](/docs/configurations/virtual_param_domains/) — the same variables, used by workflows and generated-RTL architectures
- [Configuration reference](/docs/reference/)
