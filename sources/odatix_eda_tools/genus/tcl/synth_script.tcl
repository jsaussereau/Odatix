#################################################################################
# GENUS SYNTHESIS SCRIPT
#################################################################################
set effort high

source scripts/settings.tcl
#source scripts/is_slack_met.tcl
report_progress 28 $synth_statusfile

#################################################################################
# ELABORATE
#################################################################################

#elaborate $top_level_module

#check_design

#################################################################################
# CONSTRAINTS
#################################################################################

read_sdc $constraints_file
report_clocks
report_timing -lint
check_timing_intent

report_progress 40 $synth_statusfile


#################################################################################
# SYNTHESIS
#################################################################################

set_db syn_global_effort $effort

syn_generic
report_progress 50 $synth_statusfile

syn_map
report_progress 70 $synth_statusfile

syn_opt
report_progress 90 $synth_statusfile

#################################################################################
# REPORTS
#################################################################################


report_timing > $timing_rep
report_area > $area_rep
report_power -unit mw > $power_rep
report_qor > $report_path/qor.rep
report_area -detail > $utilization_rep


report_timing 
report_area 
report_power -unit mw

report_progress 95 $synth_statusfile


#################################################################################
# NETLIST
#################################################################################

write_hdl > $result_path/${top_level_module}_netlist.v
report_progress 100 $synth_statusfile
puts "Synthesis completed successfully!"
