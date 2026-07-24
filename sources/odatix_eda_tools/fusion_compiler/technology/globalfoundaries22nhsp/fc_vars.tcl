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
"$LIB_DIR/ndm/tf/gf22nspllogl32hdl116f_8M_2Mx_4Cx_2Ix_LB.tf"



################################################################################
# TLUPlus files
################################################################################
set TLUP_DIR \
"/asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4/PlaceRoute/ICC2/TLUPlus"

set TLU_NAME "9M_2Mx_4Cx_2Ix_1Ox_LBthick"


set TLUP_MAP \
"/asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4/DFM/DRCplus/LPA/PM/layer.map"

set TLUP_MAX \
"$TLUP_DIR/${TLU_NAME}/22fdsoi_${TLU_NAME}_FuncRCmax_detailed.tluplus"

set TLUP_MIN \
"$TLUP_DIR/${TLU_NAME}/22fdsoi_${TLU_NAME}_FuncRCmin_detailed.tluplus"



################################################################################
# Reference library (generated with Library Manager)
################################################################################

# Use YOUR generated NDM
set REF_LIB "/net/users/mcirolinimic/Documents/stage/FusionCompiler_GitHub/FusionCompiler_Flow/fc_setup/globalfoundaries22nhsp/gf22nspllogl32hdl116f_frame_timing_ccs.ndm"

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
