# Odatix workspace: notes for AI agents

This directory is an [Odatix](https://odatix.readthedocs.io/en/latest/)
workspace. Odatix runs analysis, synthesis, Fmax search, place & route and
simulation jobs on every configuration of parametrizable digital designs, in
parallel, and gathers their metrics in result files.

Full guide for agents: https://odatix.readthedocs.io/en/latest/docs/ai_agents/
Documentation as Markdown: https://odatix.readthedocs.io/en/latest/llms.txt
(one file per category), or one page alone: see "Other tasks" below.

## Layout

- `odatix.yml`: workspace settings. `default_tool` is the tool used when a
  command has no `-t`: set it to a tool that is installed, or always pass `-t`.
- `odatix_userconfig/architectures/<Arch>/_settings.yml`: one design (RTL path,
  top level, clock, reset, Fmax search bounds). Each subdirectory
  `<Arch>/<domain>/` is a parameter domain: one parameter swept in the sources.
- `odatix_userconfig/targets/target_<tool>.yml`: the FPGA parts / ASIC
  technologies of each EDA tool (only the enabled ones are run).
- `odatix_userconfig/<command>_settings.yml`: what each command runs by default
  (`fmax_settings.yml`, `synth_settings.yml`, `analyze_settings.yml`...).
- `odatix_userconfig/derived_metrics.yml`: metrics computed from others (below;
  absent until one is declared).
- `work/`: one directory per job, with its `log/` and `report/`. Never edit.
- `results/`: result files (YAML), read by `odatix-explorer`. Never edit.

## Describe a design: use the Python API

Prefer `odatix.workspace` to writing YAML by hand: it validates names and
settings, and finds the top level, clock, reset and parameters for you.

```python
from odatix.workspace import Workspace, FrequencyBounds

ws = Workspace.open()
arch = ws.architectures.create("Counter")          # an existing one: ws.architectures["Counter"]
arch.settings.rtl_path = "examples/counter_sv"    # relative to the workspace
print(arch.detect_sources())       # candidates for top level, clock and reset
arch.fill_from_sources()           # take the best ones (kept if already set)
arch.settings.fmax_synthesis = FrequencyBounds(lower_bound=50, upper_bound=800)  # MHz, optional
arch.save()

for p in arch.detect_parameters():                 # most relevant first
    print(p.name, p.value, p.kind, p.relevance)
arch.domains.create_from_parameter("BITS", [8, 16, 32])
arch.domains.create_from_parameter("DEPTH", [2, 4])
```

- Set `rtl_path` first, to the directory holding the sources (never `.`):
  `top_level_file` and the files named by the domains are relative to it.
  Keep testbenches in another directory (`tb/`): every file of `rtl_path` is
  copied into each job, and a synthesis tool may read them all.
- Sweep the parameters with a high `relevance`; those computed from other
  parameters (localparam, constants) rank low and should not be swept.
- Parameters declared in another file than the top level (a SystemVerilog
  package, a VHDL package, a header): pass `file="<name>"`, relative to the
  RTL path, to both `detect_parameters()` and `create_from_parameter()`.
- An Fmax is measured on register-to-register paths: a configuration without
  any gets none, and fails. Registers on the inputs only, or on the output
  only (inputs through logic to the output register), are not such a path.
- Check that the I/Os of the widest configuration fit the target part (its
  pin count is in `targets/target_<tool>.yml`).
- The reset polarity (`reset_active_low`) is guessed from the name of the
  reset when left empty: `rst_n`, `areset_n`, `nreset`... active low; `rst`,
  `reset`, `sync_rst`... active high. Set it when the sources say otherwise.
- The Fmax search is a binary search between the bounds of `fmax_synthesis`
  (1 to 1000 MHz without them): about 10 syntheses per configuration, so
  minutes to hours. Run one configuration first, then set the bounds around
  what it gave. A design faster than the upper bound gets no Fmax: its job
  fails with "No timing violated! Try raising the upper bound".
- `use_parameters: No` in the architecture's own `_settings.yml` is expected:
  it concerns its main domain only. Each domain created from a parameter
  has `use_parameters: Yes` and its delimiters in `<Arch>/<domain>/_settings.yml`.
- Settings are written to disk by `save()` only: call it before another
  script (or an `odatix` command) reads the architecture.

## Run, then read the results

```sh
odatix analyze -t verilator -a "Counter + BITS/* + DEPTH/*" -y -E   # fast RTL check first
odatix fmax    -t yosys_fpga -a "Counter + BITS/* + DEPTH/*" -y -E   # Fmax search
odatix synth   -t design_compiler -a "Counter + BITS/16" --at 50 --at 100 -y -E   # at 50 and 100 MHz
```

- `-y` never asks for confirmation, `-E` waits for the jobs and exits: both
  are needed without a human at the terminal. A run of more than a few
  minutes (an Fmax search, an ASIC synthesis) is best started in the
  background of your shell (`... -y -E > run.log 2>&1 &`), then read.
- `"Counter + BITS/* + DEPTH/*"` selects every combination of the values of
  both domains (6 configurations here); `"Counter + BITS/16"` a single value.
  Each configuration is named `Counter+BITS_16+DEPTH_4` (job directories,
  result files); the console shows it as `Counter [BITS:16, DEPTH:4]`.
- RTL analysis tools (`-t`): `verilator`, `icarus`, `yosys` (Verilog and
  SystemVerilog), `ghdl` (VHDL); `vivado`, `quartus`, `questa`, `genus`,
  `design_compiler` when installed (both languages).
- A job whose work directory exists is skipped: add `-o` to run it again.
- Results land in `results/results_<tool>.yml` (analysis: `results/analysis/<tool>.yml`):
  a mapping whose `results` key is the list of records (`units` gives the
  unit of each metric), each with `meta` (`type`: `fmax_synthesis`,
  `custom_freq_synthesis` at a fixed `frequency`..., `architecture`, `configuration`:
  `Counter+BITS_16+DEPTH_4`, `target`, `flow`, one key per domain: `BITS: '16'`)
  and `metrics` (`Fmax` in MHz, `LUT_count`, `Reg_count`, `DSP_count`,
  `BRAM_count`, `IO_count` on an FPGA; `Cell_Area`, `Total_Power`,
  `Worst_Slack` on an ASIC... the `units` of the file list every one a tool
  gave). Simulation and workflow records
  (`results_simulation.yml`, `results_workflow.yml`) name only the base
  configuration in `configuration`: read the domain keys.
- A synthesis at a fixed frequency succeeds even when it misses timing: a
  negative `Worst_Slack` (ns) says so.
- Check a new metric against the report it is read from once: a value
  extracted from the wrong line looks just as plausible.
- To compare on a ratio, declare it once as a derived metric, then run
  `odatix results derived`: it is added to every record, and shown by
  `odatix-explorer` like any other metric.

  ```python
  ws.derived_metrics.set("Fmax_per_LUT", {"type": "operation", "op": "Fmax / LUT_count", "unit": "MHz/LUT"})
  ws.derived_metrics.set("LUT_per_tap", {"type": "operation", "op": "LUT_count / meta.TAPS"})  # a domain value
  ws.derived_metrics.save()          # odatix_userconfig/derived_metrics.yml
  ```

  A derived metric applies to synthesis records unless it says otherwise:
  add `"apply_to": "workflow"` (or `simulation`, `any`) for the others.
- `odatix results synth|sim|analysis|workflow` rewrites the result files from
  `work/` without running anything again.
- With `-E`, the command ends by listing each failed job and its log
  directory (`work/<...>/<job>/log/`); `log/status.log` only says how far a
  job went, not whether it failed. An internal error of Odatix:
  `odatix_error.log` in the directory it was run from.

EDA tools and their licences are not part of Odatix: check that the tool runs
in this shell before blaming the workspace. Start with small runs (one target,
a few values per domain): a full sweep can hold the machine for hours.

## Other tasks

What each task needs to know, then the page with every detail: Markdown at
https://odatix.readthedocs.io/en/latest/<page>index.md. Read that page only.
In the YAML files below, quote regular expressions with single quotes (`'\s'`
is an invalid escape between double quotes).

**Simulate with a template** (`verilator`, `icarus`, `ghdl`, `questa`, `xsim`):
the testbench belongs to the architecture, its files relative to the workspace,
its parameters taking the domain values:
`arch.update(testbench={"top": "tb_x", "files": ["tb/tb_x.sv"], "parameters": {"WIDTH": "${WIDTH}"}})`,
then `odatix sim -s verilator -a "Arch + WIDTH/*" -y -E` (`-s` names a
template, or a simulation of the workspace). A simulation fails
when the testbench prints an error (`$error`, `$fatal`, VHDL `assert ...
severity error`), not on a `$display("FAIL")`: capture such a verdict as a
metric. For metrics of the testbench, `s = ws.simulations.create("TB_x",
template="verilator")`, then `s.metrics.set(...)` and `s.metrics.save()` as for
a tool (below): a `yaml` metric reading a `results.yml` the testbench writes,
or a `regex` on `log/simulation.log` (Verilator; `log/vvp.log` for Icarus),
such as `'errors=([0-9]+)'`; run it with `-s TB_x`. Results:
`results/results_simulation.yml`, with `sim_status`, `sim_errors` and
`sim_warnings` (what the simulator printed) added by the template. Page:
`docs/features/simulation/`, every key: `docs/reference/simulation/`.

**Simulate with your own script**: `odatix_userconfig/simulations/<sim>/` with
the testbench files, `_settings.yml` (`tasks:` list of `{name, commands,
dependencies}`; placeholders `${vhdl_files}`, `${sv_files}`, `${tb_files}`,
`${<domain>}` for the value of each domain, for the generics of the
testbench: `ghdl -r --std=08 tb_x -gWIDTH=${WIDTH}`; the copied RTL already
holds the values) and `_metrics.yml`; `odatix sim -s <sim> -a "Arch + D/*" -y -E`
(no need to list it in `sim_settings.yml`). The tasks run in the job's work
directory, which the `file` of a metric is relative to; what they print is
kept in its `log/console.log`.
Page: `docs/features/simulation/`.

**Workflow** (any commands over a design space, no RTL needed):
`odatix_userconfig/workflows/<wf>/_settings.yml` with `sources: {path: <dir,
relative to the workspace>}`, `variables:` (e.g. `taps: {type: list,
settings: {list: [4, 8]}}`, each one a domain) and `tasks:` whose commands use
`${taps}` and `"${python}"`; `_metrics.yml` beside it. No `use_parameters`
nor delimiters are needed: nothing is replaced in the sources.
`odatix workflow -W <wf> -y -E` runs every combination (`-W "wf + taps/4"`
one value); results in `results/results_workflow.yml`, the value of each
variable in `meta.<variable>` (a string). The files a metric reads are relative to the
job's work directory, where the sources are copied and the tasks run. Page: `docs/features/workflows/`.

**ASIC synthesis, then place & route**: the technologies a tool runs on are
the `targets` list of `odatix_userconfig/targets/target_<tool>.yml` (each one
enabled there is run; `--target <name>` picks one). `odatix synth -t design_compiler -a ... --at 50 --until netlist -y -E`
writes the netlist that `odatix pnr -t innovus --from-tool design_compiler -y -E`
places and routes (a Genus synthesis too). `odatix pnr` has no `-a`: it takes
every completed synthesis the `sources` of `pnr_settings.yml` select
(`custom_freq_synthesis/<tool>/<target>/<arch>/<configuration>@<MHz>MHz`,
wildcards allowed: `custom_freq_synthesis/design_compiler/*/FIR/FIR+TAPS_4@20MHz`
for one; the configuration is the name of the job directory, listed by
`ls work/custom_freq_synthesis/<tool>/<target>/<arch>/`), narrowed by `--from-tool`, `--from-type`, `--target`
(no option picks a frequency: the `@<MHz>MHz` of `sources` does); `-t` names the
place & route tool, whose results go to `results/results_<tool>.yml`. A
place & route job takes minutes, even for a small design: run it in the
background. Each flow (`-f`) has its own work directory, so two flows run
side by side. The
metrics of the synthesis record are those before place & route. Results: `Cell_Area` (µm²),
`Total_Power` (mW), `Worst_Slack` (ns). Page: `docs/features/pnr/`.

**Design space exploration**: a campaign
`odatix_userconfig/dse_campaigns/<name>.yml` (copy `campaign_template.yml`,
every key commented): `run`, `tool`, `objectives` (`{metric: Fmax, goal: max}`
with `run: fmax_synthesis`, `frequency` with `custom_freq_synthesis`; a domain
value through a derived metric, `{"type": "operation", "op": "meta.LANES"}`,
whose name is then the objective's `metric`; `constraints: []` for none),
`search: {strategy: genetic, budget: <evaluations>}`; replace the template's
`tool`, `objectives` and `constraints` (made for a fixed-frequency Vivado
run). Check it with `odatix dse -p <name> -C`: it counts the designs left, and
when they fit in the budget, `strategy: exhaustive` gives the exact front. Run
it with `odatix dse -p <name> -j 4 -y -E` (no need to list it in
`dse_settings.yml`); the front
is in `results/dse/<name>.yml`. A design that fails still spends budget:
run one configuration with `odatix fmax` (or `synth`) first, look at the
extreme values of each domain (no register-to-register path,
more I/Os than the part), and exclude what cannot work in the architecture's
`_settings.yml`: `exclusions: [{when: "$REGISTER_LEVELS == '0'", kind: illegal}]`
(a domain compares as the name of its configuration, a string: a rule that
never holds leaves nothing out, silently, so check that `odatix dse -C` counts
fewer designs; `docs/configurations/exclusions/`). Do it before the first run:
the archive keeps the budget spent (`-o` starts over). Pages:
`docs/features/dse/`, every key: `docs/reference/dse/`.

**Add a metric to a tool**, built-in or not: an overlay holding only the new
metrics, then `odatix results` re-exports without running anything:

```python
m = ws.tools["yosys_fpga"].metrics
m.set("Carry_LUTs", {"type": "regex", "settings": {"file": "log/nextpnr.log", "pattern": 'carry LUTs: *([0-9]+)', "group_id": 1}})
m.save()                            # odatix_userconfig/tools/yosys_fpga/metrics.yml
```

The `file` of a metric is relative to the job's work directory, whose `log/`
and `report/` hold what can be read (types `regex`, `json`, `yaml`, `csv`,
`xml`, `operation`). A `regex` takes the first match in the file (`^` and `$`
match at each line): a report listing several modules is best summed up by
the tool's script first. Pages: `docs/results/metrics/`,
`docs/reference/metrics/`.

**Add a flow** (a strategy of a tool), e.g.
`flows: {retime: {parameters: {synth_options: [-retime]}}}` in
`odatix_userconfig/tools/yosys_fpga/tool.yml` (an overlay of the built-in
tool), then `-f retime`; records tell flows apart by `meta.flow`, and the
`scripts/` of a job show what the flow passed to the tool. A flow keeps every
parameter of the default flow it does not set (Innovus at 50 % utilization:
`flows: {util50: {parameters: {utilization: 0.5}}}`, then `odatix pnr -f util50`;
its other parameters: `aspect_ratio`, `core_margin`, `flow_effort`,
`power_effort`, `fix_hold`, `<step>_options`). The parameters of any
tool, with their default values: `ws.tools["<tool>"].settings.flow("standard").parameters`. Page:
`docs/tools/add_flows/`.

**Add a tool**: `odatix_userconfig/tools/<tool>/tool.yml` (one command per job
type, e.g. `custom_freq_synthesis_command`; `$top_level_file` and
`$top_level_module` name the design: the job's `rtl/` also holds the
testbenches of the RTL directory), its `metrics.yml`, and
`odatix_userconfig/targets/target_<tool>.yml` with at least one target
(`targets: [generic]`: the names are free labels, given to the scripts). Page:
`docs/tools/add_tools/`.

**Exclude combinations**, **every command and option**:
`docs/configurations/exclusions/`, `docs/commands/` (or `odatix <command> -h`).
