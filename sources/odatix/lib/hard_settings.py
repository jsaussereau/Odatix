# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

import re 

# Analyze steps
param_settings_filename = "_settings.yml"
sim_settings_filename = "_settings.yml"
tool_settings_filename = "tool.yml"
common_script_path = "_common"
tool_tcl_path = "tcl"

# Work directory paths
work_rtl_path = "rtl"
work_script_path = "scripts"
work_report_path = "report"
work_result_path = "result"
work_log_path = "log"
# Where the constraint files a user provides are copied, next to the timing
# constraint file Odatix generates itself (see lib/constraint_files.py).
work_constraint_path = "constraints"

# Work directory files
arch_filename = "architecture.txt"
target_filename = "target.txt"
flow_filename = "flow.txt"
steps_filename = "steps.yml"
tcl_config_filename = "settings.tcl"
yaml_config_filename = "settings.yml"
fmax_status_filename = "status.log"
sim_progress_filename = "progress.log"
synth_status_filename = "synth_status.log"
frequency_search_filename = "frequency_search.log"
param_domains_filename = "param_domains.yml"
pnr_source_filename = "pnr.yml"

# Where a simulation/workflow writes its progress, relative to the job's work
# directory. Makefiles write it into the log directory they are handed, so the
# default path must include it, not just the file name.
sim_progress_file = work_log_path + "/" + sim_progress_filename

# Handoff from a synthesis job to a place & route job run with another tool
# ("odatix pnr"). A synthesis flow that wants to be usable as a pnr input writes
# these three files in its result directory, under these exact names, whatever
# the tool calls them internally. Mirrored in tcl by $netlist_file, $sdc_file and
# $sdf_file (see the _common/settings.tcl of the eda tools).
pnr_netlist_filename = "netlist.v"
pnr_sdc_filename = "design.sdc"
pnr_sdf_filename = "design.sdf"

# Last path segment of a place & route job whose source is an fmax search. A
# custom frequency source uses "<N>MHz" there instead, so the two never collide
# and every pnr job directory has the same depth.
pnr_fmax_dirname = "fmax"

# Values to retrieve in files
valid_status = "Done: 100%"
valid_frequency_search = "Highest frequency with timing constraints being met"

# Patterns
source_tcl = "source scripts/"
fmax_status_pattern = re.compile(r"(.*): ([0-9]+)% \(([0-9]+)\/([0-9]+)\)(.*)")
synth_status_pattern = re.compile(r"(.*): ([0-9]+)%(.*)")
sim_status_pattern = re.compile(r"(.*): ([0-9]+)%(.*)")

# Bounds
default_fmax_lower_bound = 1  # in MHz
default_fmax_upper_bound = 1000  # in MHz
default_custom_freq_list = [50, 100]  # in MHz

# GUI
max_preview_values = 500

# Misc
main_parameter_domain = "__main__"

# Daemon
daemon_state_dirname = ".odatix_sessions"
daemon_default_host = "127.0.0.1"
daemon_default_port = 8000
daemon_state_file = "state.json"
daemon_log_file = "daemon.log"
daemon_state_prefix = "state."
daemon_state_suffix = ".json"
daemon_log_prefix = "daemon."
daemon_log_suffix = ".log"
daemon_log_enabled_default = False

# Tools are no longer hard-coded: the list of supported eda tools is discovered
# at runtime by scanning the user tools directory and the built-in one (see
# odatix.lib.eda_tools). A tool is any directory containing a "tool.yml" file.
default_analysis_target = "analysis"
default_analysis_constraint_file = "analysis_constraints.txt"

invalid_filename_characters = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', ' ']
