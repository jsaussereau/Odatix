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

# Step "signoff" of the Innovus place & route flow.

if {[catch {

    set signature "<grey>\[step_signoff.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/pnr_common.tcl

    odatix_restore post_route $signature

    # The design database does not keep the variables of the technology script.
    source $script_path/technology_setup.tcl

    verify_drc
    verifyConnectivity

    # Hand the routed design on to whatever comes next. The GDS needs the
    # stream map of the technology ($odatix_gds_map, set by its script).
    if {[info exists odatix_gds_map] && [file exists $odatix_gds_map]} {
        streamOut [file join $result_path design.gds] -mapFile $odatix_gds_map -stripes 1 -units 1000 -mode ALL
    } else {
        puts "$signature <cyan>note: no stream map in the technology script (odatix_gds_map), no GDS written<end>"
    }

    odatix_write_reports "signoff" $signature
    odatix_save post_signoff $signature
    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    exit -1
}
