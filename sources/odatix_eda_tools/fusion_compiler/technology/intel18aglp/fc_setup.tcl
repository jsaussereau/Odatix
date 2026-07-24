################################################################################
# GlobalFoundries 22nm - Fusion Compiler Setup
################################################################################

################################################################################
# Library paths
################################################################################

set LIB_DIR "/asic/ip/DesignWare_logic_libs/intel18aglp/14hs/hsl/svt/1.00a"
set PDK_TF "${LIB_DIR}/ndm/tf"
set LIBNAME "in18axpslogl14hsl050f"


################################################################################
# TLUPlus files
################################################################################
set TLUP_DIR \
"/asic/pdk/globalfoundries/12LP/V1.0_7.0b/PlaceRoute/ICC2/TLUPlus/9M_3Mx_4Cx_2Gx_LB"

set TLU_NAME "12lp_9M_3Mx_4Cx_2Gx_LB"


set TLUP_MAP \
"/asic/pdk/globalfoundries/12LP/V1.0_7.0b/DFM/DRCplus/MVS/PM/layer.map"

set TLUP_MAX \
"$TLUP_DIR/${TLU_NAME}_FuncRCmax_detailed.tlup"

set TLUP_MIN \
"$TLUP_DIR/${TLU_NAME}_FuncRCmin_detailed.tlup"



################################################################################
# Technology file
################################################################################

set TECH_FILE \
"$PDK_TF/in18axpslogl14hsl050f_m14_2x1xa1xb6ya2yb2yc.tf"

################################################################################
# Reference library (generated with Library Manager)
################################################################################

# Use the generated NDM
set REF_LIB \
"${LIB_DIR}/ndm/in18axpslogl14hsl050f_frame_only.ndm"
# Alternatively:
# set REF_LIB "$LIB_DIR/ndm/gf22nspllogl32hdl116f_frame_timing_ccs.ndm"

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