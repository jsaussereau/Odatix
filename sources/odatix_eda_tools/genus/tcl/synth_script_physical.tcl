#################################################################################
# GENUS PHYSICAL / iSPATIAL SYNTHESIS SCRIPT
#################################################################################

set effort high

source scripts/settings.tcl
report_progress 28 $synth_statusfile

#################################################################################
# PHYSICAL REPORT PATH
#################################################################################

set physical_report_path "$report_path/physical"
file mkdir $physical_report_path

set timing_rep      "$physical_report_path/timing.rep"
set area_rep        "$physical_report_path/area.rep"
set power_rep       "$physical_report_path/power.rep"
set utilization_rep "$physical_report_path/utilization.rep"


init_design 

#################################################################################
# CONSTRAINTS
#################################################################################

read_sdc $constraints_file
report_clocks
report_timing -lint
check_timing_intent

report_progress 40 $synth_statusfile

#################################################################################
# PHYSICAL SYNTHESIS SETUP
#################################################################################

set_db syn_global_effort $effort
set_db opt_spatial_effort extreme

puts "=========================================="
puts "Running PHYSICAL / iSpatial synthesis"
puts "=========================================="

#################################################################################
# FLOORPLAN PARAMETERS
#################################################################################

# Automatic floorplan generation
set_db predict_floorplan_enable_during_generic true
set_db physical_force_predict_floorplan true

#################################################################################
# SYNTHESIS
#################################################################################

syn_generic -physical
report_progress 50 $synth_statusfile

syn_map -physical
report_progress 70 $synth_statusfile

syn_opt -spatial
report_progress 90 $synth_statusfile

#################################################################################
# REPORTS
#################################################################################

report_timing > $timing_rep
report_timing > $report_path/timing_physical.rep

report_area > $area_rep
report_area > $report_path/area_physical.rep

report_power -unit mw > $power_rep
report_power -unit mw > $report_path/power_physical.rep

report_area -detail > $utilization_rep
report_area -detail > $report_path/utilization_physical.rep

report_qor > $report_path/qor_physical.rep

#################################################################################
# NETLIST / OUTPUTS
#################################################################################

write_hdl > $result_path/${top_level_module}_netlist.v
write_sdf > $result_path/${top_level_module}.sdf
write_sdc > $result_path/${top_level_module}.sdc

#################################################################################
# FINISH
#################################################################################

report_progress 100 $synth_statusfile

puts "=========================================="
puts "Physical / iSpatial synthesis completed successfully!"
puts "=========================================="