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


# Step "synthesis": creates the project and synthesizes the design.
#
# The reports written here are post-synthesis estimates: utilization from
# synthesis, timing from the synthesized netlist with a rough delay model. A run
# stopped at this step ("--until synthesis") still exports metrics, which is
# what makes it possible to pick the configurations worth implementing. The
# synthesized design stays in the project database, where the next step finds
# it.

if {[catch {

    set signature "<grey>\[step_synthesis.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/quartus_common.tcl

    report_progress 0 $synth_statusfile

    odatix_quartus_create_project $signature
    report_progress 5 $synth_statusfile

    set succeeded [odatix_quartus_synthesize $signature $synth_statusfile 5 80]
    if {$succeeded} {
        set succeeded [odatix_quartus_report_synthesis $signature]
    }
    odatix_quartus_close
    if {!$succeeded} {
        exit -1
    }

    report_progress 100 $synth_statusfile
    odatix_step_done "synthesis" $signature

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
