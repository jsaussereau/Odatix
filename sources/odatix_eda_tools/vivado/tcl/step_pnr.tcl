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
    if {[catch {
        place_design -directive Explore
    } errmsg]} {
        puts "$signature <bold><red>error: failed design place<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        exit -1
    }
    report_progress 30 $synth_statusfile

    if {[catch {
        phys_opt_design -retime -rewire -critical_pin_opt -placement_opt -critical_cell_opt
    } errmsg]} {
        puts "$signature <bold><red>error: failed physical opt, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 40 $synth_statusfile

    if {[catch {
        route_design -directive AggressiveExplore
    } errmsg]} {
        puts "$signature <bold><red>error: failed design route, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        exit -1
    }
    if {[catch {
        puts "$signature <cyan>report_route_status:<end>"
        report_route_status
    } errmsg]} {
        puts "$signature <bold><red>error: failed report_route_status, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
    }
    report_progress 60 $synth_statusfile

    if {[catch {
        place_design -post_place_opt
    } errmsg]} {
        puts "$signature <bold><red>error: failed post-place opt, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 70 $synth_statusfile

    if {[catch {
        phys_opt_design -retime -routing_opt
    } errmsg]} {
        puts "$signature <bold><red>error: failed physical opt, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 80 $synth_statusfile

    if {[catch {
        route_design -directive NoTimingRelaxation
    } errmsg]} {
        puts "$signature <bold><red>error: failed design route, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
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
