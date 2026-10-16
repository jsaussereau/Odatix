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


# Summary of the reports of the synthesis an fmax search ended on.

source scripts/settings.tcl

proc odatix_print_report {title report {pattern "*"}} {
    puts ""
    puts "<bold>$title<end>:"
    if {![file exists $report]} {
        puts "  (no report)"
        return
    }
    set f [open $report r]
    while {[gets $f data] != -1} {
        if {[string match $pattern $data]} {
            if {[string match "*(VIOLATED)*" $data]} {
                puts "  <red>$data<end>"
            } elseif {[string match "*(MET)*" $data]} {
                puts "  <green>$data<end>"
            } else {
                puts "  $data"
            }
        }
    }
    close $f
    puts "Complete report can be found in \"[file normalize $report]\""
}

if {[file exists $freq_rep]} {
    puts ""
    set f [open $freq_rep r]
    puts "  [read $f]"
    close $f
}
odatix_print_report "Timing summary" $timing_rep "*Slack*"
odatix_print_report "Fmax summary" [file join $report_path fmax.rep] "Clock*"
odatix_print_report "Utilization summary" $utilization_rep "|*"
odatix_print_report "Power summary" $power_rep "*Power Dissipation*"
