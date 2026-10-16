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


# One compilation at the frequency currently written in the constraints file.
#
# An fmax search runs it at every iteration of its binary search (see
# find_fmax.tcl), from inside a procedure: the variables of this script are
# local to it, hence the "::" of the ones that are not. Every iteration creates
# the project again and compiles it from the RTL, the constraint being the only
# thing that changed since the previous one.
#
# How far it goes is ::odatix_synth_depth: "pnr" (the default) synthesizes, fits
# and analyzes the routed design; "synthesis" stops after synthesis and analyzes
# the synthesized netlist with a rough delay model. An fmax search set to
# "synthesis" therefore searches on post-synthesis timing: much faster, and
# approximate.

if {[catch {

    source scripts/settings.tcl
    source scripts/quartus_common.tcl

    set signature "<grey>\[synth_script.tcl\]<end>"

    if {![info exists ::odatix_synth_depth]} {
        set ::odatix_synth_depth "pnr"
    }

    report_progress 0 $synth_statusfile

    odatix_quartus_create_project $signature
    report_progress 5 $synth_statusfile

    set succeeded [odatix_quartus_synthesize $signature $synth_statusfile 5 25]
    if {$succeeded} {
        if {$::odatix_synth_depth eq "synthesis"} {
            puts "$signature <cyan>stopping after synthesis: reports are post-synthesis estimates<end>"
            set succeeded [odatix_quartus_report_synthesis $signature]
        } else {
            set succeeded [odatix_quartus_implement $signature $synth_statusfile 25 85]
            if {$succeeded} {
                set succeeded [odatix_quartus_report_implementation $signature $synth_statusfile 85 98]
            }
        }
    }
    odatix_quartus_close

    if {!$succeeded} {
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }

    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    if {$gblerrmsg == "continue"} {
        return -code continue
    } else {
        puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
        puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
        catch {
            puts "$signature <cyan>tcl error detail:<red>"
            puts "$gblerrmsg"
        }
        puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
        exit -1
    }
}
