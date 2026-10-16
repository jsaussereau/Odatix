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
# Odatix - LibreLane analyze script
#################################################################################
#
# Writes the LibreLane configuration of the design, once per job: an fmax search
# sources this before its first iteration, a custom frequency synthesis before
# its "synthesis" step.
#
# An RTL analysis ("odatix analyze", odatix_mode = analysis) also lints the RTL
# with Verilator and elaborates it with Yosys (Classic flow up to
# Yosys.Synthesis, with SYNTH_ELABORATE_ONLY), then gathers what they reported in
# log/analysis.log, where Odatix reads the analysis status from.

if {[catch {

    set signature "<grey>\[analyze_script.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/librelane_common.tcl
    report_progress 5 $synth_statusfile

    odatix_librelane_technology $signature
    odatix_librelane_write_config $signature
    report_progress 10 $synth_statusfile

    if {[info exists odatix_mode] && $odatix_mode == "analysis"} {

        # VHDLClassic synthesizes with Yosys.VHDLSynthesis (GHDL) instead
        set synthesis_step Yosys.Synthesis
        if {$librelane_flow eq "VHDLClassic"} {
            set synthesis_step Yosys.VHDLSynthesis
        }
        set ok [odatix_librelane_run $signature analysis "" $synthesis_step \
            --overwrite -c SYNTH_ELABORATE_ONLY=1]

        # What Verilator and Yosys said, in the form the analysis summary reads:
        # Verilator's own "%Error"/"%Warning" lines, Yosys' errors and warnings.
        set analysis_log [open $log_path/analysis.log w]
        set run_dir $librelane_runs_path/analysis
        set reported 0
        foreach step_dir [lsort -dictionary [glob -nocomplain -types d -directory $run_dir {[0-9]*-*}]] {
            foreach log [lsort [glob -nocomplain -directory $step_dir *.log]] {
                set f [open $log r]
                while {[gets $f line] >= 0} {
                    if {[string match "*verilator*" [file tail $step_dir]]} {
                        if {[string match "%*" $line] || [string match " *" $line]} {
                            puts $analysis_log $line
                            incr reported
                        }
                    } elseif {[regexp {^ERROR: (.*)$} $line -> message]} {
                        puts $analysis_log "%Error: yosys: $message"
                        incr reported
                    } elseif {[regexp {^Warning: (.*)$} $line -> message]} {
                        puts $analysis_log "Warning: yosys: $message"
                        incr reported
                    }
                }
                close $f
            }
        }
        if {!$ok} {
            # What LibreLane itself said: a failure no tool reported (a missing
            # top module, a bad configuration) is only there
            set errors $::odatix_librelane_errors
            if {[llength $errors] == 0} {
                set errors [list "LibreLane failed"]
            }
            foreach message $errors {
                puts $analysis_log "%Error: librelane: $message"
            }
        }
        close $analysis_log

        puts ""
        puts "----------------------------------------"
        puts "<bold><cyan>Analysis Summary<end>"
        puts "----------------------------------------"
        if {$ok} {
            puts "<green> Lint and elaboration     <bold>PASSED<end>"
        } else {
            puts "<red> Lint and elaboration     <bold>FAILED<end>"
        }
        puts " Messages reported: $reported (see $log_path/analysis.log)"
        puts ""
        puts "<cyan>Press 'q' to view the analysis summary.<end>"

        report_progress 100 $synth_statusfile
    }

} ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}
