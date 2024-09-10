# Change Log
All notable changes to this project will be documented in this file.
 
The format is based on [Keep a Changelog](http://keepachangelog.com/).
    
## [3.1.0] - 2024-09-10

### Added 

- Add '--normal_term_mode' option to odatix-explorer
- Add '--safe_mode' option to odatix-explorer
- Add a tool_install_path key to target files

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
