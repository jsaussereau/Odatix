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


# "synthesis" step of a custom frequency synthesis: synthesizes the elaborated
# design, writes the reports the metrics are read from and exports the netlist
# "odatix pnr" starts from.

if {[catch {

    set signature "<grey>\[step_synthesis.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    report_progress 0 $synth_statusfile

    odatix_fc_open_lib $signature "elaborate"
    odatix_fc_start_from_elab $signature

    report_progress 10 $synth_statusfile

    set frequency [odatix_fc_constrain $signature]

    report_progress 15 $synth_statusfile

    odatix_fc_synthesize $signature

    report_progress 85 $synth_statusfile

    odatix_fc_save_block $top_level_module $signature
    odatix_fc_reports $frequency synthesis $signature

    report_progress 95 $synth_statusfile

    odatix_fc_netlist $signature

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
