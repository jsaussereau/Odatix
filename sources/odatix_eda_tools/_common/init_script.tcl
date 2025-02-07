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

if {[catch {

    set signature "<grey>\[init_script.tcl\]<end>"
    
    source scripts/settings.tcl

    ######################################
    # Create directories
    ######################################

    file mkdir $tmp_path
    file mkdir $report_path
    file mkdir $result_path
    file mkdir $log_path

    ######################################
    # Create status files
    ######################################

    close [open $synth_statusfile w]
    if {$target_frequency != 0} {
        close [open $statusfile w]
    }

    ######################################
    # Init constraints file
    ######################################

    source scripts/update_freq.tcl

    file mkdir [file dirname $constraints_file]
    close [open $constraints_file w]
    update_freq $target_frequency $constraints_file

    if {$target_frequency != 0} {
        close [open $statusfile w]
        set frequency_file_handler [open $frequency_file w]
        puts $frequency_file_handler "$target_frequency MHz"
        close $frequency_file_handler
    }

} ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    puts "$signature <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}