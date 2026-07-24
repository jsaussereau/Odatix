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
source scripts/settings.tcl

proc update_freq {freq constraints_file} {
    global clock_signal

#    if {$freq <= 0} {
#        error "Frequency must be greater than 0 MHz"
#    }

    set period_ns [expr {1000.0 / double($freq)}]

    set fp [open $constraints_file "w"]

    puts $fp "create_clock -name clk -period $period_ns \[get_ports $clock_signal\]"
    puts $fp "set_clock_uncertainty 0.1 \[get_clocks clk\]"

    close $fp

    puts "Generated constraints file: $constraints_file"
    puts "Clock port: $clock_signal"
    puts "Frequency: $freq MHz"
    puts "Period: $period_ns ns"
}