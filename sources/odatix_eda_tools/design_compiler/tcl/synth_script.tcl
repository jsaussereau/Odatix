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

# One synthesis at the frequency currently written in the constraints file.
#
# This is what an fmax search runs at every iteration of its binary search, in
# the process that runs the search itself. find_fmax.tcl has set up the
# technology libraries and analyzed the RTL once, and what does not depend on
# the frequency is done once as well: the first iteration elaborates the design
# and saves it, the next ones clear the memory and read that database back. Only
# the constraints, the compilation and the reports are replayed.
#
# Each iteration starts again from the elaborated design rather than from what
# the previous one left in memory: a compiled design (and the subdesigns its
# compilation created) must not leak into the next compilation.
#
# What does persist from one iteration to the next is the application variables
# a strategy may change (the high effort scripts of compile_ultra do): the first
# iteration runs before them, the next ones after. Running each iteration in a
# process of its own would avoid it, at the cost of a license checkout and a
# library load per iteration.
#
# No netlist is exported here: the frequency this iteration ran at is not
# necessarily the one the search converges to (see step_fmax_netlist.tcl).

if {[catch {

    set signature "<grey>\[synth_script.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    set basename ${top_level_module}

    report_progress 2 $synth_statusfile

    if {![info exists ::odatix_dc_elaborated]} {
        odatix_dc_elaborate $signature

        report_progress 10 $synth_statusfile

        puts "<bold>"
        puts "**************************************"
        puts "  Save Database for further loading"
        puts "**************************************"
        puts "<end>"

        odatix_write_ddc "${basename}.ddc" $signature
        set ::odatix_dc_elaborated 1
    } else {
        remove_design -all
        odatix_read_ddc "${basename}.ddc" $signature "search"
    }

    report_progress 13 $synth_statusfile

    set frequency [odatix_dc_constrain $signature]

    report_progress 15 $synth_statusfile

    odatix_dc_compile $signature

    report_progress 90 $synth_statusfile

    odatix_dc_reports $frequency $signature

    report_progress 100 $synth_statusfile

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
