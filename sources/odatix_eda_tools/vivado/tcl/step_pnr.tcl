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

# Step "pnr" of the "staged" flow: place & route, starting from the checkpoint
# the synthesis step left behind.
#
# The reports written here replace the post-synthesis estimates with the real
# numbers, so a run stopped at this step ("--until pnr") exports implemented
# results without spending time on a bitstream.

if {[catch {

    set signature "<grey>\[step_pnr.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    odatix_single_thread $signature

    report_progress 0 $synth_statusfile

    odatix_open_checkpoint "post_synth.dcp" $signature "synthesis"

    # Constraints scoped to place & route: an IO placement, a floorplan. They
    # are read here rather than with the synthesis ones so that a constraint
    # meant for implementation does not change what the synthesis step produced.
    odatix_read_user_constraints pnr read_xdc $signature

    report_progress 10 $synth_statusfile

    ######################################
    # Place and route
    ######################################

    # The strategy is the flow's (see odatix_vivado_implement).
    if {![odatix_vivado_implement $signature $synth_statusfile 10 90]} {
        exit -1
    }

    report_progress 90 $synth_statusfile

    ######################################
    # Report and hand over
    ######################################
    odatix_write_reports "pnr" $signature
    report_progress 95 $synth_statusfile

    odatix_write_checkpoint "post_route.dcp" $signature

    report_progress 100 $synth_statusfile
    odatix_step_done "pnr" $signature

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
