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

# Step "netlist" of an fmax search: the synthesis that gets handed over.
#
# The search leaves the constraints file at the highest frequency it found the
# timing met at, but the design left in memory is the one of its last iteration,
# which may well be a violating one. So this step synthesizes once more, at the
# frequency the search converged to, and publishes that netlist for
# "odatix pnr". Its reports replace the search's, for the same frequency.
#
# The RTL has been analyzed by analyze_script.tcl in the same process.

if {[catch {

    set signature "<grey>\[step_fmax_netlist.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    set basename ${top_level_module}

    report_progress 0 $synth_statusfile

    odatix_dc_elaborate $signature

    report_progress 10 $synth_statusfile

    odatix_write_ddc "${basename}.ddc" $signature

    set frequency [odatix_dc_constrain $signature]

    report_progress 15 $synth_statusfile

    odatix_dc_compile $signature

    report_progress 80 $synth_statusfile

    odatix_write_ddc "${basename}_gates.ddc" $signature

    odatix_dc_reports $frequency $signature

    report_progress 90 $synth_statusfile

    odatix_dc_netlist $signature

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
