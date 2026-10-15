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

# Helpers shared by the steps of a stepped flow.
#
# The steps of a single run share one Vivado process (see the
# "*_session" keys of tool.yml): the design stays in memory from one step to the
# next, and nothing has to be written and read back. A run that stops, and a
# later one that resumes it, are two processes though — so each step still hands
# its design over through a design checkpoint, and a step starting a process
# opens the checkpoint the previous one left instead of starting from the RTL.

source scripts/settings.tcl

proc odatix_checkpoint_path {name} {
    global result_path
    return [file join $result_path $name]
}

proc odatix_write_checkpoint {name signature} {
    global result_path
    file mkdir $result_path
    set path [odatix_checkpoint_path $name]
    if {[catch {
        write_checkpoint -force $path
    } errmsg]} {
        puts "$signature <bold><red>error: failed writing checkpoint $name<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        exit -1
    }
    # What this process holds in memory, so that the next step of the same
    # session continues from it instead of reading the checkpoint back.
    set ::odatix_design_in_memory $name
    puts "$signature <cyan>wrote checkpoint $path<end>"
}

proc odatix_open_checkpoint {name signature previous_step} {
    if {[info exists ::odatix_design_in_memory] && $::odatix_design_in_memory eq $name} {
        puts "$signature <cyan>continuing from the \"$previous_step\" step, in the same session<end>"
        return
    }
    set path [odatix_checkpoint_path $name]
    if {![file exists $path]} {
        puts "$signature <bold><red>error: missing checkpoint $name<end>"
        puts "$signature <cyan>note: this step continues the \"$previous_step\" step, which has to run first<end>"
        exit -1
    }
    if {[catch {
        open_checkpoint $path
    } errmsg]} {
        puts "$signature <bold><red>error: failed opening checkpoint $name<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        exit -1
    }
    set ::odatix_design_in_memory $name
    puts "$signature <cyan>opened checkpoint $path<end>"
}

# Metrics are exported when the run ends, whichever step it ended on, so every
# step that produces meaningful numbers writes the reports the metrics are read
# from. The standard files always hold the latest numbers; a copy is kept per
# step so the post-synthesis estimates survive place & route.
#
# "kinds" selects what a step can report. Each report is written on its own —
# one the tool refuses to produce does not cost the others.
proc odatix_write_reports {stage signature {kinds {utilization timing power}}} {
    global report_path utilization_rep utilization_h_rep timing_rep power_rep

    set written [list]
    foreach {kind command report} [list \
        utilization {report_utilization}               $utilization_rep \
        utilization {report_utilization -hierarchical} $utilization_h_rep \
        timing      {report_timing}                    $timing_rep \
        power       {report_power}                     $power_rep \
    ] {
        if {[lsearch -exact $kinds $kind] < 0} {
            continue
        }
        if {[catch {
            eval $command > $report
        } errmsg]} {
            puts "$signature <bold><red>error: failed report $report, skipping...<end>"
            puts -nonewline "$signature tool says -> $errmsg"
            continue
        }
        lappend written $report
    }

    set stage_path [file join $report_path $stage]
    file mkdir $stage_path
    foreach report $written {
        catch {file copy -force $report $stage_path}
    }
}

# An elaborated design is not mapped to the device, so the tool refuses every
# utilization, timing and power report: "report_utilization can be run only
# after synthesis has successfully completed". What an elaborated design does
# hold is the operators and the registers inferred from the RTL, as cells of the
# RTL netlist — counting them is the estimate available at that point, and the
# one this writes.
#
# The numbers are technology independent: they say how much arithmetic, memory
# and state the RTL describes, not how many LUTs it will take. They are there to
# compare configurations of a design space with each other in seconds, not to
# stand in for post-synthesis utilization.
proc odatix_write_rtl_resources {stage signature} {
    global report_path

    set arithmetic {RTL_ADD RTL_SUB RTL_MULT RTL_DIV RTL_MOD RTL_NEG RTL_ABS}

    array set per_cell {}
    set registers 0
    set memories 0
    set operators_arithmetic 0
    set operators_mux 0
    set operators_other 0

    foreach cell [get_cells -quiet -hierarchical] {
        # Vivado names an RTL cell after both the operator it inferred and the
        # shape it took ("RTL_REG__BREG_1"); the operator alone is counted.
        set ref [get_property -quiet REF_NAME $cell]
        regsub {__.*$} $ref "" ref
        if {$ref eq ""} {
            continue
        }
        if {[info exists per_cell($ref)]} {
            incr per_cell($ref)
        } else {
            set per_cell($ref) 1
        }

        switch -- [get_property -quiet PRIMITIVE_GROUP $cell] {
            RTL_REGISTER { incr registers }
            RTL_MEMORY   { incr memories }
            RTL_OPERATOR {
                if {[lsearch -exact $arithmetic $ref] >= 0} {
                    incr operators_arithmetic
                } elseif {$ref eq "RTL_MUX"} {
                    incr operators_mux
                } else {
                    incr operators_other
                }
            }
        }
    }

    set stage_path [file join $report_path $stage]
    file mkdir $stage_path
    set path [file join $stage_path rtl_resources.rep]
    if {[catch {set f [open $path w]} errmsg]} {
        puts "$signature <bold><red>error: failed report $path, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        return
    }

    puts $f "RTL Resources"
    puts $f "-------------"
    puts $f ""
    puts $f "Estimated from the elaborated RTL netlist, before any mapping to the"
    puts $f "device: these are inferred operators and registers, not device resources."
    puts $f ""
    puts $f "+--------------------------+--------+"
    puts $f "| Site Type                |   Used |"
    puts $f "+--------------------------+--------+"
    foreach {label value} [list \
        "Registers"            $registers \
        "Memories"             $memories \
        "Arithmetic Operators" $operators_arithmetic \
        "Multiplexers"         $operators_mux \
        "Other Operators"      $operators_other \
    ] {
        puts $f [format "| %-24s | %6d |" $label $value]
    }
    puts $f "+--------------------------+--------+"
    puts $f ""
    puts $f "+--------------------------+--------+"
    puts $f "| RTL Cell                 |   Used |"
    puts $f "+--------------------------+--------+"
    foreach ref [lsort [array names per_cell]] {
        puts $f [format "| %-24s | %6d |" $ref $per_cell($ref)]
    }
    puts $f "+--------------------------+--------+"
    close $f

    puts "$signature <cyan>wrote report $path<end>"
}

proc odatix_single_thread {signature} {
    global single_thread
    if {$single_thread != 1} {
        return
    }
    if {[catch {
        set_param synth.maxThreads 1
        set_param general.maxThreads 1
    } errmsg]} {
        puts "$signature <bold><red>error: failed setting vivado to single thread<end>"
        puts -nonewline "$signature tool says -> $errmsg"
    }
}

######################################
# Strategy
######################################
# How the design is synthesized and implemented is the flow's to say, through
# its "parameters" in tool.yml. Every script running synthesis or place & route
# goes through the two procs below -- the steps of a custom frequency synthesis
# as well as each iteration of an fmax search -- so a flow is the same strategy
# whatever the job:
#
#   synth_options      options of synth_design (directive, retiming, hierarchy)
#   opt_passes         one opt_design per entry, with these options
#   power_opt          a power_opt_design pass after logic optimization
#   place_options      options of place_design
#   phys_opt_passes    one phys_opt_design per entry, after placement
#   route_options      options of route_design
#   post_route_passes  commands run after routing, in order
#
# A pass list may be empty: the stage is then skipped. Without parameters, the
# defaults are what Odatix has always run.

# Run one command of the strategy. A failing optimization pass is skipped -- the
# design is still valid without it -- but a failing synthesis, placement or
# routing is fatal: returns 0 then, 1 otherwise.
proc odatix_vivado_run {command fatal signature} {
    puts "$signature <cyan>$command<end>"
    if {[catch {uplevel #0 $command} errmsg]} {
        if {$fatal} {
            puts "$signature <bold><red>error: failed '[lindex $command 0]'<end>"
            puts -nonewline "$signature tool says -> $errmsg"
            puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
            return 0
        }
        puts "$signature <bold><red>error: failed '[lindex $command 0]', skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
    }
    return 1
}

# Synthesis and logic optimization. Returns 0 when synthesis failed.
proc odatix_vivado_synthesize {target signature {progressfile ""} {from 0} {to 100}} {
    global top_level_module

    set synth_options [odatix_flow_param synth_options [list -flatten_hierarchy full]]
    set opt_passes [odatix_flow_param opt_passes [list "-sweep -remap -propconst" "-directive Explore"]]

    # Flows declared before parameters existed set these from an entry script.
    if {[info exists ::odatix_synth_options]} {
        lappend synth_options {*}$::odatix_synth_options
    }
    set power_opt [odatix_flow_param power_opt 0]
    if {[info exists ::odatix_power_opt] && $::odatix_power_opt} {
        set power_opt 1
    }

    set command [list synth_design -part $target -top $top_level_module -verilog_define VIVADO {*}$synth_options]
    if {![odatix_vivado_run $command 1 $signature]} {
        return 0
    }
    if {$progressfile ne ""} {
        report_progress [expr {$from + ($to - $from) * 2 / 3}] $progressfile
    }

    foreach pass $opt_passes {
        odatix_vivado_run [list opt_design {*}$pass] 0 $signature
    }
    if {$power_opt} {
        odatix_vivado_run [list power_opt_design] 0 $signature
    }
    return 1
}

# Placement, physical optimization and routing. Returns 0 when placement or
# routing failed.
proc odatix_vivado_implement {signature {progressfile ""} {from 0} {to 100}} {
    set place_options [odatix_flow_param place_options [list -directive Explore]]
    set phys_opt_passes [odatix_flow_param phys_opt_passes [list "-retime -rewire -critical_pin_opt -placement_opt -critical_cell_opt"]]
    set route_options [odatix_flow_param route_options [list -directive AggressiveExplore]]
    set post_route_passes [odatix_flow_param post_route_passes [list \
        "place_design -post_place_opt" \
        "phys_opt_design -retime -routing_opt" \
        "route_design -directive NoTimingRelaxation" \
    ]]

    if {![odatix_vivado_run [list place_design {*}$place_options] 1 $signature]} {
        return 0
    }
    if {$progressfile ne ""} {
        report_progress [expr {$from + ($to - $from) / 4}] $progressfile
    }
    foreach pass $phys_opt_passes {
        odatix_vivado_run [list phys_opt_design {*}$pass] 0 $signature
    }
    if {![odatix_vivado_run [list route_design {*}$route_options] 1 $signature]} {
        return 0
    }
    catch {
        puts "$signature <cyan>report_route_status:<end>"
        report_route_status
    }
    if {$progressfile ne ""} {
        report_progress [expr {$from + ($to - $from) * 3 / 4}] $progressfile
    }
    # Routing again is fatal when it fails: the design would be left unrouted.
    foreach pass $post_route_passes {
        set fatal [expr {[lindex $pass 0] eq "route_design"}]
        if {![odatix_vivado_run $pass $fatal $signature]} {
            return 0
        }
    }
    return 1
}
