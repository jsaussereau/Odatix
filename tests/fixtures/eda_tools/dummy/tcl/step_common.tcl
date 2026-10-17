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

# Helpers shared by the steps of the "staged" flow.
#
# Steps run as separate processes, so everything a step hands over to the next
# one goes through a file: this is where a real tool would write and read its
# checkpoints (write_checkpoint / read_checkpoint for Vivado, write -format ddc
# for Design Compiler, write_db for Genus).

set odatix_work_dir [lindex $argv 0]

proc checkpoint_path {name} {
    global odatix_work_dir
    return [file join $odatix_work_dir result $name]
}

proc write_checkpoint {name signature} {
    file mkdir [file dirname [checkpoint_path $name]]
    set handler [open [checkpoint_path $name] w]
    puts $handler "dummy checkpoint written by $signature"
    close $handler
    puts "$signature wrote checkpoint <cyan>$name<end>"
}

proc require_checkpoint {name signature} {
    if {![file exists [checkpoint_path $name]]} {
        puts "$signature <bold><red>error: missing checkpoint $name from the previous step<end>"
        exit -1
    }
    puts "$signature read checkpoint <cyan>$name<end>"
}

proc simulate_work {seconds statusfile} {
    set steps 8
    for {set i 0} {$i <= $steps} {incr i} {
        report_progress [expr {100 * $i / $steps}] $statusfile
        after [expr {int($seconds * 1000 / $steps)}]
    }
}
