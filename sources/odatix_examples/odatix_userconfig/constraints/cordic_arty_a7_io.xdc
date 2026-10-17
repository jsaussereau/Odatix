##############################################
# IO placement for the CORDIC example
# Board: Digilent Arty A7-100T (xc7a100t-csg324-1)
##############################################
#
# Read on top of the timing constraint Odatix generates itself, which only
# holds the "create_clock" of the frequency being tried. See the "constraints"
# key of the "_settings.yml" of Example_Cordic_sv / Example_Cordic_vhdl.
#
# Scoped to "pnr": placing a pin has no effect on what synthesis produces, and
# an unplaceable pin should not make an fmax search fail.
#
# Only the four scalar ports are pinned, because they are the only ones a board
# actually has a place for. The datapath of the CORDIC is 3*WIDTH+32 bits wide
# -- 80 pins at the default WIDTH of 16 -- which no header on the Arty can
# carry. Those ports are left for the placer to assign anywhere in the package,
# which is what you want out of a design space exploration: the point is to
# measure the core, not to build a board.
#
# This file is shared by the SystemVerilog and the VHDL versions of the CORDIC:
# their port names are identical.

# 100 MHz oscillator. Odatix drives the frequency of "create_clock" itself, so
# nothing here says how fast the design runs -- E3 is just where the pin is.
set_property -dict {PACKAGE_PIN E3 IOSTANDARD LVCMOS33} [get_ports clock]

# btn[0]
set_property -dict {PACKAGE_PIN D9 IOSTANDARD LVCMOS33} [get_ports reset]

# sw[0]
set_property -dict {PACKAGE_PIN A8 IOSTANDARD LVCMOS33} [get_ports i_valid]

# led[0]
set_property -dict {PACKAGE_PIN H5 IOSTANDARD LVCMOS33} [get_ports o_valid]

# Every remaining port still needs an IO standard, or the placer refuses to
# assign it. "-quiet" keeps this file usable on a configuration whose WIDTH
# leaves one of the buses empty.
foreach port [get_ports -quiet {i_x[*] i_y[*] i_angle[*] o_x[*] o_y[*]}] {
  set_property IOSTANDARD LVCMOS33 $port
}
