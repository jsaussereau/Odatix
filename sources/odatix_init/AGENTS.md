# Odatix workspace: notes for AI agents

This directory is an [Odatix](https://odatix.readthedocs.io/en/latest/)
workspace. Odatix runs analysis, synthesis, Fmax search, place & route and
simulation jobs on every configuration of parametrizable digital designs, in
parallel, and gathers their metrics in result files.

Full guide for agents: https://odatix.readthedocs.io/en/latest/docs/ai_agents/
Documentation as Markdown, one file per category: https://odatix.readthedocs.io/en/latest/llms.txt

## Layout

- `odatix.yml`: workspace settings (paths, `default_tool`, resource limits).
- `odatix_userconfig/architectures/<Arch>/_settings.yml`: one design (RTL path,
  top level, clock, reset). Each subdirectory `<Arch>/<domain>/` is a
  parameter domain: a parameter swept in the sources.
- `odatix_userconfig/targets/target_<tool>.yml`: the FPGA parts / ASIC
  technologies of each EDA tool.
- `odatix_userconfig/<command>_settings.yml`: what each command runs by default
  (`fmax_settings.yml`, `synth_settings.yml`, `analyze_settings.yml`...).
- `work/`: one directory per job, with its `log/` and `report/`. Never edit.
- `results/`: result files (YAML), read by `odatix-explorer`. Never edit.

## Describe a design: use the Python API

Prefer `odatix.workspace` to writing YAML by hand: it validates names and
settings, and finds the top level, clock, reset and parameters for you.

```python
from odatix.workspace import Workspace

ws = Workspace.open()
arch = ws.architectures.create("Counter")
arch.settings.rtl_path = "examples/counter_sv"    # relative to the workspace
print(arch.detect_sources())       # candidates for top level, clock and reset
arch.fill_from_sources()           # take the best ones (kept if already set)
arch.save()

for p in arch.detect_parameters():                 # most relevant first
    print(p.name, p.value, p.kind, p.relevance)
arch.domains.create_from_parameter("BITS", [8, 16, 32])
```

## Run, then read the results

```sh
odatix analyze -t verilator -a "Counter + BITS/*" -y -E   # fast RTL check first
odatix fmax    -t vivado    -a "Counter + BITS/*" -y -E
```

- `-y` never asks for confirmation, `-E` waits for the jobs and exits: both
  are needed without a human at the terminal.
- `"Counter + BITS/*"` selects every configuration of the domain `BITS`.
- A job whose work directory exists is skipped: add `-o` to run it again.
- `odatix results synth|sim|analysis|workflow` rewrites the result files from
  `work/` without running anything again.
- A failed job: read `work/<...>/<job>/log/`. An internal error of Odatix:
  `odatix_error.log` in the directory it was run from.

EDA tools and their licences are not part of Odatix: check that the tool runs
in this shell before blaming the workspace.
