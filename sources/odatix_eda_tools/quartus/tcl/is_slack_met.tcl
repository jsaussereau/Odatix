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


# Verdicts on the timing report written by sta_report.tcl: its summary ends with
# the worst slack of the design, setup and minimum pulse width together.

proc is_slack_met {report_path timing_rep} {
    if {![file exists $timing_rep]} {
        return 0
    }
    set tfile [open $timing_rep]
    set met 0
    while {[gets $tfile data] != -1} {
        if {[string match "Worst Slack (MET)*" $data]} {
            set met 1
            break
        }
    }
    close $tfile
    return $met
}

proc is_slack_inf {report_path timing_rep} {
    if {![file exists $timing_rep]} {
        return 0
    }
    set tfile [open $timing_rep]
    set inf 0
    while {[gets $tfile data] != -1} {
        if {[regexp {^Worst Slack\s*: inf} $data]} {
            set inf 1
            break
        }
    }
    close $tfile
    return $inf
}
