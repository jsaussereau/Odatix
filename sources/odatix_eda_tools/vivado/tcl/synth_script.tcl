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

    ######################################
    # Flow options
    ######################################
    # Knobs a flow can override from its entry script (see the "flows" section
    # of tool.yml). The defaults reproduce the historical behaviour, so a
    # tool.yml without flows runs exactly as before. The "::" prefix is
    # required: find_fmax.tcl sources this script from inside a proc.
    if {![info exists ::odatix_synth_options]} {
        set ::odatix_synth_options ""
    }
    if {![info exists ::odatix_power_opt]} {
        set ::odatix_power_opt 0
    }
    # How far this run goes. "pnr" (the default) synthesizes and implements, as
    # it always did; "synthesis" stops after logic optimization and reports on
    # the synthesized netlist. An fmax search set to "synthesis" therefore
    # searches on post-synthesis timing: much faster, and optimistic.
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
    if {[catch {
        synth_design -flatten_hierarchy full -part ${target} -top ${top_level_module} -verilog_define VIVADO {*}$::odatix_synth_options
    } errmsg]} {
        puts "$signature <bold><red>error: failed design synth<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }
    report_progress 45 $synth_statusfile
    if {[catch {
        opt_design -sweep -remap -propconst
    } errmsg]} {
        puts "$signature <bold><red>error: failed design opt, skipping<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 55 $synth_statusfile
    if {[catch {
        opt_design -directive Explore
    } errmsg]} {
        puts "$signature <bold><red>error: failed design opt, skipping<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    if {$::odatix_power_opt} {
        if {[catch {
            power_opt_design
        } errmsg]} {
            puts "$signature <bold><red>error: failed power optimization, skipping<end>"
            puts -nonewline "$signature tool says -> $errmsg"
            puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        }
    }
    report_progress 65 $synth_statusfile

    ######################################
    # Place and route
    ######################################
    if {$::odatix_synth_depth eq "synthesis"} {
        puts "$signature <cyan>stopping after synthesis: reports are post-synthesis estimates<end>"
    } else {
    if {[catch {
        place_design -directive Explore
    } errmsg]} {
        puts "$signature <bold><red>error: failed design place<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }
    report_progress 70 $synth_statusfile
    if {[catch {
        phys_opt_design -retime -rewire -critical_pin_opt -placement_opt -critical_cell_opt
    } errmsg]} {
        puts "$signature <bold><red>error: failed physical opt, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 75 $synth_statusfile
    if {[catch {
        route_design -directive AggressiveExplore
    } errmsg]} {
        puts "$signature <bold><red>error: failed design route, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }
    if {[catch {
        puts "$signature <cyan>report_route_status:<end>"
        report_route_status
    } errmsg]} {
        puts "$signature <bold><red>error: failed report_route_status, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }

    report_progress 85 $synth_statusfile
    if {[catch {
        place_design -post_place_opt
    } errmsg]} {
        puts "$signature <bold><red>error: failed post-place opt, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 90 $synth_statusfile
    if {[catch {
        phys_opt_design -retime -routing_opt
        # -lut_opt -casc_opt
    } errmsg]} {
        puts "$signature <bold><red>error: failed physical opt, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 95 $synth_statusfile
    if {[catch {
        route_design -directive NoTimingRelaxation
    } errmsg]} {
        puts "$signature <bold><red>error: failed design route, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
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