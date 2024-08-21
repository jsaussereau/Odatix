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

######################################
# Settings
######################################

set top_level_module   soc_wrapper_top
set top_level_file     soc/soc_top_level.sv

set clock_signal       i_xtal_p
set reset_signal       i_rst

set script_path        scripts
set tmp_path           synth
set arch_path          architectures
set rtl_path           ../../../rtl
set result_path        $tmp_path/result
set report_path        $tmp_path/report
set log_path           $tmp_path/log
set work_path          $tmp_path/work

set init_script        $script_path/init_script.tcl
set analyze_script     $script_path/analyze_script.tcl
set synth_script       $script_path/synth_script.tcl
set summary_script     $script_path/summary.tcl

set target_file        $tmp_path/target.txt
set architecture_file  $tmp_path/architecture.txt
set constraints_file   $tmp_path/constraints.txt

set utilization_rep    $report_path/utilization.rep
set area_rep           $report_path/area.rep
set timing_rep         $report_path/timing.rep
set power_rep          $report_path/power.rep
set freq_rep           $report_path/frequency.rep
set ref_rep            $report_path/reference.rep

set logfile            $log_path/frequency_search.log
set statusfile         $log_path/status.log
set synth_statusfile   $log_path/synth_status.log

set fmax_lower_bound   70
set fmax_upper_bound   90
set fmax_explore       0
set fmax_mindiff       1
set fmax_safezone      5

set rtl_file_format    .sv

set lib_name           WORK

######################################
# Procedure
######################################

proc report_progress {progress progressfile {comment ""}} {
    set progressfile_handler [open $progressfile w]
    if {$progress >= 100} {
        puts $progressfile_handler "Done: 100\% $comment"
    } else {
        puts $progressfile_handler "In progress: $progress% $comment"
    }
    close $progressfile_handler
}
