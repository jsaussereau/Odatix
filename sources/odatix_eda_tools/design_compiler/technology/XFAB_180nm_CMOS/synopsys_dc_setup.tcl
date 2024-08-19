#####################################################################
##     Initialization Setup file for Synopsys Design Compiler      ##
#####################################################################

#define_design_lib WORK -path "./work/design_compiler"

### retrieve Xfab directory path and SYNOPSYS path from the environement variables
set XKIT ~/xfab180n/XKIT
set XFABDIR $XKIT/xh018
set SYNDIR /imssofts/softs/Synopsys/DesignCompiler/2013.03-SP5

### set library paths
set search_path	". $XKIT/x_all/cadence/XFAB_AMS_RefKit-cadence_IC61/v2_5_1/trunk/pdk/xh018/diglibs/D_CELLS_HD/v3_0/liberty_LPMOS/v3_0_0/PVT_1_80V_range $SYNDIR/libraries/syn $SYNDIR/dw/sim_ver ../rtl ./db ./"
##set symbol_library "D_CELLS_HD_LPMOS_typ_1_80V_25C.sdb" => cannot find sdb file, so this line is commented so that the generic symbols from synopsys installation are used
set target_library "D_CELLS_HD_LPMOS_typ_1_80V_25C.db"

# set synthetic_library dw_foundation.sldb 
set link_library "* $target_library $synthetic_library"

### set bus naming style for compliance between .sdf and post syn .vhdl
set sdfout_no_edge  true
#set verilogout_equation	false
#set verilogout_no_tri	true 
#set verilogout_single_bit  false

set hdlout_internal_busses true     
set vhdlout_single_bit user
set vhdlout_preserve_hierarchical_types user
set bus_inference_style "%s_%d_"  
set bus_naming_style    "%s_%d"
set write_name_nets_same_as_ports true

#puts "USE: set_fix_multiple_port_nets -all [all_designs]"
