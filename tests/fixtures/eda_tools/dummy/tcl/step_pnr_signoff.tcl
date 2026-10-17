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

# Step "signoff" of the dummy place & route flow.

if {[catch {

    set signature "<grey>\[step_pnr_signoff.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl
    source scripts/pnr_common.tcl

    puts "$signature <yellow>warning: this is a dummy script, nothing is being done here!<end>"
    puts "$signature dummy signoff for $lib_name"

    require_checkpoint post_route.chk $signature

    simulate_work 1 $synth_statusfile

    write_pnr_report power.rep [list "Dummy place & route" "Total Power: 12.5 mW"] $signature
    snapshot_pnr_reports signoff $signature
    write_checkpoint post_signoff.chk $signature
    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    exit -1
}
