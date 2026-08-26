#################################################################################
# GLOBALFOUNDRIES 22FDX - GENUS SETUP
#################################################################################

#-----------------------------------------------------------------------------
# TECHNOLOGY PATHS
#-----------------------------------------------------------------------------
set ::LIB_TYPE GF_22nm

set PDK_PATH /asic/pdk/globalfoundries/22FDX-PLUS/V1.0_3.4

set LIB_ROOT /asic/ip/DesignWare_logic_libs/globalfoundaries22nhsp/32hd116/hdl/lvt/2.00a

set LIB_PATH $LIB_ROOT/liberty/logic_synth_lvf

set CELL_LEF_PATH $LIB_ROOT/lef/5.8

#-----------------------------------------------------------------------------
# SEARCH PATHS
#-----------------------------------------------------------------------------

set LIB_SEARCH_PATHS [list]

lappend LIB_SEARCH_PATHS .
lappend LIB_SEARCH_PATHS $LIB_PATH

set_db init_lib_search_path $LIB_SEARCH_PATHS


#-----------------------------------------------------------------------------
# TIMING LIBRARIES
#-----------------------------------------------------------------------------

#set LIBS [list]
#lappend LIBS gf22nspllogl32hdl116f_SSG_0P72V_0P00V_0P60V_M1P00V_125C.lib.gz

#-----------------------------------------------------------------------------
# READ TIMING LIBRARIES
#-----------------------------------------------------------------------------

#foreach lib $LIBS {
#    read_libs $lib
#}
#if {$synth_mode eq "physical"} {
#    read_mmmc scripts/genus_mmmc.tcl
#} else {
#    foreach lib $LIBS {
#        read_libs $lib
#    }
#}

read_mmmc scripts/genus_mmmc.tcl

#-----------------------------------------------------------------------------
# PHYSICAL LIBRARIES
#-----------------------------------------------------------------------------
set TECH_LEF_PATH $PDK_PATH/PlaceRoute/Innovus/Techfiles/10M_2Mx_6Cx_2Ix_LB

set LEFS [list]

# Technology / routing stack
lappend LEFS $TECH_LEF_PATH/22FDSOI_10M_2Mx_6Cx_2Ix_LB_116cpp_tech.lef

# Standard placement-site definitions
lappend LEFS $PDK_PATH/PlaceRoute/Innovus/Techfiles/22fdsoi_standard_site.lef

# Standard-cell physical library
lappend LEFS $CELL_LEF_PATH/gf22nspllogl32hdl116f.lef


#-----------------------------------------------------------------------------
# READ PHYSICAL LIBRARIES
#-----------------------------------------------------------------------------

read_physical -lefs $LEFS


#################################################################################
# HDL / NETLIST OPTIONS
#################################################################################

# Bus naming
#set_db hdl_bus_naming_style {%s_%d}

# Preserve hierarchy
#set_db preserve_hierarchy true

# Internal buses
#set_db hdl_track_filename_row_col true