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


# The timing constraint of the job, rewritten for every frequency an fmax search
# tries. It is read by Quartus executables that know nothing of the variables
# of these scripts: the clock is written by its name.

source scripts/settings.tcl

proc update_freq {freq constraints_file} {
    global clock_signal
    set period [expr {1000.0 / $freq}]
    set f [open $constraints_file w]
    puts $f "create_clock -name {$clock_signal} -period $period \[get_ports {$clock_signal}\]"
    close $f
}
