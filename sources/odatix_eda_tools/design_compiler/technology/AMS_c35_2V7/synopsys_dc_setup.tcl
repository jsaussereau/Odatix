
#########
### Define Work Library Location
#########
#define_design_lib WORK -path "./work"

#########
### retrieve AMS directory path and SYNOPSYS path from the environement variables
#########

if {[catch {
    set AMSDIR [get_unix_variable AMS_C35_2V7]
} errmsg]} {
    set AMSDIR "/opt/ams/"
}

set SYNDIR [get_unix_variable SYNOPSYS]

#########
### set library paths
#########
set search_path	". $AMSDIR/synopsys/c35_2.7V /softs/kits/ams/AMS_410_CDS/synopsys/c35_2.7V/ $SYNDIR/libraries/syn $SYNDIR/dw/sim_ver"
set target_library "c35_CORELIB_WC.db c35_IOLIB_WC.db"

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
