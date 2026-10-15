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

    # The strategy procs (odatix_vivado_synthesize / odatix_vivado_implement)
    # follow the parameters of the flow, the same way the steps of a custom
    # frequency synthesis do.
    source scripts/step_common.tcl

    # How far this run goes. "pnr" (the default) synthesizes and implements, as
    # it always did; "synthesis" stops after logic optimization and reports on
    # the synthesized netlist. An fmax search set to "synthesis" therefore
    # searches on post-synthesis timing: much faster, and optimistic. The "::"
    # prefix is required: find_fmax.tcl sources this script from inside a proc.
    if {![info exists ::odatix_synth_depth]} {
        set ::odatix_synth_depth "pnr"
    }

    if {$single_thread == 1} {
        if {[catch {
            set_param synth.maxThreads 1
            set_param general.maxThreads 1
        } errmsg]} {
            puts "$signature <bold><red>error: failed setting vivado to single thread<end>"
            puts -nonewline "$signature tool says -> $errmsg"
        }
    }

    report_progress 0 $synth_statusfile

    ######################################
    # Read constraints
    ######################################
    if {[catch {
        read_xdc $constraints_file
    } errmsg]} {
        puts "$signature <bold><red>error: failed reading constraint file, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        exit -1
    }
    # find_fmax.tcl sources this script once per iteration of the search, each
    # time on a design rebuilt from the RTL, so the user constraints are read
    # again here every time — exactly like the generated timing constraint above,
    # which update_freq has just rewritten.
    odatix_read_user_constraints synthesis read_xdc $signature

    ######################################
    # Get target
    ######################################
    set f [open $target_file]
    set target [gets $f]
    close $f

    report_progress 10 $synth_statusfile

    ######################################
    # Synthetize
    ######################################

    if {![odatix_vivado_synthesize $target $signature $synth_statusfile 10 65]} {
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }

    report_progress 65 $synth_statusfile

    ######################################
    # Place and route
    ######################################

    if {$::odatix_synth_depth eq "synthesis"} {
        puts "$signature <cyan>stopping after synthesis: reports are post-synthesis estimates<end>"
    } else {
        odatix_read_user_constraints pnr read_xdc $signature
        if {![odatix_vivado_implement $signature $synth_statusfile 65 98]} {
            if {$continue_on_error == 1} {
                return -code continue "continue"
            } else {
                exit -1
            }
        }
    }

    report_progress 98 $synth_statusfile

    ######################################
    # Report
    ######################################
    if {[catch {
        report_utilization > $utilization_rep
        report_utilization -hierarchical > $utilization_h_rep
        report_timing > $timing_rep
        report_power > $power_rep
    } errmsg]} {
        puts "$signature <bold><red>error: failed report, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }

    # Keep a copy of the reports under the depth this run went to, the same way
    # the staged steps do (see odatix_write_reports in step_common.tcl). An fmax
    # search searching on post-synthesis timing and one searching on post-route
    # timing overwrite the same report files, so without this snapshot the
    # first one's numbers would be lost as soon as the second runs.
    set stage_path [file join $report_path $::odatix_synth_depth]
    file mkdir $stage_path
    foreach report [list $utilization_rep $utilization_h_rep $timing_rep $power_rep] {
        catch {file copy -force $report $stage_path}
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