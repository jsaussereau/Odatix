#################################################################################
# AMS C35 - MMMC SETUP
#################################################################################

#-----------------------------------------------------------------------------
# TIMING LIBRARY
#-----------------------------------------------------------------------------
set PDK_PATH /asic/pdk/ams/AMS_410_CDS

set LIB_WC  $PDK_PATH/liberty/c35_2.7V/c35_CORELIB_WC.lib
set LIB_TYP $PDK_PATH/liberty/c35_2.7V/c35_CORELIB_TYP.lib
set LIB_BC  $PDK_PATH/liberty/c35_2.7V/c35_CORELIB_BC.lib

#-----------------------------------------------------------------------------
# CONSTRAINT FILE
#-----------------------------------------------------------------------------

set SDC_FILE $constraints_file

if {![file exists $SDC_FILE]} {
    error "SDC file not found: $SDC_FILE"
}

set QRC_WORST $PDK_PATH/assura/c35b4/c35b4/RCX-worst/qrcTechFile
set QRC_BEST $PDK_PATH/assura/c35b4/c35b4/RCX-best/qrcTechFile

#-----------------------------------------------------------------------------
# LIBRARY SET
#-----------------------------------------------------------------------------

create_library_set \
    -name LIBSET_WC \
    -timing [list $LIB_WC]

create_library_set \
    -name LIBSET_TYP \
    -timing [list $LIB_TYP]

create_library_set \
    -name LIBSET_BC \
    -timing [list $LIB_BC]

#-----------------------------------------------------------------------------
# TIMING CONDITION
#-----------------------------------------------------------------------------

create_timing_condition \
    -name TC_WC \
    -library_sets [list LIBSET_WC]

create_timing_condition \
    -name TC_TYP \
    -library_sets [list LIBSET_TYP]

create_timing_condition \
    -name TC_BC \
    -library_sets [list LIBSET_BC]

#-----------------------------------------------------------------------------
# RC CORNER
#-----------------------------------------------------------------------------

create_rc_corner \
    -name RC_WORST \
    -qrc_tech $QRC_WORST

create_rc_corner \
    -name RC_BEST \
    -qrc_tech $QRC_BEST

#-----------------------------------------------------------------------------
# DELAY CORNER
#-----------------------------------------------------------------------------

create_delay_corner \
    -name DELAY_WORST \
    -timing_condition TC_WC \
    -rc_corner RC_WORST

create_delay_corner \
    -name DELAY_BEST \
    -timing_condition TC_BC \
    -rc_corner RC_BEST

#-----------------------------------------------------------------------------
# CONSTRAINT MODE
#-----------------------------------------------------------------------------

create_constraint_mode \
    -name FUNC \
    -sdc_files [list $SDC_FILE]

#-----------------------------------------------------------------------------
# ANALYSIS VIEW
#-----------------------------------------------------------------------------

create_analysis_view \
    -name VIEW_SETUP \
    -constraint_mode FUNC \
    -delay_corner DELAY_WORST

create_analysis_view \
    -name VIEW_HOLD \
    -constraint_mode FUNC \
    -delay_corner DELAY_BEST

#-----------------------------------------------------------------------------
# ACTIVE ANALYSIS VIEWS
#-----------------------------------------------------------------------------

set_analysis_view \
    -setup [list VIEW_SETUP] \
    -hold  [list VIEW_HOLD]