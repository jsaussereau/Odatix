#
# Copyright(C) 2022 by Jonathan Saussereau. All rights reserved.
# 
# All source codes and documentation contain proprietary confidential
# information and are distributed under license. It may be used, copied
# and/or disclosed only pursuant to the terms of a valid license agreement
# with Jonathan Saussereau. This copyright must be retained at all times.
#
# Last edited: 2022/07/07 13:10
#

######################################
# Settings
######################################
source scripts/settings.tcl

report_progress 0 $synth_statusfile

######################################
# Analyze source files
######################################
if {[info exists ::env(DO_NOT_ANALYZE_RTL)]} {
    if {[$::env(DO_NOT_ANALYZE_RTL) == 0]} {
        #source $analyze_script
        #puts "analyzing" 
    }
} else {
    #source $analyze_script
    #puts "analyzing" 
}
#source $analyze_script

######################################
# Read constraints
######################################
read_xdc $constraints_file

######################################
# Get target
######################################
set f [open $target_file]
set target [gets $f]
close $f

report_progress 10 $synth_statusfile

######################################
# Synthetize
######################################
synth_design -flatten_hierarchy full -part ${target} -top ${top_level_module} -verilog_define VIVADO
report_progress 45 $synth_statusfile
opt_design -sweep -remap -propconst
report_progress 55 $synth_statusfile
opt_design -directive Explore
report_progress 65 $synth_statusfile

######################################
# Place and route
######################################
place_design -directive Explore
report_progress 70 $synth_statusfile
phys_opt_design -retime -rewire -critical_pin_opt -placement_opt -critical_cell_opt
report_progress 75 $synth_statusfile
route_design -directive AggressiveExplore
report_progress 85 $synth_statusfile
place_design -post_place_opt
report_progress 90 $synth_statusfile
phys_opt_design -retime -routing_opt
# -lut_opt -casc_opt
report_progress 95 $synth_statusfile
route_design -directive NoTimingRelaxation
report_progress 98 $synth_statusfile

######################################
# Report
######################################
report_utilization > $utilization_rep
report_timing > $timing_rep
report_power > $power_rep

report_progress 0 $synth_statusfile
