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


# One iteration of an fmax search (sourced by find_fmax.tcl at each frequency it
# tries). The first one elaborates the design analyze_script.tcl read; every
# iteration then synthesizes a copy of it, or places and routes it when the
# search goes that far (::odatix_synth_depth, see step_fmax_*.tcl). The
# iteration meeting timing exports the netlist "odatix pnr" starts from.

if {[catch {

    set signature "<grey>\[synth_script.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    if {![info exists ::odatix_synth_depth]} {
        set ::odatix_synth_depth "synthesis"
    }

    report_progress 2 $synth_statusfile

    if {![info exists ::odatix_fc_elaborated]} {
        odatix_fc_elaborate $signature
        set ::odatix_fc_elaborated 1
    }

    report_progress 10 $synth_statusfile

    if {$::odatix_synth_depth eq "pnr"} {
        set frequency [odatix_fc_place_route $signature]
    } else {
        odatix_fc_start_from_elab $signature
        set frequency [odatix_fc_constrain $signature]
        odatix_fc_synthesize $signature
    }

    report_progress 90 $synth_statusfile

    odatix_fc_reports $frequency $::odatix_synth_depth $signature

    report_progress 95 $synth_statusfile

    if {[is_slack_met $report_path $timing_rep]} {
        odatix_fc_netlist $signature
    }

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
