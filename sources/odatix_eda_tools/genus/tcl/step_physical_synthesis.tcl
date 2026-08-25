#################################################################################
# GENUS PHYSICAL / iSPATIAL SYNTHESIS SCRIPT
#################################################################################

set effort high

source scripts/settings.tcl
#source scripts/genus_setup.tcl

report_progress 28 $synth_statusfile


if {![info exists ::init_design_done]} {
    init_design
    set ::init_design_done 1
}

report_clocks
report_timing -lint
check_timing_intent

report_progress 40 $synth_statusfile

#################################################################################
# Doing first the logical synthesis
#################################################################################

# source scripts/synth_script_logical.tcl

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
set_db predict_floorplan_core_density_size true

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

report_timing > $report_path/timing.rep
report_area > $report_path/area.rep
report_power -unit mw > $report_path/power.rep
report_area -detail > $report_path/utilization.rep
report_qor > $report_path/qor.rep

report_timing > $report_path/timing_physical.rep
report_area > $report_path/area_physical.rep
report_power -unit mw > $report_path/power_physical.rep
report_area -detail > $report_path/utilization_physical.rep
report_qor > $report_path/qor_physical.rep

# report timing from differents views
#report_timing -view VIEW_SETUP \
    > $report_path/timing_setup_physical.rep
#report_timing -view VIEW_HOLD -check_type hold \
    > $report_path/timing_hold_physical.rep


report_timing
report_area
report_power -unit mw

report_progress 95 $synth_statusfile


#################################################################################
# PHYSICAL RESULT PATH
#################################################################################

set physical_result_path "$result_path/physical"
file mkdir $physical_result_path

#################################################################################
# NETLIST / OUTPUTS
#################################################################################

write_hdl > $physical_result_path/${top_level_module}_netlist.v
write_sdf > $physical_result_path/${top_level_module}.sdf

#write_sdc -view VIEW_SETUP \
    > $physical_result_path/${top_level_module}_setup.sdc
#write_sdc -view VIEW_HOLD \
    > $physical_result_path/${top_level_module}_hold.sdc

#################################################################################
# FINISH
#################################################################################

# Save design for innovus
write_design -base_name $physical_result_path/genus2invs

# Save design for genus
write_db $physical_result_path/genus_physical.db

report_progress 100 $synth_statusfile

puts "=========================================="
puts "Physical / iSpatial synthesis completed successfully!"
puts "=========================================="