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

#proc update_freq {freq constraints_file} {

#  set period_ns [expr {1000.0 / $freq}]

#  set fp [open $constraints_file w]

#  puts $fp "create_clock -name clock -period $period_ns \[get_ports clock\]"
#  puts $fp "set_input_delay 0.1 -clock clock \[all_inputs\]"
#  puts $fp "set_output_delay 0.1 -clock clock \[all_outputs\]"

#  close $fp

#}


source scripts/settings.tcl

proc update_freq {freq constraints_file} {

    global clock_signal
    global reset_signal

    set period_ns [expr {1000.0 / $freq}]

    set fp [open $constraints_file w]

    puts $fp "create_clock -name $clock_signal -period $period_ns \[get_ports $clock_signal\]"

    puts $fp "set_input_delay 0.1 -clock $clock_signal \[remove_from_collection \[all_inputs\] \[get_ports {$clock_signal $reset_signal}\]\]"

    puts $fp "set_output_delay 0.1 -clock $clock_signal \[all_outputs\]"

    close $fp
}

