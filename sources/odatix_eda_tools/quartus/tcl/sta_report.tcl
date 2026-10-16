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

# Timing reports of a job, written from inside the timing analyzer.
#
# quartus_sta runs this at the end of its default script (--report_script), the
# timing netlist built and every corner analyzed. odatix_quartus_timing (see
# quartus_common.tcl) sets what it needs before sourcing it:
#
#   ::odatix_sta_stage         stage the reports describe
#   ::odatix_sta_post_syn      1 for the synthesized netlist
#   ::odatix_sta_sdc_files     the timing constraints of the job
#   ::odatix_sta_timing_rep    timing report to write
#   ::odatix_sta_fmax_rep      Fmax report to write
#
# The timing report starts with a summary in a format of our own -- what the
# metrics and the fmax search read -- then gives the worst paths. A design meets
# timing when its worst setup slack and its worst minimum pulse width slack are
# both positive, on every corner: a clock faster than the device allows fails
# the pulse width check even when no path is too long.

set signature "<grey>\[sta_report.tcl\]<end>"

# On the synthesized netlist, quartus_sta reads only the constraints embedded in
# the RTL: the timing constraint of the job has to be read here.
if {$::odatix_sta_post_syn} {
    reset_design
    foreach sdc_file $::odatix_sta_sdc_files {
        read_sdc $sdc_file
    }
    update_timing_netlist
}

# Worst slack of a kind, over every clock: {slack clock corner}, or {} when no
# clock has such a path.
proc odatix_sta_worst {kind} {
    set worst {}
    if {[catch {get_clock_domain_info -$kind} domains]} {
        return $worst
    }
    foreach domain $domains {
        lassign $domain clock slack tns endpoints corner
        if {![string is double -strict $slack]} {
            continue
        }
        if {$worst eq {} || $slack < [lindex $worst 0]} {
            set worst [list $slack $clock $corner]
        }
    }
    return $worst
}

proc odatix_sta_line {label worst} {
    if {$worst eq {}} {
        return [format "%-28s: inf" $label]
    }
    lassign $worst slack clock corner
    set verdict [expr {$slack >= 0 ? "MET" : "VIOLATED"}]
    return [format "%-28s: %.3f ns (%s, %s)" "$label ($verdict)" $slack $clock $corner]
}

set setup [odatix_sta_worst setup]
set hold  [odatix_sta_worst hold]
set mpw   [odatix_sta_worst mpw]
# Over every corner, before the worst paths select one of them
set fmax_failed [catch {get_clock_fmax_info} clocks]

set f [open $::odatix_sta_timing_rep w]
puts $f "Quartus timing summary ($::odatix_sta_stage[expr {$::odatix_sta_post_syn ? ", post-synthesis estimate" : ""}])"
puts $f ""
puts $f [odatix_sta_line "Setup Slack" $setup]
puts $f [odatix_sta_line "Hold Slack" $hold]
puts $f [odatix_sta_line "Pulse Width Slack" $mpw]
if {$setup eq {}} {
    # No register to register path: nothing to search a frequency on
    puts $f [format "%-28s: inf" "Worst Slack"]
} else {
    set worst [lindex $setup 0]
    if {$mpw ne {} && [lindex $mpw 0] < $worst} {
        set worst [lindex $mpw 0]
    }
    set verdict [expr {$worst >= 0 ? "MET" : "VIOLATED"}]
    puts $f [format "%-28s: %.3f ns" "Worst Slack ($verdict)" $worst]
}
puts $f ""
close $f

# The worst setup paths, on the corner the worst slack is found on
if {$setup ne {}} {
    if {[catch {
        set conditions [get_available_operating_conditions]
        if {[llength $conditions] > 1} {
            set worst_condition ""
            set worst_slack ""
            foreach condition $conditions {
                set_operating_conditions $condition
                update_timing_netlist
                foreach domain [get_clock_domain_info -setup] {
                    set slack [lindex $domain 1]
                    if {$worst_slack eq "" || $slack < $worst_slack} {
                        set worst_slack $slack
                        set worst_condition $condition
                    }
                }
            }
            set_operating_conditions $worst_condition
            update_timing_netlist
        }
        report_timing -setup -npaths 10 -detail full_path -file $::odatix_sta_timing_rep -append
    } errmsg]} {
        puts "$signature <yellow>warning: could not report the worst paths: $errmsg<end>"
    }
}

# What Quartus computes from the slacks: the frequency each clock would reach,
# and the one the device allows it ("Restricted Fmax"). An estimate the timing
# summary gives anyway, so it is reported for every job.
set f [open $::odatix_sta_fmax_rep w]
puts $f "Quartus Fmax summary ($::odatix_sta_stage)"
puts $f ""
if {!$fmax_failed} {
    foreach clock $clocks {
        lassign $clock name fmax restricted
        puts $f [format "Clock %-20s: Fmax %s MHz, Restricted Fmax %s MHz" $name $fmax $restricted]
    }
}
close $f

puts "$signature <cyan>wrote report $::odatix_sta_timing_rep<end>"
