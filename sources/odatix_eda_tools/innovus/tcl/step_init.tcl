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

# Step "init" of the Innovus place & route flow.

if {[catch {

    set signature "<grey>\[step_init.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/pnr_common.tcl

    # Read the netlist the synthesis handed over, together with its constraints.
    odatix_require_source $signature

    # Technology setup. This is what you have to adapt to your PDK: the target
    # file of this tool copies your technology script into the job directory
    # (script_copy_enable / script_copy_source), and it is sourced here.
    if {[file exists $script_path/technology_setup.tcl]} {
        source $script_path/technology_setup.tcl
    } else {
        puts "$signature <bold><red>error: no technology_setup.tcl in this job<end>"
        puts "$signature <cyan>note: point script_copy_source at your Innovus technology script in the target file<end>"
        exit -1
    }

    set init_verilog $source_netlist
    set init_design_netlisttype "Verilog"
    set init_top_cell $top_level_module
    init_design

    read_sdc $source_sdc

    # Floorplan. Replace with the one your design needs.
    floorPlan -site core -r 1.0 0.7 5 5 5 5

    odatix_write_reports "init" $signature
    odatix_save post_init $signature
    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    exit -1
}
