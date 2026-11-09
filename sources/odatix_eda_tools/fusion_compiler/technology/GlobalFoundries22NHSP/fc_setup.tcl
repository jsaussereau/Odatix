################################################################################
# GlobalFoundries 22FDX+ (22NHSP, 32HD116 LVT) - Fusion Compiler technology setup
################################################################################
#
# Copied into the job by Odatix (target_fusion_compiler.yml), then sourced by
# the Fusion Compiler scripts, which create the design library from it. It only
# sets variables:
#
#   TECH_FILE   technology file (.tf)
#   REF_LIBS    reference libraries (.ndm), as a list
#   TLUP_MAX    TLU+ file of the worst RC corner  \
#   TLUP_MIN    TLU+ file of the best RC corner    } physical synthesis and
#   TLUP_MAP    layer map of the TLU+ files        /  place and route only
#
# Adjust the paths to your installation.

set LIB_DIR "/asic/ip/DesignWare_logic_libs/globalfoundaries22nhsp/32hd116/hdl/lvt/2.00a"
set PDK_DIR "/asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4"

set TECH_FILE "$LIB_DIR/ndm/tf/gf22nspllogl32hdl116f_9M_2Mx_4Cx_2Ix_1Ox_LB.tf"

# Frame and timing (CCS) library, generated from the cell library with Library
# Manager: point this at where you generated it.
set REF_LIBS [list "$LIB_DIR/ndm/gf22nspllogl32hdl116f_frame_timing_ccs.ndm"]

set TLU_NAME "9M_2Mx_4Cx_2Ix_1Ox_LBthick"
set TLUP_DIR "$PDK_DIR/PlaceRoute/ICC2/TLUPlus/$TLU_NAME"
set TLUP_MAX "$TLUP_DIR/22fdsoi_${TLU_NAME}_FuncRCmax_detailed.tluplus"
set TLUP_MIN "$TLUP_DIR/22fdsoi_${TLU_NAME}_FuncRCmin_detailed.tluplus"
set TLUP_MAP "$PDK_DIR/PEX/StarRC/$TLU_NAME/22fdsoi_${TLU_NAME}_FuncRCmax_CalLVS.map"
