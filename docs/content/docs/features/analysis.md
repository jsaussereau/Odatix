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
    description: "Vivado, Quartus, Genus, Design Compiler and Verilator on the same RTL: each catches what the others accept."
  - title: "Every configuration"
    description: "The whole design space is checked, not just the variant you happened to develop on."
  - title: "What deserves attention"
    description: "Findings sorted by kind across tools, the normal ones set apart: what is left is what to fix."
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

Each analysis reads what the tool reported and turns it into **findings**: a
severity, a category, what it is about and where. Categories are shared by
every tool — a missing module is the same finding whether Vivado, Quartus or
Verilator reports it — which is what makes tools comparable: the report says
which tool flagged what.

Each analyzed configuration ends up in one of six states:

| Status | Meaning |
|--------|---------|
| **Failed** | The tool found errors in the design: a syntax error, an undeclared signal, a missing module or include, a port that does not exist. |
| **Tool failure** | The tool could not analyze the design — no license, missing technology files, a script error. The design is not at fault. |
| **Incomplete** | The run never reached its completion marker (stopped, tool died). Its verdict cannot be trusted, so it is not reported as passed. |
| **Warnings** | It was analyzed, with warnings that deserve a look: a latch, multiple drivers, a width mismatch, an undriven output. |
| **Not supported** | The design is written in a language the tool does not read (Verilator and VHDL): reported as such, not as a pile of syntax errors. |
| **Passed** | The tool reported nothing, or nothing but expected findings. |

### Expected findings

Some findings are normal. Quartus advises the Reset Release IP for every Agilex
design; a combinational design leaves its clock unused; a debug bus is only
connected in the lab build. Those are **expected**: still reported, apart, with
the reason they are normal — but they do not count. A design whose findings are
all expected passes, so whatever remains in *Warnings* or *Failed* deserves
attention.

What each tool says of every design is declared expected by Odatix. What is
normal for *your* designs goes in the `expected` section of
`analyze_settings.yml`:

{{< code lang=yaml filename="odatix_userconfig/analyze_settings.yml" >}}
expected:
  debug_bus:
    category: unused
    subject: dbg_*
    reason: "Debug bus, only connected in the lab build"
  rom_latch:
    category: latch
    architectures: [Legacy_ROM]
    reason: "The legacy ROM uses a latch on purpose"
{{< /code >}}

The results files keep the verdict read when each job ended: after editing this
section, `odatix results analysis` reads the analyses of the work directory
again and rewrites their records, so that Explorer says what the terminal
report says.

### The report

At the end of the run, `odatix analyze` prints:

1. the status of every design with every tool, side by side, when several tools ran;
2. the kinds of findings, and for how many design points each tool reported them;
3. one line per design that is not clean: its most relevant finding, and where;
4. the expected findings, grouped by reason.

{{< code lang=text filename="Terminal" >}}
 Findings                   quartus   verilator    vivado
 Missing module                2          1          2
 Combinational loop            ·          1          ·
 Latch inferred                1          1          ·
 ...

 ✗ Failed (22)
   D_missing_module · quartus     Instance "u_sub" instantiates undefined entity "sub_missing"  rtl/top.sv:2
   D_missing_module · verilator   Cannot find file containing module: 'sub_missing'            rtl/top.sv:2
 ...
 ○ Expected (19, not counted)
   Other      ×10 in 10 designs (quartus): Quartus advises the Reset Release IP for every Agilex design
{{< /code >}}

Every result is also a record of `results/results_analysis_<tool>.yml`, written
as soon as its job ends — whether the tool succeeded or not. A finished analysis
is not run again unless `-o/--overwrite` is given: after fixing the RTL, run
`odatix analyze -o`. Five metrics come
with each record — `error_count`, `critical_warning_count`, `warning_count`,
`info_count` and `expected_count` — so they can be charted like any other metric.

How each tool's reports are read is declared in the `analysis.yml` of the tool,
not in Odatix: adding a tool, or teaching Odatix a message it does not know, is a
few lines of YAML. See [Analysis definitions](/docs/reference/analysis/).

Whether a tool supports analysis is a property of the tool: a
[`tool.yml`](/docs/reference/tools/) supports it when it declares an
`analysis_command`. Vivado, Quartus, Genus, Design Compiler, Verilator and
LibreLane all do.

An analysis targets no device and no technology: Design Compiler and Genus
elaborate the design into generic cells, so no PDK and no
`target_<tool>.yml` is needed to analyze with them — only their license.

## Working with the rest of Odatix

| Combine it with | Why |
|-----------------|-----|
| [Architecture exploration](/docs/features/architecture-exploration/) | Validates the generated sources of a whole design space in one command. |
| [Fmax synthesis](/docs/features/rtl_fmax_synthesis/) · [Fixed-frequency synthesis](/docs/features/rtl_synthesis/) | The natural step before them: analysis is the cheap subset of what they do. |
| [Simulation](/docs/features/simulation/) | Complementary verdicts — analysis says the RTL is *valid*, simulation says it is *correct*. |
| [Explorer](/docs/features/explorer/) | A dedicated dashboard groups configurations by status, with the actual errors and warnings behind each. |
| [Tools](/docs/tools/add_tools/) | Declare `analysis_command` and your own tool joins the same comparison. |

## Using it

### From the configuration files and the CLI

What to analyze lives in `odatix_userconfig/analyze_settings.yml`, in the same
form as the synthesis settings files — plus a `tools` list, since analysis is
the one job type that runs several tools at once:

{{< code lang=yaml filename="odatix_userconfig/analyze_settings.yml" >}}
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
$ odatix analyze --tool vivado verilator --flow vivado:runtime
{{< /code >}}

`--flow` follows `--tool`: a bare flow name applies to every selected tool that
has a flow of that name, the others keeping their default flow, while
`tool:flow` targets one of them. Work directories go to `work/analysis/`, and
jobs run through the same daemon as every other job type, so the
[Job Monitor](/docs/sessions/gui_monitor/) shows their progress and logs live, and
`-d/--detach` hands them over without waiting: `odatix results analysis` then gives
their report once they are done.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze -d -S nightly
$ odatix results analysis
{{< /code >}}

Every key is on the
[run settings reference](/docs/reference/run_settings/); every option on the
[commands reference](/docs/commands/).

### From the GUI

`odatix-gui` → **Run jobs** → **RTL analysis** lists the tools that declare an
analysis command, each with its flows: clicking a flow opens the job settings,
where more tools can be ticked (they run their default flow), with the same
settings as the settings file — designs, configurations, parallel jobs,
overwrite — and launches. Results land in the **RTL Analysis** dashboard of
Explorer: the status of every design
with every tool, the kinds of findings (click one to keep the designs it was
reported for), and for each design what needs attention first — category,
message, location, message id and the source excerpt — with its expected
findings folded apart.

## Where to go next

- **Tutorial** — [Analyze the example designs](/tutorials/run_examples/analysis/).
- **Reference** — [Run settings files](/docs/reference/run_settings/) · [Commands](/docs/commands/)
- **Reference** — [`analyze_settings.yml`](/docs/reference/run_settings/), including every status and option in full.
- **Next feature** — [Automated RTL synthesis](/docs/features/rtl_synthesis/), once every configuration elaborates.
