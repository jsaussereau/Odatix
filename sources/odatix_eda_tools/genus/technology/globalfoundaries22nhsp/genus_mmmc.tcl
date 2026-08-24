#################################################################################
# MMMC SETUP - SINGLE MODE / SINGLE CORNER
#################################################################################
# Timing library
set TIMING_LIB \
    /asic/ip/DesignWare_logic_libs/globalfoundaries22nhsp/32hd116/hdl/lvt/2.00a/liberty/logic_synth_lvf/gf22nspllogl32hdl116f_SSG_0P72V_0P00V_0P60V_M1P00V_125C.lib.gz

# Constraints
set SDC_FILE $constraints_file

puts "PWD = [pwd]"

if {[info exists constraints_file]} {
    puts "constraints_file = $constraints_file"
} else {
    puts "ERROR: constraints_file is NOT defined"
}


# QRC technology files
set QRC_MAX \
    /asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4/PEX/QRC/10M_2Mx_6Cx_2Ix_LBthick/FuncRCmax/qrcTechFile

set QRC_MIN \
    /asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4/PEX/QRC/10M_2Mx_6Cx_2Ix_LBthick/FuncRCmin/qrcTechFile

create_rc_corner \
    -name RC_MAX \
    -temperature 125 \
    -qrc_tech $QRC_MAX

create_rc_corner \
    -name RC_MIN \
    -temperature 125 \
    -qrc_tech $QRC_MIN
    
#################################################################################
# LIBRARY SET
#################################################################################

create_library_set \
    -name LIBSET_SLOW \
    -timing [list $TIMING_LIB]

#################################################################################
# TIMING CONDITION
#################################################################################

create_timing_condition \
    -name TC_SLOW \
    -library_sets [list LIBSET_SLOW]

#################################################################################
# RC CORNER
#################################################################################

create_rc_corner \
    -name RC_DEFAULT \
    -temperature 125

#################################################################################
# DELAY CORNER
#################################################################################

create_delay_corner \
    -name DELAY_SLOW \
    -timing_condition TC_SLOW \
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
    -name VIEW_SLOW \
    -constraint_mode FUNC \
    -delay_corner DELAY_SLOW

#################################################################################
# ACTIVE VIEWS
#################################################################################

set_analysis_view \
    -setup [list VIEW_SLOW] \
    -hold  [list VIEW_SLOW]