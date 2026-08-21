---
title: "Configuration Generation"
description: "Generate parameter configurations automatically from compact YAML rules — ranges, powers of two, lists, functions and set operations."
weight: 5
---

# Configuration Generation

> [!IMPORTANT] Requires Odatix 3.4+

Odatix can **generate configurations automatically** instead of you writing one parameter file per variant. With a few YAML rules, it produces customized parameter combinations using ranges, powers of two, lists, computed functions and set operations.

{{< toc >}}

## Syntax

To enable generation, add the following to an architecture `_settings.yml` (or a [parameter domain](/docs/configurations/param_domains/) `_settings.yml`):

{{< code lang=yaml filename="_settings.yml" >}}
configurations:
  name: "config_${var}"
  template: "parameter VALUE = $var;"

variables:
  # one or more variable definitions (see below)
{{< /code >}}

| Field | Where | Purpose |
|-------|-------|---------|
| `name` | `configurations` | Naming convention for each configuration. |
| `template` | `configurations` | How the values are written into the configuration file. |
| `blacklist` | `configurations` | Generated configuration names to exclude from runs. |
| `constraints` | `configurations` | Conditions the values have to satisfy for a combination to exist. |
| `variables` | root | How values are generated (ranges, lists, functions…). |

Describing configurations is what asks for them: there is no flag to turn on.

A [parameter domain](/docs/configurations/param_domains/) sweeping a **single
variable** does not need `configurations` at all — declaring the variable says
everything:

{{< code lang=yaml filename="width/_settings.yml" >}}
variables:
  width:
    type: range
    settings: {from: 4, to: 12, step: 4}
{{< /code >}}

Its configurations are named after the values of that variable and hold them:
`4`, `8` and `12`. Writing `name: "${width}"` and `template: "${width}"` would
say the same thing twice. Either can still be written to say something else —
`name: "${width}bits"` keeps the implicit template — and with more than one
variable both have to be, since how the values are combined and written cannot
be guessed.

> [!NOTE]
> This holds for a **named** parameter domain (a subdirectory with its own
> `_settings.yml`). At the root of an architecture or of a workflow, the same
> variables may instead be substituted into its commands — a
> [virtual parameter domain](/docs/configurations/virtual_param_domains/) — so
> nothing is implied there, and the rules say what they mean.

> [!NOTE]
> `name` and `template` say how the configurations of *this* domain are built, and
> live inside `configurations`. `variables` is a general mechanism, also used to
> sweep [workflows and generated-RTL architectures](/docs/configurations/virtual_param_domains/),
> so it is declared at the **root** of the settings file.
>
> The former way of saying all this — `generate_configurations: Yes` with a
> `generate_configurations_settings` block, variables inside it — still works.
> Odatix reads it, and writes the form above the next time it saves the file. No
> file has to be migrated by hand.

## Excluding configurations

To exclude one generated combination without changing the values available to
other combinations, add its rendered name to `configurations.blacklist`:

{{< code lang=yaml filename="_settings.yml" >}}
configurations:
  name: "${width}bits"
  template: "parameter WIDTH = ${width};"
  blacklist: ["16bits"]
{{< /code >}}

Blacklisted names are not included in runs or generated output. The
Configuration Editor keeps them visible with a restore button, so the same
entry can be removed from the blacklist later. Names do not include the `.txt`
extension.

## Constraints between variables

Some combinations of values simply do not make sense: a feature that requires
another one, a width that has to stay above a depth. Rather than working out
which configuration names they produce and blacklisting them one by one,
`configurations.constraints` says the condition itself — one boolean expression
per entry, over the variables of the domain:

{{< code lang=yaml filename="_settings.yml" >}}
configurations:
  name: "M${value_dec}"
  template: "..."
  constraints:
    - "${p_rf_sp} <= ${p_rf_read_buf}"          # p_rf_sp requires p_rf_read_buf
    - expr: "${width} >= ${depth}"
      message: "the word has to be at least as wide as the address"
{{< /code >}}

A combination that does not satisfy **every** constraint is not a configuration
of the domain at all: it is never named, never counted, never shown and never
run. That is what tells constraints apart from the blacklist, which names
configurations that exist but are not run.

Expressions are written like the `op` of a
[`function` variable](/docs/configurations/variables/#function--compute-an-expression): `${name}` (or
`$name`) stands for the value of a variable, `math` is available, and `and`,
`or`, `not` combine conditions. `bool` variables are `0` and `1`, so `<=`
expresses an implication: `${a} <= ${b}` means *`a` requires `b`*. Derived
variables (`function`, `conversion`, `format`) may be used too, since they are
computed before the constraints are checked.

Either form works: the expression alone, or `expr` with a `message` saying why
the combination is rejected.

> [!NOTE]
> An expression that cannot be evaluated — a misspelled variable, for instance —
> is reported and rejects every combination, so a typo empties the domain
> loudly instead of quietly keeping everything.

## Several rule sets

Some architectures are not one family of configurations but several. A
parameter deciding *which other parameters mean anything* — a pipelined
datapath whose stages are configurable, against a multicycle one whose buffers
are — describes two families that share nothing: combining a stage of one with
a buffer of the other names a design that does not exist.

Writing `configurations` as a **list** declares one rule set per entry, each
with its own `name`, `template`, `constraints` and `blacklist`. What they
describe is their **union**: nothing is combined across rule sets.

{{< code lang=yaml filename="_settings.yml" >}}
configurations:
  - name: "M${m_value_dec}"                 # multicycle: the buffers vary
    template: |
      parameter p_pipeline     = 0,
      parameter p_prefetch_buf = $p_prefetch_buf,
      parameter p_decode_buf   = $p_decode_buf,
    constraints:
      - "${p_rf_sp} <= ${p_rf_read_buf}"

  - name: "P${p_value_dec}"                 # pipeline: the stages vary
    template: |
      parameter p_pipeline  = 1,
      parameter p_stage_IC  = $p_stage_IC,
      parameter p_stage_ID  = $p_stage_ID,

variables:
  # every variable of both families, declared once
{{< /code >}}

Variables are still declared **once**, at the root. A rule set is about the
ones it *uses*: the variables its name, its template and its constraints
mention, and the ones those are computed from. Everything else is left out of
that rule set — which is what keeps the two families from being combined. A
variable named in a template as plain text (`parameter p_stage_IF = 1,`) is
text, not a use: only `$name` and `${name}` are.

A rule set that has to sweep a variable it never spells out can say so with a
`variables` list of names, next to its `name` and `template`.

> [!NOTE]
> Every configuration of the union needs its own name, across rule sets as well
> as within one. Two rule sets naming a configuration alike is reported the same
> way one rule set naming two combinations alike is.

> [!NOTE]
> The Configuration Editor shows what several rule sets generate, and leaves the
> file as it is. Editing the rules themselves is done in the settings file for
> now.

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
configurations:
  name: "config_${var}..${var_func}"
  template: "parameter VALUE_START = $var;\n parameter VALUE_END = ${var_func};"

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
configurations:
  name: "DMEM_${dmem_depth_pw2}-IMEM_${imem_depth_pw2}"
  template: "\n  parameter p_dmem_depth_pw2 = $dmem_depth,\n  parameter p_imem_depth_pw2 = $imem_depth,\n"

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

## Writing the configurations out

Nothing has to be generated before a run: a run resolves what the rules describe
on its own, and a search resolves only the points it evaluates.

Writing the configurations out as files stays useful — to read them, to track
them, or to correct one by hand:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix generate
{{< /code >}}

Odatix lists every configuration it will write and asks for confirmation first.

A configuration you then edit is **kept**: the next `odatix generate` leaves it
alone, and the run uses your version. `-o` takes it back to what its rule says,
and `-C` deletes what an earlier generation wrote and the rules no longer
describe — never a file you wrote yourself.

> [!NOTE]
> A configuration a run resolves on its own is written under `.odatix_configs/`,
> inside the directory of the domain, so a run never adds files to the ones you
> keep. You never have to look at it, and deleting it is always safe: the next run
> resolves the same configurations again. Add it to your `.gitignore`.

## In the GUI

Every parameter domain of the **RTL Architectures** and **Workflows** editors
carries a **Configuration rules** panel, folded away until you open it. It edits
the two templates and the variables of this page, and shows the values each
variable takes as you type. The `${...}` of both templates are highlighted:
green for a variable this domain declares, orange for a name nothing here
defines — usually a typo, since a rule has no other source of values. A named
domain can leave both fields empty: they then show what Odatix uses in
their place — the values themselves, joined by an underscore for the name and
written one per line for the content.

While the rules differ from what the settings file holds, the configurations
they would produce are previewed above the ones the domain has, as dashed cards:
nothing is written until you save. Once saved, they join the configurations of
the domain, each labelled with where it comes from:

| Label | What it means |
|-------|---------------|
| *generated* | The rules produce it, and no file says otherwise. Renaming it means changing the name template. |
| *edited* | The rules produce it, and a file of the same name says something else. The file is what runs use, and `odatix generate` leaves it alone. |
| (none) | A file the rules know nothing about, written by hand. |

## See also

- [Variables](/docs/configurations/variables/) — the exhaustive variable reference
- [Parameter domains](/docs/configurations/param_domains/)
- [Virtual parameter domains](/docs/configurations/virtual_param_domains/) — the same variables, used by workflows and generated-RTL architectures
- [Configuration reference](/docs/reference/)
