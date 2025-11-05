
#########
### Define Work Library Location
#########
#define_design_lib WORK -path "./work"

#########
### retrieve AMS directory path and SYNOPSYS path from the environement variables
#########
set AMSDIR [get_unix_variable AMS_H18_5V0]
set SYNDIR [get_unix_variable SYNOPSYS]

#########
### set library paths
#########
set search_path	". $AMSDIR /opt/ams/synopsys/h18_5.0V /softs/kits/ams/AMS_411_CDS/synopsys/h18_5.0V/ $SYNDIR/libraries/syn $SYNDIR/dw/sim_ver ../rtl ./db ./"
# set symbol_library "h18_CORELIB.sdb"
set target_library "h18_CORELIB_TYP.db"

# set synthetic_library dw_foundation.sldb 
set link_library "* $target_library $synthetic_library"

#########
### set bus naming style for compliance between .sdf and post syn .vhdl
#########
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
