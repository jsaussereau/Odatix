#################################################################################
# AMS H18 1.8V - MMMC SETUP
#################################################################################

set PDK_PATH /asic/pdk/ams/AMS_411_CDS

set LIB_WC  $PDK_PATH/liberty/h18_1.2V/h18_CORELIB_WC.lib
set LIB_TYP $PDK_PATH/liberty/h18_1.2V/h18_CORELIB_TYP.lib
set LIB_BC  $PDK_PATH/liberty/h18_1.2V/h18_CORELIB_BC.lib


set SDC_FILE $constraints_file

if {![file exists $SDC_FILE]} {
    error "SDC file not found: $SDC_FILE"
}


#################################################################################
# QRC
#################################################################################

set QRC_FILE \
    $PDK_PATH/assura/h18a4/h18a4/QRC/qrcTechFile


#################################################################################
# LIBRARY SET
#################################################################################

create_library_set \
    -name LIBSET_WC \
    -timing [list $LIB_WC]

create_library_set \
    -name LIBSET_TYP \
    -timing [list $LIB_TYP]

create_library_set \
    -name LIBSET_BC \
    -timing [list $LIB_BC]


#################################################################################
# TIMING CONDITION
#################################################################################

create_timing_condition \
    -name TC_WC \
    -library_sets [list LIBSET_WC]

create_timing_condition \
    -name TC_TYP \
    -library_sets [list LIBSET_TYP]

create_timing_condition \
    -name TC_BC \
    -library_sets [list LIBSET_BC]


#################################################################################
# RC CORNER
#################################################################################

create_rc_corner \
    -name RC_DEFAULT \
    -qrc_tech $QRC_FILE


#################################################################################
# DELAY CORNER
#################################################################################

create_delay_corner \
    -name DELAY_WORST \
    -timing_condition TC_WC \
    -rc_corner RC_DEFAULT

create_delay_corner \
    -name DELAY_BEST \
    -timing_condition TC_BC \
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
    -delay_corner DELAY_WORST

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