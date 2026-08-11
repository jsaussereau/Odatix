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

# Step "synthesis" of the "staged" flow: synthesis and logic optimization.
#
# The reports written here are post-synthesis estimates: a run stopped at this
# step ("--until synthesis") still exports metrics, which is what makes it
# possible to pick the configurations worth implementing.

if {[catch {

    set signature "<grey>\[step_synthesis.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    odatix_single_thread $signature

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
        synth_design -flatten_hierarchy full -part ${target} -top ${top_level_module} -verilog_define VIVADO
    } errmsg]} {
        puts "$signature <bold><red>error: failed design synth<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        exit -1
    }
    report_progress 55 $synth_statusfile

    if {[catch {
        opt_design -sweep -remap -propconst
    } errmsg]} {
        puts "$signature <bold><red>error: failed design opt, skipping<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 70 $synth_statusfile

    if {[catch {
        opt_design -directive Explore
    } errmsg]} {
        puts "$signature <bold><red>error: failed design opt, skipping<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
    }
    report_progress 80 $synth_statusfile

    ######################################
    # Report and hand over
    ######################################
    odatix_write_reports "synthesis" $signature
    report_progress 90 $synth_statusfile

    odatix_write_checkpoint "post_synth.dcp" $signature

    report_progress 100 $synth_statusfile
    odatix_step_done "synthesis" $signature

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
