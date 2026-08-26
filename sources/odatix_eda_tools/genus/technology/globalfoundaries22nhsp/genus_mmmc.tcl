#################################################################################
# MMMC SETUP - SINGLE MODE / SINGLE CORNER
#################################################################################
# Timing library
set RTL_LIB /asic/ip/DesignWare_logic_libs/globalfoundaries22nhsp/32hd116/hdl/lvt/2.00a/liberty/logic_synth_lvf

set LIB_WC $RTL_LIB/gf22nspllogl32hdl116f_SSG_0P59V_0P00V_0P00V_0P00V_125C.lib.gz
set LIB_BC $RTL_LIB/gf22nspllogl32hdl116f_FFG_0P945V_0P00V_0P00V_0P00V_M40C.lib.gz
set LIB_TYP $RTL_LIB/gf22nspllogl32hdl116f_TT_0P80V_0P00V_0P00V_0P00V_25C.lib.gz

# Constraints
set SDC_FILE $constraints_file

puts "PWD = [pwd]"

if {[info exists constraints_file]} {
    puts "constraints_file = $constraints_file"
} else {
    puts "ERROR: constraints_file is NOT defined"
}


# QRC technology files
set RTL_QRC /asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4/PEX/QRC/10M_2Mx_6Cx_2Ix_LBthick
set QRC_MAX $RTL_QRC/FuncRCmax/qrcTechFile
set QRC_MIN $RTL_QRC/FuncRCmin/qrcTechFile
set QRC_TYP $RTL_QRC/nominal/qrcTechFile
    
#################################################################################
# LIBRARY SET
#################################################################################

create_library_set \
    -name LIBSET_SLOW \
    -timing [list $LIB_WC]

create_library_set \
    -name LIBSET_FAST \
    -timing [list $LIB_BC]

create_library_set \
    -name LIBSET_TYP \
    -timing [list $LIB_TYP]

#################################################################################
# TIMING CONDITION
#################################################################################

create_timing_condition \
    -name TC_SLOW \
    -library_sets [list LIBSET_SLOW]

create_timing_condition \
    -name TC_FAST \
    -library_sets [list LIBSET_FAST]

create_timing_condition \
    -name TC_TYP \
    -library_sets [list LIBSET_TYP]

#################################################################################
# RC CORNER
#################################################################################

create_rc_corner \
    -name RC_MAX \
    -temperature 125 \
    -qrc_tech $QRC_MAX

create_rc_corner \
    -name RC_MIN \
    -temperature -40 \
    -qrc_tech $QRC_MIN

create_rc_corner \
    -name RC_DEFAULT \
    -temperature 25 \
    -qrc_tech $QRC_TYP

#################################################################################
# DELAY CORNER
#################################################################################

create_delay_corner \
    -name DELAY_SLOW \
    -timing_condition TC_SLOW \
    -rc_corner RC_MAX

create_delay_corner \
    -name DELAY_FAST \
    -timing_condition TC_FAST \
    -rc_corner RC_MIN

create_delay_corner \
    -name DELAY_TYP \
    -timing_condition TC_TYP \
    -rc_corner RC_DEFAULT

#################################################################################
# CONSTRAINT MODE
#################################################################################

create_constraint_mode \
    -name FUNC \
    -sdc_files [list $SDC_FILE]

#################################################################################
# ANALYSIS VIEW
#################################################################################

create_analysis_view \
    -name VIEW_SETUP \
    -constraint_mode FUNC \
    -delay_corner DELAY_SLOW

create_analysis_view \
    -name VIEW_HOLD \
    -constraint_mode FUNC \
    -delay_corner DELAY_FAST

create_analysis_view \
    -name VIEW_TYP \
    -constraint_mode FUNC \
    -delay_corner DELAY_TYP

#################################################################################
# ACTIVE VIEWS
#################################################################################

set_analysis_view \
    -setup [list VIEW_SETUP] \
    -hold  [list VIEW_HOLD]