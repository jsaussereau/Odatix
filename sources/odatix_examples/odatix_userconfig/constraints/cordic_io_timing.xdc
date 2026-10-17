##############################################
# IO timing budget for the CORDIC example
##############################################
#
# The companion of "cordic_arty_a7_io.xdc": that one says where the pins are,
# this one says what is expected of them in time.
#
# Scoped to "all", so both synthesis and place & route see it. Unlike a pin
# assignment, an IO budget changes what synthesis produces: without it the tool
# assumes the whole period is available at the boundary and under-constrains the
# first and last stages of the pipeline, which flatters the reported fmax.
#
# The delays are expressed as a fraction of the period Odatix is currently
# trying, read back from the clock it created, so that they follow an fmax
# search instead of fighting it: a budget frozen at, say, 2 ns would be 20% of
# the period at 100 MHz and 100% of it at 500 MHz, and the search would stop on
# the budget rather than on the design.

set cordic_clock [get_clocks -of_objects [get_ports clock]]
set cordic_period [get_property PERIOD $cordic_clock]

# 20% of the period for whatever drives the inputs, 20% for whatever the
# outputs drive.
set cordic_input_delay  [expr {0.2 * $cordic_period}]
set cordic_output_delay [expr {0.2 * $cordic_period}]

set_input_delay -clock $cordic_clock $cordic_input_delay \
  [get_ports -quiet {i_valid i_x[*] i_y[*] i_angle[*]}]

set_output_delay -clock $cordic_clock $cordic_output_delay \
  [get_ports -quiet {o_valid o_x[*] o_y[*]}]

# "reset" is asynchronous and never on a timing path worth reporting.
set_false_path -from [get_ports reset]
