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

set local_script_path  scripts
set local_rtl_path     rtl
set local_result_path  result
set local_report_path  report
set local_log_path     log
set local_work_path    work

set tmp_path           synth
set script_path        $tmp_path/$local_script_path
set rtl_path           $tmp_path/$local_rtl_path
set result_path        $tmp_path/$local_result_path
set report_path        $tmp_path/$local_report_path
set log_path           $tmp_path/$local_log_path
set work_path          $tmp_path/$local_work_path

set source_rtl_path    ../../../rtl
set source_arch_path   architectures

# Handoff a synthesis flow writes for "odatix pnr" to pick up. A flow that wants
# its results to be placeable & routable by another tool writes its netlist, its
# constraints and its delays under these exact names, whatever the tool calls
# them internally. Odatix looks for nothing else.
set netlist_file       $result_path/netlist.v
set sdc_file           $result_path/design.sdc
set sdf_file           $result_path/design.sdf

# The other end of that handoff, set by Odatix on place & route jobs only: the
# synthesis job this one continues, and the files it left there. Empty for every
# other job type.
set source_work_path   ""
set source_type        ""
set source_tool        ""
set source_flow        ""
set source_netlist     ""
set source_sdc         ""
set source_sdf         ""

set init_script        $script_path/init_script.tcl
set analyze_script     $script_path/analyze_script.tcl
set synth_script       $script_path/synth_script.tcl
set summary_script     $script_path/summary.tcl

set frequency_file     $tmp_path/frequency.txt
set target_file        $tmp_path/target.txt
set architecture_file  $tmp_path/architecture.txt
set constraints_file   $tmp_path/constraints.txt

set utilization_rep    $report_path/utilization.rep
set utilization_h_rep  $report_path/utilization_hier.rep
set area_rep           $report_path/area.rep
set timing_rep         $report_path/timing.rep
set power_rep          $report_path/power.rep
set freq_rep           $report_path/frequency.rep
set ref_rep            $report_path/reference.rep
set design_analysis    $report_path/checkout.rep
set unresolved_report  $report_path/unresolved.rep

set logfile            $log_path/frequency_search.log
set statusfile         $log_path/status.log
set synth_statusfile   $log_path/synth_status.log
set analysis_statusfile $log_path/analysis_status.log

set target_frequency   100
set fmax_lower_bound   70
set fmax_upper_bound   90
set fmax_explore       0
set fmax_mindiff       1
set fmax_safezone      5

set continue_on_error  0
set single_thread      1

set lib_name           WORK




######################################
# Procedures
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

proc odatix_step_done {step {signature ""}} {
    # Record that a step of the flow completed, in the file Odatix resumes from
    # ("log/steps.yml", see odatix.lib.job_steps).
    #
    # Odatix records the steps of a task itself once the process it ran them
    # with exits, which is enough as long as one process runs one step. A flow
    # declaring a session runs several steps in a single process, and a session
    # dying halfway would then lose every step it had already finished: calling
    # this at the end of each step is what keeps such a run resumable. Recording
    # a step twice is harmless — Odatix rewrites the file from the steps it ran
    # anyway.
    global log_path
    set path [file join $log_path "steps.yml"]
    file mkdir $log_path
    if {![file exists $path]} {
        set f [open $path w]
        puts $f "completed:"
        close $f
    }
    set timestamp [clock format [clock seconds] -format "%Y-%m-%d_%H-%M-%S"]
    set f [open $path a]
    puts $f "- name: $step"
    puts $f "  timestamp: $timestamp"
    close $f
    puts "$signature <cyan>step '$step' done<end>"
}

proc odatix_publish_handoff {netlist sdc sdf {signature ""}} {
    # Publish a synthesis result under the names "odatix pnr" looks for.
    #
    # Tools name their outputs as they please (Design Compiler writes
    # "<design>_<run>.v", Genus "<top>_netlist.v"), so a synthesis flow calls
    # this with whatever it just wrote and Odatix gets a stable handoff. Call it
    # at the very end of a synthesis, once the netlist, the constraints and the
    # delays are on disk.
    global netlist_file sdc_file sdf_file
    file mkdir [file dirname $netlist_file]
    foreach {produced published} [list $netlist $netlist_file $sdc $sdc_file $sdf $sdf_file] {
        if {$produced eq "" || ![file exists $produced]} {
            puts "$signature <yellow>warning: no [file tail $published] to publish for place & route<end>"
            continue
        }
        if {[file normalize $produced] ne [file normalize $published]} {
            file copy -force $produced $published
        }
        puts "$signature published <cyan>[file tail $published]<end> for place & route"
    }
}

proc odatix_require_source {{signature ""}} {
    # Check that the synthesis a place & route job continues left what is needed.
    #
    # Odatix already checks this before running the job; a flow calls it anyway
    # so that a directory cleaned in between fails with a clear message instead
    # of the tool's own one.
    global source_netlist source_sdc source_work_path source_tool
    if {$source_work_path eq ""} {
        puts "$signature <bold><red>error: this job has no source synthesis (is it running as a place & route job?)<end>"
        exit -1
    }
    foreach required [list $source_netlist $source_sdc] {
        if {$required eq "" || ![file exists $required]} {
            puts "$signature <bold><red>error: missing $required from the source synthesis<end>"
            exit -1
        }
    }
    puts "$signature place & route of the netlist synthesized by <cyan>$source_tool<end>"
}

proc get_files_recursive {path patterns} {
    set file_list {}
    if {![file isdirectory $path]} {return $file_list}
    set queue [list $path]
    while {[llength $queue]} {
        set dir [lindex $queue 0]
        set queue [lrange $queue 1 end]
        foreach pattern $patterns {
            foreach f [glob -nocomplain -directory $dir -types f $pattern] {
                lappend file_list $f
            }
        }
        foreach sub [glob -nocomplain -directory $dir -types d *] {
            set tail [file tail $sub]
            if {$tail eq "." || $tail eq ".."} {continue}
            lappend queue $sub
        }
    }
    return $file_list
}
