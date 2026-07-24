################################################################################
# GlobalFoundries 12LP - Fusion Compiler Setup
################################################################################

################################################################################
# Library paths
################################################################################

set LIB_DIR "/asic/ip/DesignWare_logic_libs/globalfoundaries12lp/IN12LP_SC7P5T_84CPP_BASE_SSC14R_FDK/RELV00R60"
set PDK_TF "$LIB_DIR/ndm/9M_3Mx_4Cx_2Gx_LB/tf"
set LIBNAME "IN12LP_SC7P5T_84CPP_BASE_SSC14R"

################################################################################
# Technology file
################################################################################

set TECH_FILE \
"$PDK_TF/12LP_9M_3Mx_4Cx_2Gx_LB_7p5t_84cpp_ndm.tf"

################################################################################
# TLUPlus files
################################################################################

set TLUP_DIR \
"/asic/pdk/globalfoundries/12LP/V1.0_7.0b/PlaceRoute/ICC2/TLUPlus/9M_3Mx_4Cx_2Gx_LB"

set TLU_NAME "12lp_9M_3Mx_4Cx_2Gx_LB"

set TLUP_MAP \
"/asic/pdk/globalfoundries/12LP/V1.0_7.0b/PEX/StarRC/tcad/9M_3Mx_4Cx_2Gx_LB/12lp_9M_3Mx_4Cx_2Gx_LB_FuncRCmax_CalLVS.map"

set TLUP_MAX \
"$TLUP_DIR/${TLU_NAME}_FuncRCmax_detailed.tlup"

set TLUP_MIN \
"$TLUP_DIR/${TLU_NAME}_FuncRCmin_detailed.tlup"

################################################################################
# Reference library
################################################################################

set REF_LIB \
"/net/users/mcirolinimic/Documents/stage/FusionCompiler_GitHub/FusionCompiler_Flow/fc_setup/globalfoundaries12lp/IN12LP_SC7P5T_84CPP_BASE_SSC14R_frame_timing_ccs.ndm"

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
# Read parasitic technology (enable after flow is stable)
################################################################################

puts ""
puts "Reading TLU+ technology..."

# read_parasitic_tech \
#     -tlup $TLUP_MAX \
#     -layermap $TLUP_MAP \
#     -name RCMAX

# read_parasitic_tech \
#     -tlup $TLUP_MIN \
#     -layermap $TLUP_MAP \
#     -name RCMIN

# set_parasitic_parameters \
#     -late_spec RCMAX \
#     -early_spec RCMIN

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