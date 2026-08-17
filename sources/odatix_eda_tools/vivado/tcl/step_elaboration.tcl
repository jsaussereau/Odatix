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

# Step "elaboration": RTL elaboration only, for a first estimate.
#
# Elaboration infers the operators and the registers the RTL describes without
# mapping anything to the device, so it takes seconds where synthesis takes
# minutes. Nothing being mapped, the tool refuses every utilization, timing and
# power report; what is counted instead are the cells of the RTL netlist (see
# odatix_write_rtl_resources). Those numbers are technology independent — they
# tell apart the configurations of a design space, they do not stand in for
# post-synthesis utilization. Stop a run here with "--until elaboration".
#
# The design is not handed over to the synthesis step: "synth_design" starts
# again from the RTL sources whatever is in memory, so this step closes the
# elaborated design instead of writing a checkpoint. The sources read to get
# here are kept though, so a synthesis running in the same session does not
# read them a second time (see analyze_script.tcl).

if {[catch {

    set signature "<grey>\[step_elaboration.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    odatix_single_thread $signature

    report_progress 0 $synth_statusfile

    ######################################
    # Get target
    ######################################
    set f [open $target_file]
    set target [gets $f]
    close $f

    report_progress 10 $synth_statusfile

    ######################################
    # Elaborate
    ######################################
    if {[catch {
        synth_design -rtl -part ${target} -top ${top_level_module} -verilog_define VIVADO
    } errmsg]} {
        puts "$signature <bold><red>error: failed design elaboration<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        exit -1
    }
    report_progress 70 $synth_statusfile

    ######################################
    # Report
    ######################################
    odatix_write_rtl_resources "elaboration" $signature
    report_progress 90 $synth_statusfile

    # Leave the tool as the synthesis step expects to find it: sources read, no
    # design open.
    catch {close_design}
    catch {unset ::odatix_design_in_memory}

    report_progress 100 $synth_statusfile
    odatix_step_done "elaboration" $signature

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
