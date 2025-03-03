# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/).

## [3.5.1] - 2025-03-03

### Fixed

- Fix wildcard not working without parameter domains
- Fix parameter domains only being applied on the first target
- Fix parameter domains wildcard not working withouy main domain wildward

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
