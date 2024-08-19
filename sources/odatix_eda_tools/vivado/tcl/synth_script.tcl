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

    report_progress 0 $synth_statusfile

    ######################################
    # Analyze source files
    ######################################
    if {[info exists ::env(DO_NOT_ANALYZE_RTL)]} {
        if {[$::env(DO_NOT_ANALYZE_RTL) == 0]} {
            #source $analyze_script
            #puts "analyzing" 
        }
    } else {
        #source $analyze_script
        #puts "analyzing" 
    }
    #source $analyze_script

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
        synth_design -flatten_hierarchy full -part ${target} -top ${top_level_module} -verilog_define VIVADO
    } errmsg]} {
        puts "$signature <bold><red>error: failed design synth, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        exit -1
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
    report_progress 65 $synth_statusfile

    ######################################
    # Place and route
    ######################################
    if {[catch {
        place_design -directive Explore
    } errmsg]} {
        puts "$signature <bold><red>error: failed design place, exiting<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        exit -1
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
        exit -1
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
        exit -1
    }
    report_progress 98 $synth_statusfile

    ######################################
    # Report
    ######################################
    if {[catch {
        report_utilization > $utilization_rep
        report_timing > $timing_rep
        report_power > $power_rep
    } errmsg]} {
        puts "$signature <bold><red>error: failed report, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
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