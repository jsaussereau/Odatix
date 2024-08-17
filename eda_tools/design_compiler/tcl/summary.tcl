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

source scripts/settings.tcl

######################################
# Procedures
######################################

proc timing_summary {freq_rep timing_rep} {
    puts ""
    puts "<bold>Timing summary<end>:"

    if {[file exists $freq_rep]} {
        puts -nonewline "  "
        puts [read [open $freq_rep r]]
        puts -nonewline "  "
    }

    if {[file exists $timing_rep]} {
        set tfile [open $timing_rep r]
        while {[gets $tfile data] != -1} {
            if {[string match *[string toupper "slack "]* [string toupper $data]]} {
                if {[string match *[string toupper "slack (MET)"]* [string toupper $data]]} {
                    puts "<bold><green>$data<end>"
                } else {
                    puts "<bold><red>$data<end>"
                }
                break
            }
        }
        close $tfile

        set tfile [open $timing_rep r]
        while {[gets $tfile data] != -1} {
            if {[string match *[string toupper "Startpoint"]* [string toupper $data]]} {
                puts $data
            }
            if {[string match *[string toupper "Endpoint"]* [string toupper $data]]} {
                puts $data
            }
        }
        close $tfile
    }

    puts ""
    set pwd [pwd]
    puts "Complete timning report can be found in \"$pwd/$timing_rep\""
}


proc area_summary {area_rep} {
    puts ""
    puts "<bold>Area summary<end>:"

    set afile [open $$area_rep r]
    while {[gets $afile data] != -1} {
        if {[string match *[string toupper "Total cell area"]* [string toupper $data]]} {
            puts -nonewline "  "
            puts $data
        }
    }
    close $afile

    puts -nonewline "  "
    puts [read [open $report_dir/cell_count.rep r]]

    set pwd [pwd]
    puts "Complete area report can be found in \"$pwd/$$area_rep\""
}

######################################
# Display summaries
######################################

timing_summary $freq_rep $timing_rep
area_summary $utilization_rep
#power_summary $power_rep
