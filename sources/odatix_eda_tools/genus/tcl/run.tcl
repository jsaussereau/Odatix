#################################################################################
# Odatix - Genus Run Script
#################################################################################
#source scripts/settings.tcl
#source scripts/analyze_script.tcl
#source scripts/synth_script.tcl




#################################################################################

# SIMPLE GENUS TEST FLOW

#################################################################################

#################################################################################

# SETTINGS

#################################################################################

set TOP counter

set RTL_DIR "/net/users/mcirolinimic/Documents/stage/genus_develop/frontend/examples/counter_verilog"

set REPORT_DIR "./reports"
set NETLIST_DIR "./netlist"

file mkdir $REPORT_DIR
file mkdir $NETLIST_DIR

#################################################################################

# LIBRARIES

#################################################################################

set LIB_SEARCH_PATHS [list 
    . 
    /asic/pdk/ams/AMS_410_CDS/liberty/c35_1.8V 
]

set_db init_lib_search_path $LIB_SEARCH_PATHS

read_libs c35_CORELIB_WC.lib

#################################################################################

# READ RTL

#################################################################################

set verilog_files [glob $RTL_DIR/*.v]

puts "Verilog files:"
foreach file $verilog_files {
    puts " - $file"
}

read_hdl -language v2001 $verilog_files

#################################################################################

# ELABORATE

#################################################################################

elaborate $TOP

check_design

#################################################################################

# CONSTRAINTS

#################################################################################

create_clock -name clk_i -period 20 [get_ports clk_i]

set_input_delay 0.3 -clock clk_i [all_inputs]
set_output_delay 0.3 -clock clk_i [all_outputs]

#################################################################################

# SYNTHESIS

#################################################################################

syn_generic
syn_map
syn_opt

#################################################################################

# REPORTS

#################################################################################

report_timing > $REPORT_DIR/timing.rpt
report_area   > $REPORT_DIR/area.rpt
report_power  > $REPORT_DIR/power.rpt

#################################################################################

# NETLIST

#################################################################################

write_hdl > $NETLIST_DIR/counter_netlist.v

#################################################################################

# DONE

#################################################################################

puts "Synthesis completed successfully!"
exit
