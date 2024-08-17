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

    source scripts/settings.tcl

    set signature "<grey>\[synth_script.tcl\]<end>"

    report_progress 5 $synth_statusfile

    if {[catch {
        set chan [open "|/bin/sh -c \"/openlane/flow.tcl -tag odatix -overwrite\"" r]
        while {[gets $chan line] >= 0} {
            puts $line
        }
        close $chan
    } errmsg]} {
        if {[file exists "$report_path/metrics.csv"]} {
            puts "$signature <bold><yellow>warning: openlane flow failed at this frequency<end>"
        } else {
            puts "$signature <bold><red>error: openlane flow failed, exiting<end>"
            puts "$signature tool says -> $errmsg"
            puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
            exit -1
        }
    }

    report_progress 98 $synth_statusfile

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