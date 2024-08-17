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

import os
import re

def edit_config_file(arch, config_file): 
  with open(config_file, 'r') as f:
    cf_content = f.read()
    cf_content = re.sub("(set tmp_path.*)",           "set tmp_path           " + os.path.realpath(arch.tmp_dir), cf_content)
    cf_content = re.sub("(set script_path.*)",        "set script_path        " + os.path.realpath(arch.tmp_script_path), cf_content)
    cf_content = re.sub("(set report_path.*)",        "set report_path        " + os.path.realpath(arch.tmp_report_path), cf_content)
    cf_content = re.sub("(set rtl_path.*)",           "set rtl_path           " + arch.rtl_path, cf_content)
    cf_content = re.sub("(set arch_path.*)",          "set arch_path          " + arch.arch_path, cf_content)
    cf_content = re.sub("(set clock_signal.*)",       "set clock_signal       " + arch.clock_signal, cf_content)
    cf_content = re.sub("(set reset_signal.*)",       "set reset_signal       " + arch.reset_signal, cf_content)
    cf_content = re.sub("(set top_level_module.*)",   "set top_level_module   " + arch.top_level_module, cf_content)
    cf_content = re.sub("(set top_level_file.*)",     "set top_level_file     " + arch.top_level_filename, cf_content)
    cf_content = re.sub("(set fmax_lower_bound.*)",   "set fmax_lower_bound   " + arch.fmax_lower_bound, cf_content)
    cf_content = re.sub("(set fmax_upper_bound.*)",   "set fmax_upper_bound   " + arch.fmax_upper_bound, cf_content)
    cf_content = re.sub("(set lib_name.*)",           "set lib_name           " + arch.lib_name, cf_content)
    cf_content = re.sub("(set constraints_file.*)",   "set constraints_file   $tmp_path/" + arch.constraint_filename, cf_content)
 
  with open(config_file, 'w') as f:
    f.write(cf_content)
