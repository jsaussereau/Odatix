---
title: "Use Odatix with AI agents"
description: "Let an AI coding agent describe your designs, run Odatix and read its results: the files it reads, the Python API it uses, and the commands it runs without a terminal."
weight: 21
tags: ["ai", "agents", "llm", "python api", "automation"]
---

# Use Odatix with AI agents

> [!IMPORTANT] Requires Odatix 4.0+

An AI coding agent (Claude Code, Codex, Cursor, Copilot...) can drive Odatix
from start to finish: describe your designs, choose the parameters to sweep,
run the jobs and read the results. Everything Odatix does is reachable without
the graphical interface, and its guesses about your sources (top level,
clock, reset, parameters) are available from Python, so an agent does not
have to read the whole RTL to get them right.

## Designed to spare tokens and context

Odatix is built so that an agent spends its tokens on your design, not on
finding out how the tool works:

- **One short guide in the workspace.** `AGENTS.md` (about 2,000 words)
  holds what an agent needs to describe a design, run it and read the results.
  For anything else, it names the one page to read, published as Markdown:
  an agent fetches only the part it is missing.
- **Guesses instead of reading.** The top level, the clock, the reset and the
  parameters worth sweeping come from one call, ranked, instead of from the
  agent reading every source file into its context.
- **A typed API instead of YAML by hand.** Settings are checked when they are
  set, and written with the layout and comments of the file kept: no trial
  and error on the syntax of a configuration file.
- **Quiet, unattended commands.** `-y -E` runs without questions and without
  the job monitor, and ends with one summary line, plus the name and log
  directory of each failed job: the agent reads what went wrong, not pages of
  progress.
- **Structured results.** One YAML file per tool, one record per job, with its
  units: no report of an EDA tool to parse.

## What an agent reads

| Where | What it holds |
|---|---|
| `AGENTS.md`, at the root of the workspace | Written by `odatix init`; when the project already has one, the Odatix notes are added at its end, once. The layout of the workspace, the Python API to describe a design, and how to run without a terminal. Coding agents read it on their own. |
| [`/llms.txt`](/llms.txt) | What Odatix is, and the list of the categories of the documentation, for agents that look for it at the root of the site. |
| `/<category>/llms.txt` | Every page of one category as Markdown, in one text file: [`/docs/reference/llms.txt`](/docs/reference/llms.txt) for the configuration files, [`/docs/python_api/llms.txt`](/docs/python_api/llms.txt) for the Python API... An agent reads only the ones it needs. |
| `<page>/index.md` | One page alone, as Markdown: the URL of any page of this site followed by `index.md`, such as [`/docs/features/simulation/index.md`](/docs/features/simulation/index.md). `AGENTS.md` names the page of each task, so that an agent reads that one only. |
| This page | The recommended way to work, below. |

To start, open your workspace with your agent and ask it, for instance:

> Read AGENTS.md. Add the design in `rtl/fir/` as an architecture named `FIR`,
> sweep its main parameters, check that every configuration elaborates with
> Verilator, then find the Fmax of each one with Vivado and tell me which one
> has the best Fmax per LUT.

## Describe a design

Use the [`odatix.workspace`](/docs/python_api/workspace/) API rather than
writing YAML by hand: it checks names and settings, keeps comments and layout,
and gives the same guesses as the *auto detect* buttons of the
[graphical interface](/docs/gui/).

{{< code lang=python filename="add_design.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()
arch = ws.architectures.create("Counter")
arch.settings.rtl_path = "examples/counter_sv"   # relative to the workspace

found = arch.detect_sources()   # candidates for top level, clock and reset, best first
print(found.to_dict())
arch.fill_from_sources()        # take the best ones; settings already set are kept
arch.save()

for param in arch.detect_parameters():           # most relevant first
    print(param.name, param.value, param.kind, param.relevance)

# One parameter domain per parameter to sweep
arch.domains.create_from_parameter("BITS", [8, 16, 32])
{{< /code >}}

- `detect_sources()` reads Verilog, SystemVerilog and VHDL. Each guess is a
  list of candidates (`value`, `score`, `detail`, `file`), so the agent can
  check them against the sources, or ask you, when the first is not clearly
  ahead.
- `detect_parameters()` also reads C/C++ (HLS), Scala (Chisel), Python and
  configuration files. `relevance` (0 to 10) ranks what a design expects to be
  set from outside, with a plain value, above what is derived or local.
- `create_from_parameter()` finds delimiters that isolate the value of the
  parameter in its file, and creates a domain whose configurations are the
  values given. When no delimiters isolate it, it raises: set
  `start_delimiter` and `stop_delimiter` of the domain by hand.

The functions behind these methods (`detect_sources`, `detect_parameters`,
`parameter_domain_settings`) work on any directory or file, outside any
architecture. See the [API reference](/docs/python_api/workspace/#what-the-sources-say).

## Run without a terminal

An agent has no one at the keyboard, and often no terminal able to show the
job monitor:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix analyze -t verilator -a "Counter + BITS/*" -y -E
$ odatix fmax -t vivado -a "Counter + BITS/*" -y -E
{{< /code >}}

- `-y` never asks for confirmation; `-E` waits for the jobs, prints how many
  succeeded and failed, and exits. Without a terminal that can show it, the
  monitor is skipped.
- `"Counter + BITS/*"` selects every configuration of the domain `BITS`, and
  `"Counter + BITS/* + DEPTH/*"` every combination of two domains (see
  [Commands](/docs/commands/)).
- Pass `-t` unless `default_tool` in `odatix.yml` names a tool that is
  installed. For the RTL check of VHDL, use `ghdl` rather than `verilator`.
- Start with `odatix analyze`: it elaborates every configuration in seconds and
  catches errors before a long synthesis.
- A job whose work directory exists is skipped: `-o` runs it again.
- With `-E`, the command ends by listing each failed job and its log directory.
  The `log/status.log` file of a job only says how far it went.
- An Fmax search is a binary search: about ten syntheses per configuration
  between the default bounds (1 to 1000 MHz). Run one configuration first, then
  set `fmax_synthesis` around what it gave. A design faster than the upper
  bound gets no Fmax: its job fails, and asks for a higher bound.
- From Python, [`odatix.run`](/docs/python_api/run/) does the same, and its
  `Run.check()` says what a run would do without running anything.

## Read the results

Results are YAML files under `results/` (see the [format](/docs/results/format/)),
one record per job, which an agent reads directly: `results/results_<tool>.yml`
holds the list of records under its `results` key, each with its `meta`
(architecture, `configuration` such as `Counter+BITS_16`, target, the value of
each domain) and its `metrics` (`Fmax`, `LUT_count`...), and their `units`.
To show them to you, `odatix-explorer` opens them in the browser.

To compare configurations on a ratio, declare it once as a
[derived metric](/docs/results/derived_metrics/) rather than computing it in a
script: it is then added to every record, and plotted by Explorer like any
other metric.

{{< code lang=python filename="add_metric.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()
ws.derived_metrics.set("Fmax_per_LUT", {"type": "operation", "op": "Fmax / LUT_count", "unit": "MHz/LUT"})
ws.derived_metrics.save()   # odatix_userconfig/derived_metrics.yml
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix results derived
{{< /code >}}

When a job fails, its log is in `work/<...>/<job>/log/`. When Odatix itself
crashes, the details are in `odatix_error.log`, in the directory it was run
from.

## Good practice

- Let the agent work in a workspace under version control, so you can review
  what it changed in `odatix_userconfig/`.
- `work/` and `results/` are written by Odatix: they are read, never edited.
- EDA tools and their licences are not part of Odatix. Before letting an agent
  look for a bug in the workspace, check that the tool runs in its shell.
- Ask for small runs first (one target, a few configurations): a full sweep can
  hold the machine and the licences for hours.
