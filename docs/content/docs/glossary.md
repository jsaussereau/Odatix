---
title: "Glossary"
description: "The words of Odatix: one concept, one word, everywhere — in the CLI, the GUI, the documentation and the settings files."
weight: 1
---

# Glossary

Odatix uses **one word per concept**, the same in the command line, the
graphical interface, this documentation, the settings files and the messages.
Where a standard EDA term exists, it is the one used. The table also says which
words are avoided, so that a page that seems to say something else is not
misread.

{{< toc >}}

## Terms

| Term | Definition | Not to be confused with |
|------|------------|-------------------------|
| <a id="architecture"></a>**Architecture** | A parametrizable RTL design, with its sources and its settings (`_settings.yml`). | "Design" alone, which is a [design point](#design-point) when something is measured. |
| <a id="configuration"></a>**Configuration** | One set of parameter values of an architecture. | A settings file. |
| <a id="parameter-domain"></a>**Parameter domain** | A set of parameters that vary together, and combine with the other domains of the architecture. The word of the `param_domains:` key and of the `${domain}` placeholder. | |
| <a id="design-point"></a>**Design point** | An architecture, with a configuration, a target and a frequency: the unit that is measured. | "Design" for a design point: an exploration evaluates design points. `design_path` and "design files" keep their meaning: the sources of an architecture. |
| <a id="target"></a>**Target** | The FPGA device or ASIC technology a design point is implemented on. Listed in the target file of each tool (`target_<tool>.yml`). | "Device" or "part", except inside the settings of a tool. |
| <a id="tool"></a>**Tool** | An EDA tool: Vivado, Yosys, Design Compiler... Each has a directory with its `tool.yml`. | |
| <a id="tool-flow"></a>**Tool flow** / **step** | The sequence of steps a tool runs (synthesis, place, route, bitstream...). A tool can have several flows to compare. | A [workflow](#workflow). "Flow" alone is avoided in the interface. |
| <a id="workflow"></a>**Workflow** | A chain of tasks defined by the user and run by Odatix: any command-line step becomes a task. | A [tool flow](#tool-flow). A *task* is a step of a workflow. |
| <a id="fmax-synthesis"></a>**Fmax synthesis** | The search for the maximum frequency a design point reaches (`odatix fmax`). | |
| <a id="fixed-frequency-synthesis"></a>**Fixed-frequency synthesis** | A synthesis at frequencies chosen by the user (`odatix synth`), whose frequencies an architecture gives in its `fixed_freq_synthesis` block. | "Custom frequency synthesis": its block was called `custom_freq_synthesis`, a name still read for one version. The job type keeps the name `custom_freq_synthesis` in work directories and result files. |
| <a id="run"></a>**Run** | A command started by the user, from the command line or the GUI, which produces jobs. | A [job](#job). |
| <a id="job"></a>**Job** | The execution of one design point by one tool. | A *task*, which is a step of a workflow. |
| <a id="session"></a>**Session** | A named group of jobs, followed in the monitor. | |
| <a id="daemon"></a>**Daemon** | The process that owns the sessions and runs their jobs (`odatix monitor`, `odatix stop`). | "Background mode". |
| <a id="detached"></a>**Detached** | The mode where a run hands its jobs over to the daemon and returns (`-d/--detach`). | "Background", "daemon mode". |
| <a id="campaign"></a>**Campaign** | A design space exploration: a space, objectives, a search strategy and a budget, in a file of `dse_campaigns/`. | "Exploration", for a campaign. |
| <a id="results"></a>**Results** | The measurements exported in `results_*.yml`, read by Odatix Explorer. | "Benchmark": benchmark scores are simulation metrics. |

## Conventions

- YAML keys are in `snake_case`, command-line options in `--kebab-case`.
- A settings file is named after the command that reads it:
  `<command>_settings.yml`, and the key of `odatix.yml` that points to it is
  `<command>_settings_file`.
- The first use of a term of this glossary on a page links to its definition.

## See also

- [Getting started](/docs/getting-started/): the same concepts, in the order
  a first run meets them.
- [Commands](/docs/commands/): what each command does.
