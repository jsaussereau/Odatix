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

# Summary of the run an fmax search reports (sourced by find_fmax.tcl)

source scripts/settings.tcl

puts ""
puts "<bold>Timing summary<end>:"
if {[file exists $freq_rep]} {
    set f [open $freq_rep r]
    puts "  [read $f]"
    close $f
}
if {[file exists $timing_rep]} {
    set f [open $timing_rep r]
    while {[gets $f line] >= 0} {
        if {[regexp {^(setup_ws|setup_tns|hold_ws): (\S+)} $line -> name value]} {
            if {$value ne "inf" && $value < 0} {
                puts "  <bold><red>$name: $value ns<end>"
            } else {
                puts "  <bold><green>$name: $value ns<end>"
            }
        }
    }
    close $f
}

puts ""
puts "<bold>Metrics<end>:"
if {[file exists $report_path/metrics.json]} {
    set f [open $report_path/metrics.json r]
    while {[gets $f line] >= 0} {
        if {[regexp {"([^"]+)": (\S+?),?$} $line -> name value]} {
            puts "  $name: $value"
        }
    }
    close $f
}
puts ""
puts "All the metrics LibreLane measured are in \"$report_path/librelane_metrics.json\""
