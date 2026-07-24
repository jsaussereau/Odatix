################################################################################
# Fusion Compiler
################################################################################

source scripts/settings.tcl
source scripts/fc_setup.tcl

set signature "<grey>\[synth_script.tcl\]<end>"

report_progress 5 $synth_statusfile

################################################################################
# Read constraints
################################################################################

if {[llength [get_modes functional -quiet]] == 0} {
    create_mode functional
}

if {[sizeof_collection [get_corners default]] == 0} {
    create_corner default
}

if {[llength [get_scenarios functional_default -quiet]] == 0} {
    create_scenario \
        -name functional_default \
        -mode functional \
        -corner default
}

current_scenario functional_default

read_sdc $constraints_file

report_progress 25 $synth_statusfile

################################################################################
# Synthesis
################################################################################

puts ""
puts "----------------------------------------"
puts "<bold><cyan> SYNTHESIS <end>"
puts "----------------------------------------"

if {[info exists synthesis_mode] && $synthesis_mode == "physical"} {
    puts "<bold><yellow>Mode: Physical synthesis<end>"

    ########################################################################
    # TLU+ files
    ########################################################################

    read_parasitic_tech \
        -tlup $TLUP_MAX \
        -layermap $TLUP_MAP \
        -name RCMAX

    read_parasitic_tech \
        -tlup $TLUP_MIN \
        -layermap $TLUP_MAP \
        -name RCMIN

    set_parasitic_parameters \
        -late_spec RCMAX \
        -early_spec RCMIN

    ########################################################################
    # Extraction
    ########################################################################

    set_extraction_options \
        -reference_direction horizontal

    ########################################################################
    # Physical synthesis
    ########################################################################

    compile_fusion



    puts ""
    puts "========================================"
    puts "Initializing Floorplan"
    puts "========================================"
    initialize_floorplan \
        -site_def unit \
        -core_utilization 0.7 \
        -core_offset 2

    place_pins -self

    place_opt   
} else {
    puts "<bold><yellow>Mode: Logical synthesis<end>"

    ########################################################################
    # Logical synthesis
    ########################################################################

    #set_non_physical_mode

    compile_logical
}



report_progress 80 $synth_statusfile

################################################################################
# Reports
################################################################################

if {[info exists synthesis_mode] && $synthesis_mode == "physical"} {
    report_utilization > $area_rep
} else {
    report_area   > $area_rep
}
report_power  > $power_rep
report_timing > $timing_rep

puts ""
puts "----------------------------------------"
puts "<bold><cyan> WRITING REPORTS <end>"
puts "----------------------------------------"
puts ""

report_power
report_area
report_timing

report_progress 90 $synth_statusfile

################################################################################
# Export
################################################################################

#write_verilog $netlist_file

#write_sdf $sdf_file

#write_sdc -output $sdc_file

report_progress 100 $synth_statusfile