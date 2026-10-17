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

# Step "pnr" of the dummy "staged" flow: place and route.

if {[catch {

    set signature "<grey>\[step_pnr.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    puts "$signature <yellow>warning: this is a dummy script, nothing is being done here!<end>"
    puts "$signature dummy place and route for $lib_name"

    require_checkpoint post_synth.chk $signature

    simulate_work 2 $synth_statusfile

    write_checkpoint post_route.chk $signature
    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    exit -1
}
