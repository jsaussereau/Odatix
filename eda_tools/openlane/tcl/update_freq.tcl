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
  # Get new period
  set clock_period [expr {1000.0 / $freq}]
  
  # Read constraints file
  set file [open $constraints_file r]
  set json_data [read $file]
  close $file

  # Change CLOCK_PERIOD
  set updated_json_data [regsub -all {("CLOCK_PERIOD":\s*)[0-9.]+} $json_data "\\1$clock_period"]

  # Save new constraints
  set file [open $constraints_file w]
  puts $file $updated_json_data
  close $file
}
