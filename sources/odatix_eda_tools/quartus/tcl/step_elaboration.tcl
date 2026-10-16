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


# Step "elaboration": analysis & elaboration of the RTL only.
#
# It takes seconds where a compilation takes minutes, and tells which
# configurations of a design space do not even elaborate: stop a run here with
# "--until elaboration". Quartus gives no estimate of an elaborated design, so
# this step exports no metric.
#
# Nothing is handed over to the synthesis step: synthesis starts again from the
# RTL, and creates the project again.

if {[catch {

    set signature "<grey>\[step_elaboration.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/quartus_common.tcl

    report_progress 0 $synth_statusfile

    odatix_quartus_create_project $signature
    report_progress 10 $synth_statusfile

    set succeeded [odatix_quartus_run syn "--analysis_and_elaboration" $signature]
    odatix_quartus_close
    if {!$succeeded} {
        exit -1
    }

    report_progress 100 $synth_statusfile
    odatix_step_done "elaboration" $signature

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
