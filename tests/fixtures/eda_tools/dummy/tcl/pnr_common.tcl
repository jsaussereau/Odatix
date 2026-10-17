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

# Helpers shared by the steps of the dummy place & route flow.
#
# The steps of a place & route run hand their state over exactly like those of a
# synthesis (see step_common.tcl); what is different is where the *first* one
# starts from: the netlist of a synthesis job run earlier, possibly by another
# tool, reached through $source_netlist and $source_sdc.

proc read_source_netlist {signature} {
    global source_netlist source_sdc source_tool source_type

    odatix_require_source $signature

    set handler [open $source_netlist r]
    set contents [read $handler]
    close $handler

    puts "$signature read [string length $contents] bytes of netlist from the <cyan>$source_tool<end> $source_type"
    puts "$signature constraints: <cyan>$source_sdc<end>"
}

proc write_pnr_report {name lines {signature ""}} {
    global report_path
    file mkdir $report_path
    set handler [open [file join $report_path $name] w]
    foreach line $lines {
        puts $handler $line
    }
    close $handler
}

# Results are exported once per step, each one reading the reports of its own
# step ("$step" in the file a metric names, see metrics.yml), so every step keeps
# a snapshot of what is known when it ends: utilization is measured at "place"
# and still readable at "signoff", where power joins it.
proc snapshot_pnr_reports {stage {signature ""}} {
    global report_path
    set stage_path [file join $report_path $stage]
    file mkdir $stage_path
    foreach report [glob -nocomplain -directory $report_path *.rep] {
        catch {file copy -force $report $stage_path}
    }
    puts "$signature <cyan>reports of the \"$stage\" step in $stage_path<end>"
}
