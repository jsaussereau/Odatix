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


# Source the scripts given as arguments, in order:
#
#   quartus_sh -t scripts/run.tcl scripts/init_script.tcl scripts/analyze_script.tcl ...
#
# quartus_sh runs a single script, where Vivado sources as many as it is given
# ("-source" once per script): this makes the scripts of a job the same with
# both tools.

if {[info exists quartus(args)]} {
    set odatix_scripts $quartus(args)
} else {
    set odatix_scripts $argv
}

foreach odatix_script $odatix_scripts {
    source $odatix_script
}
