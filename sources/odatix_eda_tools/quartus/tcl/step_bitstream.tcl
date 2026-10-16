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


# Step "bitstream": the programming file (.sof) of the fitted design.
#
# This step produces no metric of its own, which is exactly why it is a step of
# its own: it is worth running only on the implementations picked from the
# results of the previous ones. Quartus writes a programming file only for a
# design whose every pin has a location and an I/O standard: see
# odatix_quartus_assemble.

if {[catch {

    set signature "<grey>\[step_bitstream.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/quartus_common.tcl

    report_progress 0 $synth_statusfile

    if {![odatix_quartus_has_snapshot fit]} {
        puts "$signature <bold><red>error: no fitted design in the project<end>"
        puts "$signature <cyan>note: this step continues the \"pnr\" step, which has to run first<end>"
        exit -1
    }
    odatix_quartus_open $signature
    report_progress 20 $synth_statusfile

    set succeeded [odatix_quartus_assemble $signature]
    odatix_quartus_close
    if {!$succeeded} {
        exit -1
    }

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
