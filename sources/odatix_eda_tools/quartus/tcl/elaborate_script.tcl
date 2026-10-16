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


# RTL analysis ("odatix analyze"): analysis & elaboration of the design, which
# reports what does not elaborate in seconds, without synthesizing anything.

if {[catch {

    source scripts/settings.tcl
    source scripts/quartus_common.tcl

    set signature "<grey>\[elaborate_script.tcl\]<end>"

    odatix_quartus_create_project $signature 1
    set succeeded [odatix_quartus_run syn "--analysis_and_elaboration" $signature]
    odatix_quartus_close

    report_progress 100 $synth_statusfile
    if {!$succeeded} {
        puts "$signature <bold><red>error: Quartus RTL analysis terminated with errors<end>"
        exit -1
    }

} gblerrmsg ]} {
    puts "$signature <bold><red>error: Quartus RTL analysis terminated with errors<end>"
    puts "$signature tool says -> $gblerrmsg"
    report_progress 100 $synth_statusfile
    exit -1
}
