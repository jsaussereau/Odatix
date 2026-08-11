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

# Step "bitstream" of the "staged" flow: generate the bitstream from the routed
# checkpoint.
#
# This step produces no metric of its own, which is exactly why it is a step of
# its own: it is worth running only on the implementations picked from the
# results of the previous ones.

if {[catch {

    set signature "<grey>\[step_bitstream.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    odatix_single_thread $signature

    report_progress 0 $synth_statusfile

    odatix_open_checkpoint "post_route.dcp" $signature "pnr"
    report_progress 20 $synth_statusfile

    ######################################
    # Write bitstream
    ######################################
    set bitstream_file [file join $result_path "${top_level_module}.bit"]
    if {[catch {
        write_bitstream -force $bitstream_file
    } errmsg]} {
        puts "$signature <bold><red>error: failed writing bitstream<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        exit -1
    }
    puts "$signature <cyan>wrote bitstream $bitstream_file<end>"

    report_progress 100 $synth_statusfile
    odatix_step_done "bitstream" $signature

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}
