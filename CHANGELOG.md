# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/).

## [4.0.0] - Unreleased

Odatix 4.0 is a major release. Most 3.7 workspaces keep working: former command names, settings file names and keys are still accepted for a few versions, with a warning saying what to write instead, and `odatix migrate` rewrites a workspace to the new format. Read **Breaking changes** before upgrading.

### Breaking changes

- **Commands** renamed after the new [glossary](https://odatix.readthedocs.io/docs/glossary/): `odatix --init` → `odatix init`, `odatix freq` → `odatix synth`, `odatix res_synth` / `res_benchmark` → `odatix results [synth|sim|workflow|analysis|derived]` (`odatix results` alone exports everything; the dhrystone benchmark export is removed). `-f/--force` (continue on synthesis error) → `--continue-on-error`, `-f` now selecting a flow
- **Settings files** are named after the command that reads them: `fmax_synthesis_settings.yml` → `fmax_settings.yml`, `custom_freq_synthesis_settings.yml` → `synth_settings.yml`, `simulations_settings.yml` → `sim_settings.yml`, `clean.yml` → `clean_settings.yml`. The `custom_freq_synthesis` block of an architecture becomes `fixed_freq_synthesis`. Target files move to `odatix_userconfig/targets/` (still found in `odatix_userconfig/`)
- **Per-target settings of an architecture** (the `xc7a100t-csg324-1:` / `AMS350CMOS:` blocks overriding fmax bounds or frequencies) are replaced by an `overrides` list in `_settings.yml`, each rule selecting jobs by tool, target and configuration. The old blocks are **ignored** and not converted by `odatix migrate`: rewrite them by hand (see the shipped examples)
- **Results files** use a new format (`schema: 2`, one flat record per job and step). 3.7 files are still read and upgraded on the next export. Every tool exports its worst slack as `Slack` (ns)
- **Configuration generation**: `generate_configurations` / `generate_configurations_settings` become `variables` (at the root of `_settings.yml`) and a `configurations` block (`name`, `template`). 3.7 files are still read, and rewritten in the new form when saved from the GUI or by `odatix migrate`
- **Design Compiler** no longer uses a Makefile

### Added

#### EDA tools

- New synthesis and implementation tools: **Cadence Genus**, **Cadence Innovus**, **Synopsys IC Compiler II**, **Design Compiler NXT** (`dc_nxt`), **LibreLane** (open-source RTL to GDSII on sky130, gf180mcu, ihp_sg13g2) and **Quartus Prime Pro** (Agilex). **Verilator** and **Yosys** are available for RTL analysis
- `odatix pnr`: place & route from a completed synthesis, possibly made by another tool (e.g. Design Compiler or Genus, then Innovus or ICC2)
- **Flows**: several strategies per tool, chosen with `-f/--flow`, each with its own work directory (`<tool>@<flow>`) and `parameters` passed to the scripts. Built-in flows for Vivado (`runtime`, `performance`, `area`, `power_opt`), Design Compiler (`high_effort`, `ultra`, ...), Genus and Innovus
- **Steps**: jobs are split into resumable steps (Vivado: `synthesis`, `pnr`, `bitstream`). `-u/--until <step>` stops at a step, a later run resumes from there, `--rerun-from <step>` restarts from one. Metrics are exported per step
- **User-defined tools**: a directory with a `tool.yml` in `odatix_userconfig/tools/` adds a tool or extends a built-in one (`extends`), and a workspace `metrics.yml` adds, overrides or removes metrics
- User constraint files (`.xdc`, `.sdc`, floorplans) declared under `constraints` in a target file or an architecture, per stage (`synthesis`, `pnr`)
- Support for `filelist.f` files
- **Windows**: Verilator, Icarus Verilog and Yosys run RTL analyses natively (no `make` nor shell needed), and Vivado runs its steps and RTL analysis as on Linux. EDA tools and simulators installed in **WSL** run there: Odatix chooses (a tool with Linux commands only, a simulator installed in WSL only), the workspace decides (`wsl`, `wsl_distribution`, `wsl_tools` and `windows_tools` in `odatix.yml`), and a run says where each one runs

#### Design space exploration

- `odatix dse`: search a design space instead of sweeping all of it. A **campaign** (`odatix_userconfig/dse_campaigns/<name>.yml`) sets what an evaluation runs (synthesis, workflow, simulations), the `objectives`, the `constraints` and the budget; the result is the Pareto front. Strategies `exhaustive`, `random`, `genetic` and `bayesian`; tool, flow, target and frequency can be searched too. Explorations resume where they stopped and reuse the results already in the workspace
- Configuration `constraints` (expressions a combination must satisfy) and architecture `exclusions` (cross-domain combinations that are illegal, duplicates or dominated)
- Configurations described by rules are resolved on the fly: `odatix generate` is no longer needed before a run (it still writes them as files, `-C/--clean` removes stale ones). A domain with a single variable needs no `configurations` block, and `configurations` can be a list (union of rule sets)
- `generate_command` accepts `${...}` placeholders: an architecture variable used there becomes a parameter domain (see the new `Example_Counter_Chisel_CLI` and `Example_FIR_hls` examples)

#### Workflows, simulations and metrics

- `odatix workflow`: chain any commands (HLS, scripts, simulators, ...) over a design space and export the metrics they produce (`results_workflow.yml`), with `on_failure_commands`. Several examples are provided (`workflow_*`)
- **Simulation templates** (`ghdl`, `verilator`, `questa`, `xsim`, `icarus`) that simulate any architecture with its `testbench`; a minimal random testbench is generated when there is none
- Simulations accept `tasks`, export metrics (`results_simulation.yml`), can declare `invariant_domains` and list the `architectures` they run on
- **Derived metrics** (`odatix_userconfig/derived_metrics.yml`): metrics imported from another kind of result or computed from an expression, e.g. a runtime from a simulated cycle count and a synthesized frequency
- `odatix analyze`: RTL analysis with one or several tools (Vivado, Verilator, Genus, ...), reporting categorized findings (latches, missing modules, width mismatches, ...) with their location; expected findings can be declared in `analyze_settings.yml`

#### Running jobs

- Runs are **sessions** that keep going in the background: `odatix ps`, `odatix monitor` and `odatix stop` list, reattach and stop them, also on another machine through SSH (`-R user@server`)
- `odatix ls` lists the architectures, simulations and workflows of the workspace (`--arch`, `-s`, `-W` and name patterns to filter, `-a` for their configurations too, `-l` for one name per line)
- `-a/--architecture`, `--target`, `-s/--sim` and `-W/--workflow` choose what to run from the command line; glob patterns (`*/08bits`) are accepted at every level. `default_tool` in `odatix.yml`
- `nb_jobs: auto` (`-j auto`): number of CPUs minus one
- Automatic pause when the machine runs out of CPU or memory, configurable in `odatix.yml`
- `odatix migrate` to upgrade a 3.7 workspace
- Python API: `odatix.workspace` (edit a workspace, keeping the comments and layout of the files), `odatix.run` (start, follow and control runs) and `odatix.dse`

#### Odatix GUI

- New pages: EDA tools and tool editor, Simulation editor, Workflows, Derived metrics, Design space exploration and campaign editor, Monitor, Clean, and runs of every kind (synthesis, place & route, simulation, workflow, RTL analysis)
- Flow and step selection, constraint files, overrides and exclusions in the Architecture Editor; configuration rules are edited directly in the Configuration Editor
- Odatix Explorer is built in (`/explorer`)
- Custom themes can be dropped in `odatix_userconfig/themes/gui/`

#### Odatix Explorer

- Rewritten: live reload while jobs run, several result files on one chart, any dimension against any metric, filters and color/symbol/group by any dimension, CSV export
- New pages: table, parallel coordinates, RTL analysis, and design space exploration (Pareto front and progress, live)
- Metric rules (`LUT_count < 1000 and Fmax > 100`) to filter records, and saved views
- `-p/--port` option, also for Odatix GUI

### Fixed

- Design Compiler: fmax results depending on previous iterations (submodules linked as already compiled at another frequency), source files read twice, errors not caught
- Vivado: `LUT_percent` and `Reg_percent` wrong when the report says `<0.01`
- The reset signal of an architecture is now actually checked, and a missing `design_path` is reported instead of silently copying nothing
- A parameter inserted after a start delimiter ending in a line comment no longer lands inside the comment
- `regex` metrics anchored with `^` / `$` now match at every line
- Settings files are written atomically, so an interrupted run no longer leaves a truncated file; the GUI keeps their comments and unknown keys
- Synthesis jobs run in their own directory (no more `.Xil` or `vivado.jou` at the workspace root)
- Odatix Explorer: IP address retrieval on some systems, records sharing an x value drawn as one point
- `odatix-gui` and `odatix-explorer` crashing or using 100 % CPU when started without a terminal
- Windows: a run losing its session as soon as it started ("No session matches"), configuration names written with `\` (`MyCounter\32bits`, then not found), files read with the encoding of the console instead of UTF-8, simulators installed as batch files (`xelab.bat`) not found or given their arguments split on `=`, and the job files a tool reads (`settings.tcl`, `target.txt`...) written with `\r\n` line endings

## [3.7.3] - 2026-03-23

### Fixed

#### Odatix GUI

- Fix compatibility with dash 4.0

## [3.7.2] - 2025-11-24

### Fixed

#### Odatix GUI

- Fix compatibility with python 3.6

## [3.7.1] - 2025-11-24

### Fixed

#### Odatix GUI

- Fix crash

## [3.7.0] - 2025-11-24

### Added

#### Odatix

- Add new design compiler targets

#### Odatix Explorer

- Add -N alias to --normal_term_mode option

#### Odatix GUI

- Add a basic GUI web app for Odatix : odatix-gui. For now, it only supports the functionnalities listed bellow.
- Add a gui page for architecture handling
- Add a gui page for architecture settings
- Add a gui page for configurations / parameter domain settings
- Add a gui page for configuration generation
- Add a gui page for workspace settings 

### Changed

#### Odatix

- Make all keys from odatix workspace settings optional
- Make fmax bounds and custom frequency list optional
- Remove a note displayed when no main configuration is in use
- Decrease update check timeout 

#### Odatix Explorer

- Change markers of 3D charts
- Automatically display parameter domains when dissociation is activated 
- Make dropdown unclearable

### Fixed

#### Odatix

- Fix compatibility with newer design compiler versions
- Fix unclear error when using an undefined parameter domain
- Fix lib names not including parameter domains configurations
- Fix parameter domains not being exported for openlane et design_compiler
- Fix hex to bin and bin to hex converions not being handled correctly by configuration generator

#### Odatix Explorer

- Fix crash when there are no parameter domains in a result file
- Fix parameter domains not being detected if only custom frequency synthesis results are defined
- Fix forced newline on parameter file generation with 'odatix generate'
- Fix format type for parameter file generation not behaving as espected
- Fix 'SettingWithCopyWarning' 

## [3.6.1] - 2025-03-18

### Changed

#### Odatix Explorer

- Change default marker size for 3D charts

### Fixed

#### Odatix Explorer

- Fix crash with python versions prior to 3.12 
- Fix internal error in scatter 3D charts with triangle-up markers (not supported by plotly 3D charts)
- Fix internal error when symbol mode is set on domain values

## [3.6.0] - 2025-03-17

### Added

#### Odatix Explorer
- Add support for parameter domains filters and colors
- Add single radar charts
- Add scatter 3D charts
- Add multiple layouts and chart types to overview

### Changed

#### Odatix
- Change parameter domains organization. Combinaisons are now considered as configurations instead of architectures

### Fixed

#### Odatix Explorer

- Fix metrics not appearing in the same order as in the source yaml
- Fix modebar not being affected by themes

## [3.5.1] - 2025-03-03

### Fixed

- Fix wildcard not working without parameter domains
- Fix parameter domains only being applied on the first target
- Fix parameter domains wildcard not working without main domain wildcard

## [3.5.0] - 2025-03-02

### Added

- Add support for parameter domain wildcard
- Add ' ' keybinding to pause a job
- Add bool type for configuration generation 
- Add format type for configuration generation 
- Add conversion (bin/dec/hex) type for configuration generation 
- Add support for multi-line definition for configuration generation templates

### Fixed

- Fix help menu close button not working
- Fix invalid types for configuration generation not being detected 

## [3.4.0] - 2025-02-26

### Added

#### Odatix
- Add support for parameter domains
- Add support for configurations automatically defined by rules
- Add custom frequency synthesis support for design compiler
- Add a message after the motd if an update is available
- Add a help menu in the monitor
- Add the elapsed time for each job in the monitor
- Open work path in file explorer when key 'o' is pressed and when double-clicking on a job in the monitor
- Add an option to force single threading for each job
- Add '--from' and '--to' options to 'odatix fmax' to override fmax bounds
- Add '--from', '--to' and '--step' options to 'odatix freq' to override frequency list
- Add '--at' option to 'odatix freq' to override frequency list
- Add support for configuration-specific custom frequency definition

#### Odatix Explorer
- Add favicon

### Changed

#### Odatix
- Rework tool definition
- Replace shell calls with pure tcl in tcl script
- Improve log colors
- Set exit_when_done default value back to 'No'
- Improve compatibility with windows (still incomplete)
- Change default theme

### Fixed

#### Odatix
- Fix out-of-date documentation

#### Odatix Explorer
- Fix "warning: Theme "None" does not exist. Using default theme."

## [3.3.0] - 2025-01-29

### Added

#### Odatix
- Add 's' keybinding to force a job to start
- Add 'k' keybinding to kill a running job
- Add -E / --exit option to exit monitor when all jobs are done
- Add -j / --jobs option to specify maximum number of parallel jobs
- Add --logsize option to specify the size of the log history per job in the monitor
- Add -f / --force to force fmax synthesis to continue on synthesis error

#### Odatix Explorer
- Add themes
- Add --nobrowser option
- Add -T / --theme option

### Changed

#### Odatix
- Replaced 'sim_work_path' key in odatix.yml by 'simulation_work_path' (now relative to work_path)
- Replaced 'fmax_work_path' key in odatix.yml by 'fmax_synthesis_work_path' (now relative to work_path)
- Replaced 'custom_freq_work_path' key in odatix.yml by 'custom_freq_synthesis_work_path' (now relative to work_path)

### Fixed

#### Odatix
- Fix 'odatix results' not using the work paths defined in odatix.yml
- Fix lut and register count not being exported with ultrascale targets on vivado
- Fix custom frequency synthesis fail resulting in a success status

## [3.2.2] - 2025-01-24

### Fixed
- Fix fmax synthesis metrics not being exported

## [3.2.1] - 2025-01-23

### Fixed
- Fix missing scripts

## [3.2.0] - 2025-01-23

### Added

#### Odatix
- Add support for synthesis at custom frequencies (list and/or range)
- Add wildcard (*) support in place of configuration name
- Add alternate keyboard shortcuts
- Add mouse interactions
- Add basic theming
- Add exit_when_done and log_size_limit keys 

#### Odatix Explorer
- Add target selection in side bar
- Add support for range results
- Add color and maker options
- Add a home page
- Add options to enable/disable unique color+symbol for architectures and targets

### Changed
  
#### Odatix
- Change default work path for fmax synthesis to work/fmax_synthesis
- Change fmax synthesis output result key to 'fmax_synthesis'

#### Odatix Explorer
- Improve speed and remove unnecessary refreshes
- Improve UI and UX
- 
### Fixed

#### Odatix
- Fix crash if the number of jobs is greater than the number of lines in the terminal
- Fix controls not working with caps locked
- Fix missing param_target_file while generate_rtl=true not raising an error

#### Odatix Explorer
- Fix sidebar options being reset on page switch
- Fix high cpu usage

## [3.1.0] - 2024-09-10

### Added

#### Odatix
- Add a tool_install_path key to target files

#### Odatix Explorer
- Add '--normal_term_mode' option
- Add '--safe_mode' option

### Changed
  
- Change default work path for fmax synthesis to work/fmax
- Change default odatix-explorer development server address to 0.0.0.0

### Fixed

- Fix verilator examples not working with older versions of verilator
- Fix ghdl examples not working with older versions of ghdl
- Fix ugly formatting after replacing examples parameters
- Fix incorrect display when resizing in odatix curses interface
- Fix not resetting the terminal mode is the result path is not found in odatix-explorer
- Fix odatix-explorer crashing if when no target is selected
- Fix internal error at launch with some versions of dash core components
- Fix configuration file generation not working for openlane

## [3.0.3] - 2024-08-26

### Fixed

- Fix odatix-explorer not opening if the default port is already in use
- Fix compatibility with python 3.6
- Improve error handling

## [3.0.2] - 2024-08-23

### Added

- Add a 'init' command that does the same thing as '--init' but without any prompt

### Fixed

- Fix clean command not using the file specified in odatix.yml

## [3.0.0] - 2024-08-21

### Added

- Add support for OpenLane
- Add support for custom metrics
- Add a new curses interface
- Add a new job scheduler
- Add a '--init' flag to configure current directory
- Add a new interface for odatix-explorer
- Add VS charts to odatix-explorer
- Add radar charts to odatix-explorer
- Add display and export settings to odatix-explorer
 
### Changed

- Change Asterism's name to Odatix
- Change config files directory 
- Change results format 
