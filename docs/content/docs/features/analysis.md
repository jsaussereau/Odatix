---
title: "RTL Analysis"
description: "Elaborate every configuration of your designs with several EDA tools at once, and catch missing sources, black boxes and lint issues in seconds instead of hours."
layout: "doc-features"
badge: "Validation"
badgeColor: "#f59e0b"
cta: true
weight: 2
features:
  - title: "Seconds, not hours"
    description: "Elaboration only — no placement, no routing, no licence-hungry synthesis run."
  - title: "Several tools at once"
    description: "Vivado, Genus, Design Compiler and Verilator on the same RTL: each catches what the others accept."
  - title: "Every configuration"
    description: "The whole design space is checked, not just the variant you happened to develop on."
  - title: "Black boxes flagged"
    description: "Critical warnings are singled out, because an empty module synthesizes beautifully."
---

> [!IMPORTANT] Requires Odatix 4.0+

## Check before you commit hours

Launching a synthesis campaign over a large design space is an expensive way to
discover that a parameter file has a typo. `odatix analyze` runs the
**analysis / elaboration** stage of one or several EDA tools on every
configuration and reports, per configuration, whether the tool parsed it,
elaborated it, and what it complained about.

An fmax search would find the same problems too — hours later, one binary-search
iteration at a time. Analysis finds them in seconds, for every configuration, and
tells you *which tool* disagrees with which.

## When you need it

- **Before a large campaign.** You just generated 200 configurations. Ten seconds
  of analysis is cheaper than ten hours of failed synthesis.
- **After changing parameter delimiters or a generation rule.** The fastest way to
  confirm that every generated source is still valid.
- **When targeting several tools.** Code Vivado accepts is not always code Design
  Compiler accepts. Analyzing with both at once surfaces the disagreement before
  the results do.
- **Hunting black boxes.** A module that silently elaborates into a black box
  produces a beautifully small, beautifully fast, completely meaningless
  synthesis result. Analysis flags it.
- **Continuous checks.** Verilator's default flow is a pure lint/elaboration
  checker: no licence, seconds per configuration, fine to run on every commit.

## How it works

Each analyzed configuration ends up in one of four states:

| Status | Meaning |
|--------|---------|
| **PASSED** | The tool elaborated the design and reported nothing. |
| **WARNING** | It elaborated, but the tool warned — a black box, an unresolved reference, a lint complaint. |
| **INCOMPLETE** | The run never reached its completion marker (interrupted, tool quit early). Its verdict cannot be trusted, so it is not reported as passed. |
| **FAILED** | Errors were detected: a parse error, an undeclared signal, a module not found, a failed elaboration. |

Critical warnings are singled out from ordinary ones, for exactly the black-box
reason above.

Odatix prints a summary per tool at the end of the run, writes a report next to
the work directory (`analysis.yml`), and exports one record per configuration to
`results/results_analysis_<tool>.yml`. Four numeric metrics come with each
record — `error_count`, `warning_count`, `critical_warning_count` and
`standard_warning_count` — so a configuration's warning count can be charted like
any other metric.

Whether a tool supports analysis is a property of the tool: a
[`tool.yml`](/docs/reference/tools/) supports it when it declares an
`analysis_command`. Vivado, Genus, Design Compiler and Verilator all do.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | Validates the generated sources of a whole design space in one command. |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) · [Custom-frequency synthesis](/docs/features/rtl_synthesis/) | The natural step before them: analysis is the cheap subset of what they do. |
| [Simulation](/docs/features/simulation/) | Complementary verdicts — analysis says the RTL is *valid*, simulation says it is *correct*. |
| [Explorer](/docs/features/explorer/) | A dedicated dashboard groups configurations by status, with the actual errors and warnings behind each. |
| [Custom tools](/docs/custom_tools/add_tools/) | Declare `analysis_command` and your own tool joins the same comparison. |

## Using it

### From the configuration files and the CLI

What to analyze lives in `odatix_userconfig/analysis_settings.yml`, in the same
form as the synthesis settings files — plus a `tools` list, since analysis is
the one job type that runs several tools at once:

{{< code lang=yaml filename="odatix_userconfig/analysis_settings.yml" >}}
nb_jobs: 8

tools:
  - vivado
  - verilator

architectures:
  - Example_Counter_sv/08bits
  - Example_ALU_sv/*          # every configuration of this design
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze                                  # tools from the settings file
$ odatix analyze --tool vivado                    # one tool
$ odatix analyze --tool vivado verilator genus    # several, same run
$ odatix analyze --tool vivado verilator --flow vivado:implementation
{{< /code >}}

`--flow` follows `--tool`: a bare flow name applies to every selected tool, while
`tool:flow` targets one of them. Work directories go to `work/analysis/`, and
jobs run through the same daemon as every other job type, so the
[Job Monitor](/docs/gui/monitor/) shows their progress and logs live.

Every key is on the
[run settings reference](/docs/reference/run_settings/); every option on the
[commands reference](/docs/commands/).

### From the GUI

`odatix-gui` → **Run Jobs** → **RTL Analysis** lists the tools that declare an
analysis command, lets you tick several, then shows the same job settings as the
settings file — designs, configurations, parallel jobs — and launches. Results
land in the **RTL Analysis** dashboard of Explorer: architectures grouped by
status, counts at a glance, and expandable details listing the errors and
warnings the tool emitted, with the log file behind each one.

## Where to go next

- **Tutorial** — [Analyze the example designs](/tutorials/run_examples/analysis/).
- **Reference** — [Run settings files](/docs/reference/run_settings/) · [Commands](/docs/commands/)
- **Reference** — [`analysis_settings.yml`](/docs/reference/run_settings/), including every status and option in full.
- **Next feature** — [Automated RTL synthesis](/docs/features/rtl_synthesis/), once every configuration elaborates.
