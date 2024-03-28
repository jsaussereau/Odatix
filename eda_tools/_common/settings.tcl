#
# Copyright(C) 2022 by Jonathan Saussereau. All rights reserved.
# 
# All source codes and documentation contain proprietary confidential
# information and are distributed under license. It may be used, copied
# and/or disclosed only pursuant to the terms of a valid license agreement
# with Jonathan Saussereau. This copyright must be retained at all times.
#
# Last edited: 2022/07/08 22:04
#

######################################
# Settings
######################################

set top_level_module  soc_wrapper_top
set top_level_file    soc/soc_top_level.sv

set clock_signal      i_xtal_p

set script_path       scripts
set tmp_path          synth
set arch_path         architectures
set rtl_path          ../../../rtl
set report_path       $tmp_path/report
set log_path          $tmp_path/log

set analyze_script    $script_path/analyze_script.tcl
set synth_script      $script_path/synth_script.tcl
set summary_script    $script_path/summary.tcl

set target_file       $tmp_path/target.txt
set architecture_file $tmp_path/architecture.txt
set constraints_file  $tmp_path/constraints.txt

set utilization_rep   $report_path/utilization.rep
set timing_rep        $report_path/timing.rep
set power_rep         $report_path/power.rep
set freq_rep          $report_path/frequency.rep

set logfile           $log_path/frequency_search.log
set statusfile        $log_path/status.log
set synth_statusfile  $log_path/synth_status.log

set fmax_lower_bound  70
set fmax_upper_bound  90
set fmax_explore      0
set fmax_mindiff      1
set fmax_safezone     5

set rtl_file_format   .sv

set file_copy_enable  true
set file_copy_source  config/soc_config.sv
set file_copy_dest    rtl/soc_config.sv

# warning: escape characters twice (e.g. '\\/' for '/')
set use_parameters    true
set start_delimiter   "#("
set stop_delimiter    ")("

######################################
# Create directories
######################################

exec /bin/sh -c "mkdir -p $tmp_path"
exec /bin/sh -c "mkdir -p $report_path"
exec /bin/sh -c "mkdir -p $log_path"

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
