#################################################################################
# GENUS LOGICAL SYNTHESIS SCRIPT
#################################################################################

set effort high

source scripts/settings.tcl
report_progress 28 $synth_statusfile

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

puts "=========================================="
puts "Running LOGICAL synthesis"
puts "=========================================="

syn_generic
report_progress 50 $synth_statusfile

syn_map
report_progress 70 $synth_statusfile

syn_opt
report_progress 90 $synth_statusfile

#################################################################################
# LOGICAL REPORT PATH
#################################################################################

set logical_report_path "$report_path/logical"
file mkdir $logical_report_path

#################################################################################
# REPORTS
#################################################################################


report_timing > $timing_rep
report_timing > $report_path/timing_logical.rep

report_area > $area_rep
report_area > $report_path/area_logical.rep

report_power -unit mw > $power_rep
report_power -unit mw > $report_path/power_logical.rep

report_area -detail > $utilization_rep
report_area -detail > $report_path/utilization_logical.rep

report_qor > $report_path/qor_logical.rep

report_timing
report_area
report_power -unit mw

report_progress 95 $synth_statusfile

#################################################################################
# LOGICAL RESULT PATH
#################################################################################

set logical_result_path "$result_path/logical"
file mkdir $logical_result_path

#################################################################################
# NETLIST / OUTPUTS
#################################################################################

write_hdl > $logical_result_path/${top_level_module}_netlist.v
write_sdf > $logical_result_path/${top_level_module}.sdf
write_sdc > $logical_result_path/${top_level_module}.sdc

#################################################################################
# FINISH
#################################################################################

report_progress 100 $synth_statusfile

puts "=========================================="
puts "Logical synthesis completed successfully!"
puts "=========================================="