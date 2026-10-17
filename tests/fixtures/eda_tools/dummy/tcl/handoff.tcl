# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

# What the dummy synthesis hands over to a place & route run ("odatix pnr").
#
# A real tool writes these files itself and then calls odatix_publish_handoff to
# put them under the names Odatix looks for (see the _common settings.tcl). The
# dummy tool has no netlist to write, so it fabricates one: enough for a dummy
# place & route to read it back and for the whole chain to be exercised without
# a licence.

proc write_handoff {{signature ""}} {
    global netlist_file sdc_file sdf_file
    global top_level_module clock_signal target_frequency lib_name

    file mkdir [file dirname $netlist_file]

    set handler [open $netlist_file w]
    puts $handler "// dummy netlist written by Odatix"
    puts $handler "// library: $lib_name"
    puts $handler "module $top_level_module (input $clock_signal);"
    puts $handler "endmodule"
    close $handler

    set handler [open $sdc_file w]
    if {$target_frequency > 0} {
        set period [expr {1000.0 / $target_frequency}]
    } else {
        set period 10.0
    }
    puts $handler "create_clock -name $clock_signal -period $period \[get_ports $clock_signal\]"
    close $handler

    set handler [open $sdf_file w]
    puts $handler "(DELAYFILE (DESIGN \"$top_level_module\"))"
    close $handler

    puts "$signature published <cyan>netlist, sdc and sdf<end> for place & route"
}
