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

# Step "synthesis": constraints, compilation and reports.
#
# It continues the "elaborate" step through its database instead of reading the
# RTL again, and leaves the mapped design behind for the "netlist" step. This is
# the step metrics are read from: a run stopped here ("--until synthesis") still
# exports area, timing and power.

if {[catch {

    set signature "<grey>\[step_synthesis.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    report_progress 0 $synth_statusfile

    odatix_dc_setup $signature
    odatix_read_ddc "${top_level_module}.ddc" $signature "elaborate"

    report_progress 10 $synth_statusfile

    set frequency [odatix_dc_constrain $signature]

    report_progress 15 $synth_statusfile

    odatix_dc_compile $signature

    report_progress 85 $synth_statusfile

    odatix_write_ddc "${top_level_module}_gates.ddc" $signature

    report_progress 90 $synth_statusfile

    odatix_dc_reports $frequency $signature

    report_progress 100 $synth_statusfile

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
