#################################################################################
# AMS C35 2.2V - MMMC SETUP
#################################################################################

set PDK_PATH \
    /asic/pdk/ams/AMS_410_CDS

set TIMING_LIB \
    $PDK_PATH/liberty/c35_2.2V/c35_CORELIB_WC.lib

set SDC_FILE \
    $constraints_file

if {![file exists $SDC_FILE]} {
    error "SDC file not found: $SDC_FILE"
}


#################################################################################
# QRC
#################################################################################

set QRC_WORST \
    $PDK_PATH/assura/c35b4/c35b4/RCX-worst/qrcTechFile

set QRC_BEST \
    $PDK_PATH/assura/c35b4/c35b4/RCX-best/qrcTechFile


#################################################################################
# LIBRARY SET
#################################################################################

create_library_set \
    -name LIBSET_WC \
    -timing [list $TIMING_LIB]


#################################################################################
# TIMING CONDITION
#################################################################################

create_timing_condition \
    -name TC_WC \
    -library_sets [list LIBSET_WC]


#################################################################################
# RC CORNERS
#################################################################################

create_rc_corner \
    -name RC_WORST \
    -qrc_tech $QRC_WORST

create_rc_corner \
    -name RC_BEST \
    -qrc_tech $QRC_BEST


#################################################################################
# DELAY CORNERS
#################################################################################

create_delay_corner \
    -name DELAY_WC \
    -timing_condition TC_WC \
    -rc_corner RC_WORST

create_delay_corner \
    -name DELAY_BEST \
    -timing_condition TC_WC \
    -rc_corner RC_BEST


#################################################################################
# CONSTRAINT MODE
#################################################################################

create_constraint_mode \
    -name FUNC \
    -sdc_files [list $SDC_FILE]


#################################################################################
# ANALYSIS VIEWS
#################################################################################

create_analysis_view \
    -name VIEW_SETUP \
    -constraint_mode FUNC \
    -delay_corner DELAY_WC

create_analysis_view \
    -name VIEW_HOLD \
    -constraint_mode FUNC \
    -delay_corner DELAY_BEST


#################################################################################
# ACTIVE VIEWS
#################################################################################

set_analysis_view \
    -setup [list VIEW_SETUP] \
    -hold  [list VIEW_HOLD]