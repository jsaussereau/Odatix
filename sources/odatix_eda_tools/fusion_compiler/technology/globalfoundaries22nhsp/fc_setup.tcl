################################################################################
# GlobalFoundries 22nm - Fusion Compiler Setup
################################################################################

################################################################################
# Library paths
################################################################################

set LIB_DIR "/asic/ip/DesignWare_logic_libs/globalfoundaries22nhsp/32hd116/hdl/lvt/2.00a"

################################################################################
# Technology file
################################################################################

set TECH_FILE \
"$LIB_DIR/ndm/tf/gf22nspllogl32hdl116f_9M_2Mx_4Cx_2Ix_1Ox_LB.tf"

################################################################################
# TLUPlus files
################################################################################

set TLUP_DIR \
"/asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4/PlaceRoute/ICC2/TLUPlus"

set TLU_NAME "9M_2Mx_4Cx_2Ix_1Ox_LBthick"

set TLUP_MAP \
"/asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4/PEX/StarRC/9M_2Mx_4Cx_2Ix_1Ox_LBthick/22fdsoi_9M_2Mx_4Cx_2Ix_1Ox_LBthick_FuncRCmax_CalLVS.map"

set TLUP_MAX \
"$TLUP_DIR/${TLU_NAME}/22fdsoi_${TLU_NAME}_FuncRCmax_detailed.tluplus"

set TLUP_MIN \
"$TLUP_DIR/${TLU_NAME}/22fdsoi_${TLU_NAME}_FuncRCmin_detailed.tluplus"

################################################################################
# Reference library
################################################################################

set REF_LIB "/net/users/mcirolinimic/Documents/stage/FusionCompiler_GitHub/FusionCompiler_Flow/fc_setup/globalfoundaries22nhsp/gf22nspllogl32hdl116f_frame_timing_ccs.ndm"

################################################################################
# Check files
################################################################################

if {![file exists $TECH_FILE]} {
    error "Technology file not found:\n$TECH_FILE"
}

if {![file exists $REF_LIB]} {
    error "Reference library not found:\n$REF_LIB"
}

################################################################################
# Already initialized?
################################################################################

if {[info exists ::FC_SETUP_DONE]} {
    return
}

################################################################################
# Print configuration
################################################################################

puts ""
puts "===================================================="
puts "Fusion Compiler Setup"
puts "===================================================="
puts "Technology file : $TECH_FILE"
puts "Reference NDM   : $REF_LIB"
puts "===================================================="
puts ""

################################################################################
# Create design library
################################################################################

create_lib work \
    -technology $TECH_FILE \
    -ref_libs $REF_LIB

puts "Current library:"
current_lib

puts ""
puts "Reference libraries:"
report_ref_libs

puts ""
puts "Technology:"
report_lib work

################################################################################
# Read parasitic technology
################################################################################

puts ""
puts "Reading TLU+ technology..."


#read_parasitic_tech \
    -tlup $TLUP_MAX \
    -layermap $TLUP_MAP \
    -name RCMAX

#read_parasitic_tech \
    -tlup $TLUP_MIN \
    -layermap $TLUP_MAP \
    -name RCMIN

#set_parasitic_parameters \
    -late_spec RCMAX \
    -early_spec RCMIN

################################################################################
# Library information
################################################################################

puts ""
puts "Current library"
puts "---------------"
current_lib

puts ""
puts "Reference libraries"
puts "-------------------"
report_ref_libs

puts ""
puts "Site definitions"
puts "----------------"
report_site_defs

puts ""
puts "Number of library cells"
puts "-----------------------"
puts [sizeof_collection [get_lib_cells */*/frame]]

puts ""
puts "Example inverter cells"
puts "----------------------"
get_lib_cells *INV*

puts ""
puts "Example buffer cells"
puts "--------------------"
get_lib_cells *BUF*

puts ""
puts "Example AND cells"
puts "-----------------"
get_lib_cells *AND*

puts ""
puts "Example XOR cells"
puts "-----------------"
get_lib_cells *XOR*

puts ""
puts "===================================================="
puts "Setup completed successfully."
puts "===================================================="

################################################################################
# Mark setup as completed
################################################################################

set ::FC_SETUP_DONE 1