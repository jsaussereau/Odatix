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


# Step "pnr": fits the design the synthesis step left in the project, then
# analyzes its timing and its power.
#
# The reports written here replace the post-synthesis estimates with the real
# numbers, so a run stopped at this step ("--until pnr") exports implemented
# results without spending time on a programming file.

if {[catch {

    set signature "<grey>\[step_pnr.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/quartus_common.tcl

    report_progress 0 $synth_statusfile

    if {![odatix_quartus_has_snapshot syn]} {
        puts "$signature <bold><red>error: no synthesized design in the project<end>"
        puts "$signature <cyan>note: this step continues the \"synthesis\" step, which has to run first<end>"
        exit -1
    }
    odatix_quartus_open $signature
    report_progress 5 $synth_statusfile

    set succeeded [odatix_quartus_implement $signature $synth_statusfile 5 85]
    if {$succeeded} {
        set succeeded [odatix_quartus_report_implementation $signature $synth_statusfile 85 98]
    }
    odatix_quartus_close
    if {!$succeeded} {
        exit -1
    }

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
