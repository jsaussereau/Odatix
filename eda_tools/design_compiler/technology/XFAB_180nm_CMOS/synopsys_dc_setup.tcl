#####################################################################
##     Initialization Setup file for Synopsys Design Compiler      ##
#####################################################################

set X_DIR [get_unix_variable X_DIR]
set SYNOPSYS [get_unix_variable SYNOPSYS]

#set search_path	". $X_DIR/xh018/diglibs/IO_CELLS_3V/v2_1/cadence_IC61/v2_1_2/IO_CELLS_3V $X_DIR/xh018/diglibs/IO_CELLS_F3V/v2_1/cadence_IC61/v2_1_2/IO_CELLS_F3V $X_DIR/xh018/diglibs/D_CELLS_HD/v3_0/cadence_IC61/v3_0_1/D_CELLS_HD $SYNOPSYS/libraries/syn $SYNOPSYS/dw/sim_ver"

#set search_path	"."


#set target_library "*.db"

#set symbol_library "D_CELLS_HD.sdb"

# set synthetic_library dw_foundation.sldb 
set link_library "* $target_library $synthetic_library"

define_design_lib WORK -path ./work

set sdfout_no_edge  true
set verilogout_equation	false
set verilogout_no_tri	true 
set verilogout_single_bit  false
set verilogout_show_unconnected_pins true
set hdlout_internal_busses true     
set bus_inference_style "%s\[%d\]"  
set bus_naming_style    "%s\[%d\]"
set write_name_nets_same_as_ports true

puts "USE: set_fix_multiple_port_nets -all [all_designs]"
puts "change_names -rules verilog -hierarchy -verbose > change_names.v"
puts "change_names -rules vhdl -hierarchy -verbose > change_names.vhd"



