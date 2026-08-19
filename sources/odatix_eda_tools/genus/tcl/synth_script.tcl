#################################################################################
# GENUS SYNTHESIS ENTRY SCRIPT
#################################################################################

# Choose synthesis type:
#   logical
#   physical
#set synth_mode "physical"

#################################################################################
# COMMON SETUP
#################################################################################

source scripts/settings.tcl

#################################################################################
# SELECT SYNTHESIS FLOW
#################################################################################

if {$synth_mode eq "logical"} {

    puts "=========================================="
    puts "Selected synthesis mode: LOGICAL"
    puts "=========================================="

    source scripts/synth_script_logical.tcl

} elseif {$synth_mode eq "physical"} {

    puts "=========================================="
    puts "Selected synthesis mode: PHYSICAL"
    puts "=========================================="

    source scripts/synth_script_physical.tcl

} else {

    error "Invalid synthesis mode '$synth_mode'. Use 'logical' or 'physical'."

}