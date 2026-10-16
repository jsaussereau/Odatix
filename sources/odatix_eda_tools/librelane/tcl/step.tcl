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

#################################################################################
# Odatix - LibreLane step of a custom frequency synthesis
#################################################################################
#
#   tclsh scripts/step.tcl <step>
#
# Runs one step of the Classic flow (synthesis, floorplan, place, cts, route,
# signoff, see librelane_step_ranges) in runs/custom. A step starts from the
# state the previous one left (state/<previous step>.json), not from whatever
# the run directory holds last: a step killed halfway leaves the states of the
# LibreLane steps it completed there, and resuming it must start over from its
# own beginning.
#
# Each step writes its reports to report/<step> (and report/, the latest), and
# the state the next one starts from to state/<step>.json. "synthesis" also
# writes the LibreLane configuration of the job first, and its netlist is
# published for "odatix pnr".

if {[catch {

    set step [lindex $argv 0]
    set signature "<grey>\[step.tcl:$step\]<end>"

    source scripts/settings.tcl
    source scripts/librelane_common.tcl

    if {![dict exists $librelane_step_ranges $step]} {
        error "unknown step \"$step\" (expected one of: $librelane_step_order)"
    }
    lassign [dict get $librelane_step_ranges $step] from to

    report_progress 5 $synth_statusfile

    set options [list]
    if {$step eq "synthesis"} {
        source scripts/init_script.tcl
        source scripts/analyze_script.tcl
        lappend options --overwrite
    } else {
        odatix_librelane_technology $signature
        set previous [lindex $librelane_step_order [expr {[lsearch -exact $librelane_step_order $step] - 1}]]
        set input $librelane_state_path/$previous.json
        if {![file exists $input]} {
            error "no state left by step \"$previous\" ($input): run it first"
        }
        lappend options -i $input
    }

    report_progress 15 $synth_statusfile
    set ok [odatix_librelane_run $signature custom $from $to {*}$options]
    report_progress 90 $synth_statusfile

    if {!$ok} {
        puts "$signature <bold><red>error: step $step failed, exiting<end>"
        exit -1
    }

    if {![odatix_librelane_collect $signature custom $report_path/$step $librelane_state_path/$step.json]} {
        exit -1
    }
    foreach report [glob -nocomplain -directory $report_path/$step *] {
        file copy -force $report $report_path
    }

    if {$step eq "synthesis"} {
        odatix_librelane_publish_handoff $signature $librelane_state_path/$step.json
    }

    report_progress 100 $synth_statusfile
    odatix_step_done $step $signature

} ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}
exit 0
