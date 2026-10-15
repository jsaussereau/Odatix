#################################################################################
# AMS C35 (1.8V CORELIB, 4 metal layers) - INNOVUS TECHNOLOGY SETUP
#################################################################################
#
# Sourced by step_init.tcl before init_design. It declares the physical and
# timing views of the technology; step_init.tcl adds the netlist and runs
# init_design. The timing constraints are those the synthesis wrote
# ($source_sdc), read through the MMMC setup below.

#-----------------------------------------------------------------------------
# TECHNOLOGY PATHS
#-----------------------------------------------------------------------------
set AMS_PATH  /asic/pdk/ams/AMS_410_CDS
set LEF_PATH  $AMS_PATH/cds/HK_C35/LEF/c35b4
set CAP_PATH  $AMS_PATH/cds/HK_C35/LEF/encounter
set LIB_PATH  $AMS_PATH/liberty/c35_1.8V

#-----------------------------------------------------------------------------
# PHYSICAL VIEWS
#-----------------------------------------------------------------------------
set init_lef_file [list \
    $LEF_PATH/c35b4.lef \
    $LEF_PATH/CORELIB.lef \
]

set init_pwr_net vdd!
set init_gnd_net gnd!

# Standard cell site of the core rows
set odatix_core_site standard

#-----------------------------------------------------------------------------
# TIMING VIEWS (MMMC)
#-----------------------------------------------------------------------------
set mmmc_file [file join $result_path mmmc.tcl]
file mkdir [file dirname $mmmc_file]
set fp [open $mmmc_file w]
puts $fp "create_library_set -name libs_wc -timing [list $LIB_PATH/c35_CORELIB_WC.lib]"
puts $fp "create_library_set -name libs_bc -timing [list $LIB_PATH/c35_CORELIB_BC.lib]"
puts $fp "create_rc_corner -name rc_worst -cap_table $CAP_PATH/c35b4-worst.capTable"
puts $fp "create_rc_corner -name rc_best -cap_table $CAP_PATH/c35b4-best.capTable"
puts $fp "create_delay_corner -name corner_wc -library_set libs_wc -rc_corner rc_worst"
puts $fp "create_delay_corner -name corner_bc -library_set libs_bc -rc_corner rc_best"
puts $fp "create_constraint_mode -name func -sdc_files [list [file normalize $source_sdc]]"
puts $fp "create_analysis_view -name view_setup -constraint_mode func -delay_corner corner_wc"
puts $fp "create_analysis_view -name view_hold -constraint_mode func -delay_corner corner_bc"
puts $fp "set_analysis_view -setup view_setup -hold view_hold"
close $fp

set init_mmmc_file $mmmc_file

#-----------------------------------------------------------------------------
# FLOORPLAN
#-----------------------------------------------------------------------------
# Horizontal then vertical layer of the core power ring
set odatix_ring_layers {MET3 MET4}

#-----------------------------------------------------------------------------
# CLOCK TREE SYNTHESIS
#-----------------------------------------------------------------------------
# The library flags no cell as a balanced clock buffer: name them for CCOpt.
set odatix_cts_buffers   {CLKBU2 CLKBU4 CLKBU6 CLKBU8 CLKBU12 CLKBU15}
set odatix_cts_inverters {CLKIN1 CLKIN2 CLKIN3 CLKIN4 CLKIN6 CLKIN8 CLKIN10 CLKIN12 CLKIN15}
