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

# Work directory files
arch_filename = "architecture.txt"
target_filename = "target.txt"
tcl_config_filename = "settings.tcl"
yaml_config_filename = "settings.yml"
fmax_status_filename = "status.log"
sim_progress_filename = "progress.log"
synth_status_filename = "synth_status.log"
frequency_search_filename = "frequency_search.log"
param_domains_filename = "param_domains.yml"

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

default_supported_tools = ["vivado", "design_compiler", "openlane"]

invalid_filename_characters = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', ' ']
