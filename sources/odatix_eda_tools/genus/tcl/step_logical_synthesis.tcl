#################################################################################
# GENUS LOGICAL SYNTHESIS SCRIPT
#################################################################################

set effort high
source scripts/settings.tcl

#################################################################################
# CONSTRAINTS
#################################################################################

if {![info exists ::init_design_done]} {
    puts "Initializing design..."
    init_design
    set ::init_design_done 1
} else {
    puts "Design already initialized."
    puts "Updating MMMC constraints..."
    update_constraint_mode \
        -name FUNC \
        -sdc_files [list $constraints_file]
}

report_clocks
report_timing -lint
check_timing_intent

report_progress 70 $synth_statusfile

#################################################################################
# SYNTHESIS
#################################################################################

set_db syn_global_effort $effort

puts "=========================================="
puts "Running LOGICAL synthesis"
puts "=========================================="

syn_generic
syn_map
syn_opt

#################################################################################
# LOGICAL REPORT PATH
#################################################################################

#set logical_report_path "$report_path/logical"
#file mkdir $logical_report_path

#################################################################################
# REPORTS
#################################################################################


report_timing > $report_path/timing_logical.rep
report_area > $report_path/area_logical.rep
report_power -unit mw > $report_path/power_logical.rep
report_area -detail > $report_path/utilization_logical.rep
report_qor > $report_path/qor_logical.rep

report_timing
report_area
report_power -unit mw

report_timing > $report_path/timing.rep
report_area > $report_path/area.rep
report_power -unit mw > $report_path/power.rep
report_area -detail > $report_path/utilization.rep

#################################################################################
# FINISH
#################################################################################

# Setting 
report_progress 100 $synth_statusfile

puts "=========================================="
puts "Logical synthesis completed successfully!"
puts "=========================================="

#if {$LIB_TYPE ne "GF_22nm" || "AMS_C35"} {
#    puts "WARNING: Physical/iSpatial synthesis is currently supported only for GF_22nm."
#    puts "WARNING: Stopping after logical synthesis for technology '$LIB_TYPE'."
#    exit 0
#}