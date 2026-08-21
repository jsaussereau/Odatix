---
title: "Exclusions"
description: "Leave out the combinations of several parameter domains that are illegal, duplicated or dominated — once, next to the design."
weight: 3
---


# Exclusions

> [!IMPORTANT] Requires Odatix 4.0+

[Constraints](/docs/configurations/config_generation/#constraints-between-variables) say
which combinations of **one** parameter domain mean something. **Exclusions** say
the same thing about the whole design space: one domain against another, a
domain against the topology it runs in, a parameter that only exists under one
architecture.

They are written once, in the `_settings.yml` of the architecture, and they
apply everywhere the design space is walked — an `odatix fmax` sweep, a
simulation sweep, an `odatix dse` search and the configuration preview of the
graphical interface all leave out exactly the same points.

{{< toc >}}

## Why

Without them, a combination that does not exist is left out by *not writing the
sweep line that would produce it*: once in `fmax_synthesis_settings.yml`, once
in `simulations_settings.yml`, once per campaign. The knowledge lives in three
files, none of which says why, and a search reads none of them.

## Writing one

{{< code lang=yaml filename="_settings.yml" >}}
exclusions:
  - id: overlap-single-port
    when: "$Overlap == 'On' and $p_rf_sp == 1"
    kind: illegal
    message: "a single port register file cannot serve the merged write of i and the read of i+1"

  - id: forwarding-without-rf-barrier
    when: "$config.stage_RF == 0"
    require: "$Fwd.p_fwd_pw == 1"
    kind: duplicate

  - id: share-adder-with-static-branches
    when: "$p_alu_share_adder == 1 and $BranchPred == 'Off' and $PipeCtrl.p_branch_stage == 0"
    kind: dominated
    message: "both worst contributions to the critical path at once"
{{< /code >}}

| key | meaning |
|-----|---------|
| `when` | the combination the rule is about. A point is rejected when it holds. |
| `require` | what such a point has to be instead. Written, the point is only rejected when the `require` does **not** hold. |
| `kind` | `illegal`, `duplicate` or `dominated` (see below). `illegal` when nothing says. |
| `message` | why, shown when the point is left out. |
| `id` | how a campaign turns this one rule off. |

An entry written as a bare expression says what has to be **true**, exactly like
a domain constraint: `- "$a <= $b"`.

## The three kinds

`illegal`
: The design does not work — the RTL asserts, the elaboration fails. The point
  does not exist. Asking for it by name is an error; a wildcard simply does not
  expand to it.

`duplicate`
: The design works and is the *same hardware* as another one: a parameter that
  the rest of the configuration makes meaningless. What matters is not to drop
  it but to pick one, which is what `require` is for — it names the canonical
  value. A search **folds** the other points onto it instead of throwing them
  away, so the space keeps its density and the budget is not spent proposing
  points that do not exist.

`dominated`
: The design works and is its own, but another one beats it on everything a
  campaign is looking for. That is knowledge about a *question*, not about the
  design, so it is **not applied by default**.

A sweep says what it left out once per rule — how many combinations that rule
took out, and one of them as an example — rather than once per combination: a
wildcard over six parameter domains leaves out tens of thousands of points, and
saying so one by one hides the reason instead of giving it.

## What an expression reads

| written | is |
|---------|-----|
| `$variable` | a variable of the main domain |
| `$domain` | the **name** of the configuration a domain contributes (`$Overlap == 'On'`) |
| `$domain.variable` | one of the values behind it |
| `$config`, `$main` | the configuration of the main domain, and its values |
| `$architecture` | the name of the architecture |

Plus `match($config, 'P-*RF1*')` (shell pattern), `matches()` (regular
expression), `contains()`, `defined()`, `min`, `max`, `abs` and `math`.

A name nothing defines is **unknown**: it compares equal to nothing and is
falsy, so an exclusion mentioning a domain that a given architecture does not
have never fires instead of breaking the space. An expression that cannot be
evaluated at all is reported once and rejects nothing.

## Reading a hand-written configuration

A configuration built by rules carries its variables, and `$domain.variable`
reads them directly. A configuration written by hand is a file with a name and a
content — and yet what tells one pipeline topology from another is exactly what
an exclusion needs to read.

An `attributes` block says how to read values off that name or that content, in
the `_settings.yml` of the domain that holds them:

{{< code lang=yaml filename="topologies/_settings.yml" >}}
attributes:
  defaults:
    stage_EX: 0
    stage_RF: 0
  from_name: "(?:EX(?P<stage_EX>\\d+))?(?:RF(?P<stage_RF>\\d+))?"
  from_content: "p_stage_EX\\s*=\\s*(?P<stage_EX>\\d+)"
  values:
    "P-IF1MA1": {legacy: 1}
{{< /code >}}

The regular expressions are read for their **named groups** and nothing else; a
group that does not match leaves the attribute at its default. Values that look
like numbers are compared as numbers, so `$config.stage_EX >= 2` means what it
says. `values` reaches, by [selector](/docs/configurations/param_domains/), the
configurations a pattern cannot.

The order is: `defaults`, `from_name`, `from_content`, `values`, then the
variables of the rules — the most direct knowledge wins.

> [!TIP]
> If you can, describe the family with variables instead: a generated
> configuration already carries everything, and `attributes` is there for the
> ones that are written by hand.

## What a campaign decides

An exclusion is a property of the design, so the rules live with the
architecture. What a campaign is entitled to decide is which of them its
question applies:

{{< code lang=yaml filename="dse_campaigns/frequency.yml" >}}
exclusions:
  apply: [illegal, duplicate, dominated]
  ignore: [share-adder-with-static-branches]
  rules:
    - when: "$width == 8"
      kind: dominated
{{< /code >}}

`apply` defaults to `[illegal, duplicate]`. `ignore` names the `id` of a rule
this campaign does not want — an area-oriented campaign keeps the design a
frequency-oriented one calls dominated. `rules` adds exclusions of its own, on
top of those of the architecture.

The campaign line printed when an exploration starts says how many combinations
the exclusions take out of the space, and the budget is compared against what is
left — the number of designs that exist, not the number of combinations of the
axes.
