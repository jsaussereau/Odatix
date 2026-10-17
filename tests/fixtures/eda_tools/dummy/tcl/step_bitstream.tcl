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

# Step "bitstream" of the dummy "staged" flow: bitstream generation.

if {[catch {

    set signature "<grey>\[step_bitstream.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    puts "$signature <yellow>warning: this is a dummy script, nothing is being done here!<end>"
    puts "$signature dummy bitstream generation for $lib_name"

    require_checkpoint post_route.chk $signature

    simulate_work 2 $synth_statusfile

    write_checkpoint design.bit $signature
    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    exit -1
}
