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

proc update_freq {freq constraints_file} {
  set period [expr {(1.0/$freq)*1000.0}]
  set constraints_file_handler [open $constraints_file w]
  puts -nonewline $constraints_file_handler {create_clock -period }
  puts -nonewline $constraints_file_handler $period 
  puts $constraints_file_handler { [get_ports $clock_signal]}
  close $constraints_file_handler
}