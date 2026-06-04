set MAIN_CLOCK_NAME clock
set MAIN_RST_NAME reset

set period_clk [format "%.2f" [expr 1000.0 / $freq_mhz]] ;# (100 ns = 10 MHz) (10 ns = 100 MHz) (2 ns = 500 MHz) (1 ns = 1 GHz)
set clk_uncertainty 0.05 ;# ns (“a guess”)
set clk_latency 0.10 ;# ns (“a guess”)
set clk_skew 0.10 ;# ns (“a guess”)
set in_delay 0.30 ;# ns
set out_delay 0.30;#ns 
set out_load 0.045 ;#pF 
set slew "146 164 264 252" ;#minimum rise, minimum fall, maximum rise and maximum fall 
set slew_min_rise 0.146 ;# ns
set slew_min_fall 0.164 ;# ns
set slew_max_rise 0.264 ;# ns
set slew_max_fall 0.252 ;# ns







#################################################################################
## DEFINE VARS
#################################################################################
set sdc_version 1.5
current_design ${DESIGN}

#################################################################################
## IDEAL NETS
#################################################################################
set_ideal_net [get_nets ${MAIN_CLOCK_NAME}]
set_ideal_net [get_nets ${MAIN_RST_NAME}]

#################################################################################
## CLOCK
#################################################################################
create_clock -name ${MAIN_CLOCK_NAME} -period $period_clk [get_ports ${MAIN_CLOCK_NAME}]
set_clock_uncertainty ${clk_uncertainty} [get_clocks ${MAIN_CLOCK_NAME}]
set_clock_skew ${clk_skew} [get_clocks ${MAIN_CLOCK_NAME}]
set_clock_latency ${clk_latency} [get_clocks ${MAIN_CLOCK_NAME}]

#################################################################################
## INPUT PINS SECTION
#################################################################################
set_input_delay -clock [get_clocks ${MAIN_CLOCK_NAME}] ${in_delay} [remove_from_collection [all_inputs] "[get_ports ${MAIN_CLOCK_NAME}]"]

#################################################################################
## OUTPUT PINS SECTION
#################################################################################
set_output_delay -clock [get_clocks ${MAIN_CLOCK_NAME}] ${out_delay} [all_outputs]

#################################################################################
# DEFAULT OUTPUT PIN LOAD
#################################################################################
set_load -pin_load ${out_load} [get_ports [all_outputs]]

#################################################################################
## DEFAULT DRIVER 
##################################################################################

set_input_transition -rise -min $slew_min_rise [remove_from_collection [all_inputs] "[get_ports ${MAIN_CLOCK_NAME}]"]
set_input_transition -fall -min $slew_min_fall [remove_from_collection [all_inputs] "[get_ports ${MAIN_CLOCK_NAME}]"]

set_input_transition -rise -max $slew_max_rise [remove_from_collection [all_inputs] "[get_ports ${MAIN_CLOCK_NAME}]"]
set_input_transition -fall -max $slew_max_fall [remove_from_collection [all_inputs] "[get_ports ${MAIN_CLOCK_NAME}]"]
