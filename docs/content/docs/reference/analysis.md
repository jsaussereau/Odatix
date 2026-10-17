---
title: "Analysis Definitions"
description: "How the reports of an EDA tool become findings — analysis.yml, its message rules, the shared categories, expected findings — and what an analysis record holds."
weight: 10
---

# Analysis definitions

`odatix analyze` runs a tool on a design and reads what it reported. Every tool
reports in its own words: what those words mean is not written in Odatix, it is
the **analysis definition** of the tool, a file named `analysis.yml` next to its
`tool.yml`. Each message a definition recognizes becomes a **finding**:

| Field | What it says |
|-------|--------------|
| `severity` | `error`, `critical`, `warning` or `info`. |
| `category` | What it is about, in a vocabulary shared by every tool: a missing module is the same finding whether Vivado, Quartus or Verilator reports it. |
| `subject` | The module, signal or file it is about (`sub_missing`, `q`). |
| `file`, `line` | Where, relative to the job directory (`rtl/top.sv:2`). |
| `code` | The message id of the tool (`Synth 8-439`, `MODMISSING`). |
| `count` | How many times it was reported. The bits of a bus are one finding. |
| `detail` | The lines the tool printed under it: usually the source excerpt. |
| `expected`, `reason` | Whether it is normal, and why (see [Expected findings](#expected-findings)). |

{{< toc >}}

## Where definitions come from

The definition of a tool is the merge of several files, lowest precedence
first — the same resolution as [metrics files](/docs/reference/metrics/):

1. `odatix_eda_tools/_common/analysis.yml`, shipped with Odatix: the shared
   [categories](#categories), the language extensions, and the messages of the
   Odatix scripts themselves.
2. The `analysis.yml` of every directory defining the tool. A tool that
   [`extends`](/docs/reference/tools/) another one (DC NXT extends Design
   Compiler) reads its messages alike.
3. `<tools_path>/<tool>/analysis.yml` in your workspace, which needs no
   `tool.yml` next to it: dropping that one file is enough to complete or
   correct the definition of a built-in tool.

A later file adds to an earlier one. In `messages`, `categories`, `codes`,
`severities` and `expected`, an entry of the same name replaces the earlier one
and an entry mapped to nothing (`missing_module:`, YAML null) removes it; the
`ignore` patterns add up.

Odatix ships definitions for Vivado, Quartus, Design Compiler, Genus, Verilator
and LibreLane.

## Keys of `analysis.yml`

| Key | Type | Description |
|-----|------|-------------|
| `extends` | tool name | Read the definition of that tool first, and complete it. LibreLane, which reports the messages of Verilator, says `extends: verilator`. |
| `languages` | list | The languages the tool reads (`verilog`, `systemverilog`, `vhdl`). A design written in another one is reported as **not supported** instead of failing with syntax errors. All of them when absent. |
| `logs` | list of glob patterns | The files messages are read from, relative to the job directory. `log/analysis.log` by default. When none of them exists, the console output of the job (`log/console.log`) is read instead: a tool that could not start (no license) only says why there. |
| `ignore` | list of regular expressions | Lines that are no finding (`"^%Error: Exiting due to"`). |
| `continuation` | regular expression | Lines continuing the previous message, kept as its `detail` (`"^\\s"` for the indented excerpt of Verilator). |
| `severities` | `{word: severity}` | How the tool says each severity, for the rules capturing it (`CRITICAL WARNING: critical`). Compared without case. |
| `codes` | `{code: category}` or `{code: {category, severity, secondary, message}}` | What each message id is about, for the rules capturing a code. Its `message`, if any, replaces the rule's (see below). |
| `messages` | `{name: rule}` | The message rules, see below. |
| `expected` | `{name: conditions}` | Findings of this tool that are normal, see [Expected findings](#expected-findings). |
| `categories` | `{name: category}` | More categories, on top of the shared ones. |
| `language_extensions` | `{language: [extensions]}` | The source extensions of each language (`_common` declares them). |

### Message rules

Every line of the logs is tried against the rules in order; the first one
matching makes a finding. A rule marked `fallback` is tried after every other
one, whatever file declares it.

| Key | Description |
|-----|-------------|
| `pattern` | A regular expression searched in the line. Its named groups fill the finding: `message` (the whole line otherwise), `subject`, `file`, `line`, `code` and `severity`. |
| `message` | The message, written by the rule, the groups it names in braces filled in: `"Latch inferred for '{subject}'"`. For a message read from a table or a list, which says nothing by itself. |
| `severity` | The severity of the finding, unless the pattern captures one (through `severities`) or the `codes` table says otherwise. `error` by default. |
| `category` | Its category, unless the `codes` table says otherwise. `other` by default. |
| `subject` | Regular expressions searched in the message when the pattern captures no subject; the first group of the first one matching. |
| `after` | `{patterns, within}`: what the message says on the `within` lines below it (3 by default). Each pattern fills the groups it captures that the message did not: `subject`, `file` and `line`; a captured `message` completes the message (`Parsing error: Expecting token ';'`). Genus writes every message that way. |
| `heading` | A regular expression: the rule reads the rows of a list under this heading, the pattern being tried on the lines right below it, up to the first one it does not match. |
| `files` | Glob patterns: the rule only reads these logs (`report/checkout.rep`). |
| `secondary` | The message only follows from others (`failed synthesizing module 'top'`, `Unable to resolve reference 'sub'` after a port `sub` lacks): it is left out when a finding at least as severe is there. |
| `fallback` | Try this rule last. |

Most tools need one generic rule and a `codes` table. Vivado, for instance:

{{< code lang=yaml filename="vivado/analysis.yml" >}}
severities:
  ERROR: error
  CRITICAL WARNING: critical
  WARNING: warning

codes:
  "Synth 8-439": missing_module
  "Synth 8-9263": missing_file
  "Synth 8-327": latch
  "Synth 8-6156": {category: elaboration, secondary: true}

messages:
  message:
    pattern: "^(?P<severity>ERROR|CRITICAL WARNING|WARNING): \\[(?P<code>[^\\]]+)\\] (?P<message>.*?)(?: \\[(?P<file>[^\\[\\]]+):(?P<line>\\d+)\\])?\\s*$"
    severity: warning
    subject: ["'([^']+)'"]
{{< /code >}}

A message no code describes is still reported, under `other`: completing a
definition makes findings more precise, it never makes them appear.

Genus prints what a message is about on the lines below it, and lists the
checks of the elaborated design under headings:

{{< code lang=yaml filename="genus/analysis.yml" >}}
codes:
  VLOGPT-650: {category: missing_file, severity: error, message: "Cannot open '{subject}'"}

messages:
  # "Warning : Cannot open file. [VLOGPT-650]"
  # "        : File 'missing_defs.svh' in file 'rtl/top.sv' on line 1, column 27."
  message:
    pattern: "^(?P<severity>Error|Warning)\\s*:\\s*(?P<message>.*?)\\s*\\[(?P<code>[A-Z0-9]+-\\d+)\\]"
    severity: warning
    fallback: true
    after:
      within: 2
      patterns:
        - "in file '(?P<file>[^']+)' on line (?P<line>\\d+)"
        - "^\\s+:\\s*(?:Symbol|File|Entity) '(?P<subject>[^']+)'"

  # "design 'top' has the following unloaded port(s)", then "port:top/clk"
  unloaded_port:
    heading: "has the following unloaded port"
    pattern: "^port:(?:\\S+/)?(?P<subject>[^/\\s]+)\\s*$"
    message: "Input '{subject}' is never read"
    severity: warning
    category: unused
    files: ["report/checkout.rep"]
{{< /code >}}

Whatever the tool, the bits of a bus are one finding, which says them:
`Input 'd[15:8]' is never read`, reported eight times.

### Categories

The order of the categories is their relevance: the summary of a design is its
first finding, by severity and then by category.

| Category | Scope | Meaning |
|----------|-------|---------|
| `tool_setup` | tool | The tool could not be set up or run: license, installation, technology files, script error. |
| `missing_file` | design | A source or include file cannot be found. |
| `missing_top` | design | The top level module is not in the sources. |
| `syntax` | design | The source cannot be parsed. |
| `missing_module` | design | A module is instantiated but defined nowhere: it would be an empty black box. |
| `undeclared` | design | A signal, variable or parameter is used without being declared. |
| `port_mismatch` | design | An instance connects a port its module does not have, or leaves one unconnected. |
| `type_mismatch` | design | A value is used where an incompatible type is expected. |
| `multiple_drivers` | design | A signal is driven from several places. |
| `combinational_loop` | design | A combinational path loops back on itself. |
| `latch` | design | A combinational block does not assign a signal on every path. |
| `width_mismatch` | design | A value is truncated or extended. |
| `undriven` | design | A signal or output is read but never assigned. |
| `unused` | design | A signal or input is never read. |
| `constant` | design | Logic found constant, or removed. |
| `elaboration` | design | The design could not be elaborated, without a more precise reason. |
| `style` | design | A coding style remark, without effect on the hardware. |
| `other` | design | Anything else. |

The **scope** decides the status: a design whose errors are all about the tool
is a *tool failure*, not a broken design. A missing module that is the top level
of the design is reported as `missing_top`, whatever tool reports it.

## Expected findings

Some findings are normal: Quartus advises the Reset Release IP for every Agilex
design, a combinational design leaves its clock unused. An **expected** finding
is still reported, apart from the others, but it does not count: a design whose
findings are all expected *passes*, so what remains is what deserves attention.

Expected findings are declared in two places:

- in the definition of a tool, for what that tool says of every design;
- in the `expected` section of
  [`analyze_settings.yml`](/docs/reference/run_settings/#expected--analysis-only),
  for what is normal for your designs.

Each one is a set of conditions, all of which must hold, and a reason:

| Condition | Matches |
|-----------|---------|
| `category`, `severity`, `code` | Equal to the finding's. |
| `subject`, `file` | Shell patterns (`dbg_*`, `rtl/legacy/*`). |
| `message` | A regular expression searched in the message. |
| `tools` | Shell patterns, one of which the tool must match. |
| `architectures` | Shell patterns, one of which the design (`Arch/config`) or its architecture must match. |
| `reason` | Why it is normal: shown with it. |

{{< code lang=yaml filename="odatix_userconfig/analyze_settings.yml" >}}
expected:
  debug_bus:
    category: unused
    subject: dbg_*
    reason: "Debug bus, only connected in the lab build"
  rom_latch:
    category: latch
    architectures: [Legacy_ROM]
    tools: [vivado, quartus]
    reason: "The legacy ROM uses a latch on purpose"
{{< /code >}}

## Statuses

| Status | Meaning |
|--------|---------|
| `failed` | The tool found errors in the design. |
| `tool_failure` | The tool could not analyze the design: its errors are about the tool. |
| `incomplete` | The analysis did not finish (stopped, or the tool died): its verdict cannot be trusted. |
| `warning` | Analyzed, with warnings or critical warnings that are not expected. |
| `unsupported` | Written in a language the tool does not read. |
| `passed` | Analyzed, and nothing but expected findings. |

## Analysis records

Each result is one record of `results/results_analysis_<tool>.yml`, written as
soon as its job ends, whether the tool succeeded or not: an analysis that found
errors is a result too. It is what the
[Explorer](/docs/features/explorer/) RTL Analysis page and `odatix results analysis`
read.

{{< code lang=yaml filename="results/results_analysis_verilator.yml" >}}
- meta:
    type: analysis
    tool: verilator
    architecture: Example_Counter_sv
    configuration: 08bits
    _status: failed
    _summary: "Cannot find file containing module: 'sub_missing'"
    _findings:
      - severity: error
        category: missing_module
        message: "Cannot find file containing module: 'sub_missing'"
        subject: sub_missing
        file: rtl/top.sv
        line: 2
        code: MODMISSING
        detail: ["    2 |   sub_missing u_sub (.clk(clk), .d(d), .q(q));"]
    _languages: [systemverilog]
    _logs: [/.../log/analysis.log]
  metrics:
    error_count: 1
    critical_warning_count: 0
    warning_count: 0
    info_count: 0
    expected_count: 0
{{< /code >}}

The keys starting with `_` are informational: neither chart dimensions nor part
of the record identity, so analyzing a design again replaces its record. A
result keeps its 100 most relevant findings (`_findings_omitted` counts the
others); the metrics count every occurrence, the expected ones apart.
