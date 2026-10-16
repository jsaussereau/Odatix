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

# The clock period LibreLane runs with. It is not written in config.json: the
# runs read it back from this file and give it on their command line (see
# odatix_librelane_overrides), so that config.json is written once per job and
# every iteration of an fmax search only rewrites this file.
#
# The other constraints are LibreLane's own (its base.sdc): input and output
# delays, driving cells, loads and derating of the PDK.

proc update_freq {freq constraints_file} {
  # An RTL analysis has no frequency (0): it does not time the design, but
  # LibreLane needs a clock period all the same
  if {$freq <= 0} {
    set freq 100
  }
  set clock_period [expr {1000.0 / $freq}]
  set f [open $constraints_file w]
  puts $f "{\"CLOCK_PERIOD\": $clock_period}"
  close $f
}
