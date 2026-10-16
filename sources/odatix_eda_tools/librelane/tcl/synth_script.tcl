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

#################################################################################
# Odatix - LibreLane synthesis script (one iteration of an fmax search)
#################################################################################
#
# Runs the Classic flow at the frequency currently written in the constraints
# file, from the RTL every time, as deep as the search goes
# (::odatix_synth_depth, set by step_fmax_<depth>.tcl):
#
#   synthesis   up to OpenROAD.STAPrePNR: timing of the synthesized netlist,
#               without wires (fast, optimistic), like the fmax of the other
#               ASIC synthesis tools of Odatix
#   pnr         up to OpenROAD.STAPostPNR: timing of the routed design, with
#               extracted parasitics (what the design really reaches)
#
# Each depth has a run directory of its own (runs/fmax_<depth>), overwritten at
# every iteration. The reports are written to $report_path, and copied to
# $report_path/<depth> so that the two searches do not overwrite each other.
#
# An iteration that meets timing publishes its netlist for "odatix pnr": the
# search only raises its lower bound on such an iteration, so the netlist left
# when it ends is the one of the frequency it reports.

if {[catch {

    set signature "<grey>\[synth_script.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/is_slack_met.tcl
    source scripts/librelane_common.tcl

    if {![info exists ::odatix_synth_depth]} {
        set ::odatix_synth_depth "synthesis"
    }
    switch -- $::odatix_synth_depth {
        synthesis { set to "OpenROAD.STAPrePNR" }
        pnr       { set to "OpenROAD.STAPostPNR" }
        default   { error "unknown fmax search depth \"$::odatix_synth_depth\"" }
    }
    set tag fmax_$::odatix_synth_depth

    report_progress 10 $synth_statusfile

    # Reports of the previous iteration must not be taken for this one's
    file delete -force $timing_rep $report_path/metrics.json

    set ok [odatix_librelane_run $signature $tag "" $to --overwrite]

    report_progress 90 $synth_statusfile

    # A run failing past synthesis (a checker stopping the flow) still measured
    # timing up to there: the search treats it as an iteration that missed it.
    odatix_librelane_collect $signature $tag $report_path $librelane_state_path/$tag.json

    if {!$ok} {
        error "LibreLane failed"
    }

    if {[info exists ::cur_freq] && [is_slack_met $report_path $timing_rep]} {
        odatix_librelane_publish_handoff $signature $librelane_state_path/$tag.json
    }

    set stage_path [file join $report_path $::odatix_synth_depth]
    file mkdir $stage_path
    foreach report [list $timing_rep $report_path/metrics.json $report_path/librelane_metrics.json] {
        catch {file copy -force $report $stage_path}
    }

    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><yellow>LibreLane run failed: $gblerrmsg<end>"
    report_progress 0 $synth_statusfile
    # Tells find_fmax.tcl this iteration failed
    error $gblerrmsg
}
