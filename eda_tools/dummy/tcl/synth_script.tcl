#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

if {[catch {

    source scripts/settings.tcl

    set signature "<grey>\[synth_script.tcl\]<end>"

    puts "$signature <yellow>warning: this is a dummy script, nothing is being done here!<end>"

    report_progress 0 $synth_statusfile

    for { set i 0}  {$i < [expr { 2 + rand()*2}]} {incr i} {
        set duration [expr { rand() * 10}]
        for { set j 0}  {$j < $duration} {incr j} {
            sleep 0.25
            set progress [expr { 100*$j/$duration + 100*$j/4}]
            report_progress $progress $synth_statusfile
        }
    }

    if {[expr {rand() > 0.5}]} {
        set stiming_rep_handler [open $timing_rep w]
        puts "Dummy synthesis script: Slack (MET)"
        puts $stiming_rep_handler "Slack (MET)"
        close $stiming_rep_handler
    } else {
        set stiming_rep_handler [open $timing_rep w]
        puts "Dummy synthesis script: Slack (VIOLATED)"
        puts $stiming_rep_handler "Slack (VIOLATED)"
        close $stiming_rep_handler
    }

    report_progress 0 $synth_statusfile

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