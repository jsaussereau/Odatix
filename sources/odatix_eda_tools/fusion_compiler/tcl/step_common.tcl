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

# Helpers shared by the steps of a Fusion Compiler synthesis.
#
# The design lives in a design library of the job (work/<lib>.nlib), created
# from the technology the target gives (fc_setup.tcl). A step saves the block it
# leaves; the next one, a new fc_shell process, opens it again:
#
#   <top>_elab   the elaborated design ("elaborate" step, or the first
#                iteration of an fmax search)
#   <top>        the synthesized design ("synthesis" step), or the placed and
#                routed one ("pnr" step)

source scripts/settings.tcl

proc odatix_fc_lib_path {} {
    global work_path lib_name
    return [file normalize [file join $work_path ${lib_name}.nlib]]
}

# A synthesis ("synthesis" step) is logical: it runs in non-physical mode,
# which Fusion Compiler only enters while no block is open (FLW-9103), and a
# block created in it is "logical-only": it can never be placed (DES-228). So
# the design is elaborated in the regular mode, and the mode is entered just
# before a synthesis opens its copy of the elaborated design
# (odatix_fc_start_from_elab). Not when this process places and routes ("pnr"
# step, or an fmax search on post-route timing, which set ::odatix_fc_pnr).
proc odatix_fc_session_mode {} {
    if {![info exists ::odatix_fc_pnr] && ![info exists ::odatix_fc_non_physical]} {
        set_non_physical_mode
        set ::odatix_fc_non_physical 1
    }
}

# Source the technology of the target: it only sets variables (TECH_FILE,
# REF_LIBS, TLUP_*). Without one, an analysis goes on without technology, and
# anything else stops.
proc odatix_fc_technology {signature {optional 0}} {
    global script_path
    if {![file exists $script_path/fc_setup.tcl]} {
        if {$optional} {
            puts "$signature <cyan>note: no technology, elaborating without reference libraries<end>"
            return 0
        }
        puts "$signature <bold><red>error: no technology setup 'fc_setup.tcl'<end>"
        puts "$signature <cyan>note: fusion compiler needs a technology file, make sure you added one in 'target_fusion_compiler.yml'<end>"
        exit -1
    }
    if {[catch {uplevel #0 {source scripts/fc_setup.tcl}} errmsg]} {
        puts "$signature <bold><red>error: could not source 'fc_setup.tcl'<end>"
        puts "$signature tool says -> $errmsg"
        exit -1
    }
    foreach name {TECH_FILE REF_LIBS} {
        if {![info exists ::$name]} {
            puts "$signature <bold><red>error: 'fc_setup.tcl' does not set $name<end>"
            exit -1
        }
    }
    foreach path [concat [list $::TECH_FILE] $::REF_LIBS] {
        if {![file exists $path]} {
            puts "$signature <bold><red>error: missing technology file $path<end>"
            puts "$signature <cyan>note: check the paths in 'fc_setup.tcl'<end>"
            exit -1
        }
    }
    return 1
}

# Create the design library of the job, replacing one a previous run left.
proc odatix_fc_create_lib {signature {optional_technology 0}} {
    set path [odatix_fc_lib_path]
    file delete -force $path
    file mkdir [file dirname $path]
    if {[odatix_fc_technology $signature $optional_technology]} {
        set command [list create_lib $path -technology $::TECH_FILE -ref_libs $::REF_LIBS]
    } else {
        set command [list create_lib $path]
    }
    if {[catch {{*}$command} errmsg]} {
        puts "$signature <bold><red>error: failed creating design library $path<end>"
        puts "$signature tool says -> $errmsg"
        exit -1
    }
    puts "$signature <cyan>created design library $path<end>"
}

proc odatix_fc_open_lib {signature previous_step} {
    set path [odatix_fc_lib_path]
    if {![file exists $path]} {
        puts "$signature <bold><red>error: missing design library $path<end>"
        puts "$signature <cyan>note: this step continues the \"$previous_step\" step, which has to run first<end>"
        exit -1
    }
    odatix_fc_technology $signature
    if {[catch {open_lib $path} errmsg]} {
        puts "$signature <bold><red>error: failed opening design library $path<end>"
        puts "$signature tool says -> $errmsg"
        exit -1
    }
}

proc odatix_fc_save_block {block signature} {
    if {[catch {save_block -as $block} errmsg]} {
        puts "$signature <bold><red>error: failed saving block $block<end>"
        puts "$signature tool says -> $errmsg"
        exit -1
    }
    puts "$signature <cyan>saved block $block<end>"
}

# Elaborate the analyzed design and save it as <top>_elab.
proc odatix_fc_elaborate {signature} {
    global top_level_module lib_name continue_on_error

    puts "<bold>"
    puts "**************************************"
    puts "          Elaborate Design"
    puts "**************************************"
    puts "<end>"

    if {[catch {
        elaborate -hdl_library $lib_name $top_level_module
        set_top_module $top_level_module
    } errmsg]} {
        puts "$signature <bold><red>error: failed elaborating design<end>"
        puts "$signature tool says -> $errmsg"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        }
        exit -1
    }

    odatix_fc_save_block ${top_level_module}_elab $signature
}

# Start a synthesis from the elaborated design: a copy of it, so that an fmax
# search starts every iteration from the same design. What an earlier
# iteration left open is discarded first.
proc odatix_fc_start_from_elab {signature} {
    global top_level_module
    catch {close_blocks -force [get_blocks -quiet -all]}
    odatix_fc_session_mode
    if {[catch {
        copy_block -from_block ${top_level_module}_elab -to_block $top_level_module -force
        open_block $top_level_module
        link_block
    } errmsg]} {
        puts "$signature <bold><red>error: failed copying the elaborated design<end>"
        puts "$signature tool says -> $errmsg"
        exit -1
    }
    odatix_fc_app_options $signature
}

proc odatix_fc_constrain {signature} {
    global constraints_file clock_signal reset_signal continue_on_error

    puts "<bold>"
    puts "**************************************"
    puts "           Create Clock "
    puts "**************************************"
    puts "<end>"

    # One scenario, timed in the corner of the reference libraries
    if {[sizeof_collection [get_modes -quiet functional]] == 0} {
        create_mode functional
    }
    if {[sizeof_collection [get_corners -quiet default]] == 0} {
        create_corner default
    }
    if {[sizeof_collection [get_scenarios -quiet functional_default]] == 0} {
        create_scenario -name functional_default -mode functional -corner default
    }
    current_scenario functional_default

    set frequency [string trim [read [open $constraints_file r]]]
    set clock_period [expr {1000.0 / $frequency}]
    set clock_uncertainty 0.1
    set input_delay [expr {0.1 * $clock_period}]
    set output_delay [expr {0.1 * $clock_period}]

    if {[catch {
        create_clock -name $clock_signal -period $clock_period [get_ports $clock_signal]
    } errmsg]} {
        puts "$signature <bold><red>error: failed creating clock<end>"
        puts "$signature tool says -> $errmsg"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        }
        exit -1
    }
    set_clock_uncertainty -setup $clock_uncertainty [get_clocks $clock_signal]
    set_clock_uncertainty -hold $clock_uncertainty [get_clocks $clock_signal]

    # Input and output delays, so that the paths between the ports and the
    # registers are timed too.
    set data_inputs [remove_from_collection [all_inputs] [get_ports -quiet [list $clock_signal $reset_signal]]]
    if {[sizeof_collection $data_inputs] > 0} {
        set_input_delay $input_delay -clock $clock_signal $data_inputs
    }
    if {[sizeof_collection [all_outputs]] > 0} {
        set_output_delay $output_delay -clock $clock_signal [all_outputs]
    }

    odatix_read_user_constraints synthesis read_sdc $signature

    return $frequency
}

# Place and route: parasitics of the technology and floorplan, before the
# design is synthesized on it.
proc odatix_fc_physical_setup {signature} {
    foreach name {TLUP_MAX TLUP_MIN TLUP_MAP} {
        if {![info exists ::$name] || ![file exists [set ::$name]]} {
            puts "$signature <bold><red>error: place and route needs $name, set it in 'fc_setup.tcl'<end>"
            exit -1
        }
    }
    # Read once per process: an fmax search comes back here at every iteration
    if {![info exists ::odatix_fc_parasitics_read]} {
        read_parasitic_tech -tlup $::TLUP_MAX -layermap $::TLUP_MAP -name RCMAX
        read_parasitic_tech -tlup $::TLUP_MIN -layermap $::TLUP_MAP -name RCMIN
        set ::odatix_fc_parasitics_read 1
    }
    set_parasitic_parameters -late_spec RCMAX -early_spec RCMIN
    set_extraction_options -reference_direction horizontal

    puts "<bold>"
    puts "**************************************"
    puts "            Floorplan"
    puts "**************************************"
    puts "<end>"

    initialize_floorplan \
        -site_def unit \
        -core_utilization [odatix_flow_param core_utilization 0.7] \
        -core_offset [odatix_flow_param core_offset 2]
    place_pins -self
}

proc odatix_fc_run_passes {parameter label signature} {
    # Commands of a flow parameter, run in order. One the installed version
    # does not know is skipped, with a warning.
    foreach pass [odatix_flow_param $parameter [list]] {
        puts "$signature <cyan>$label: $pass<end>"
        if {[catch {uplevel #0 $pass} errmsg]} {
            puts "$signature <bold><yellow>warning: '$pass' failed, skipping it<end>"
            puts "$signature tool says -> $errmsg"
        }
    }
}

# A command of the synthesis failed: the job stops, or with "continue_on_error"
# the iteration of the fmax search calling this does (the "continue" goes back
# to the loop of find_fmax.tcl, through the procedure calling this one).
proc odatix_fc_fail {what errmsg signature} {
    global continue_on_error
    puts "$signature <bold><red>error: $what failed<end>"
    puts "$signature tool says -> $errmsg"
    if {$continue_on_error == 1} {
        return -level 2 -code continue "continue"
    }
    exit -1
}

# App options of the strategy ("app_options": "<name> <value>" items), set on
# the block a synthesis or a place and route starts from. One the installed
# version does not know is skipped, with a warning: the design is valid without
# it.
proc odatix_fc_app_options {signature} {
    foreach option [odatix_flow_param app_options [list]] {
        lassign $option name value
        if {[catch {set_app_options -name $name -value $value} errmsg]} {
            puts "$signature <bold><yellow>warning: app option $name could not be set, going on without it<end>"
            puts "$signature tool says -> $errmsg"
        } else {
            puts "$signature <cyan>app option: $name = $value<end>"
        }
    }
}

# Logical synthesis ("synthesis" step): compile_logical, no placement.
proc odatix_fc_synthesize {signature} {
    puts "<bold>"
    puts "**************************************"
    puts "     Synthesis and Optimization"
    puts "**************************************"
    puts "<end>"

    set options [odatix_flow_param compile_logical_options [list]]
    puts "$signature <cyan>strategy: compile_logical $options<end>"
    if {[catch {compile_logical {*}$options} errmsg]} {
        odatix_fc_fail compile_logical $errmsg $signature
    }
    odatix_fc_run_passes post_compile_passes "post-compile pass" $signature
}

# Place and route ("pnr" step): the elaborated design is synthesized again on a
# floorplan (compile_fusion: physical synthesis and placement, a logical
# synthesis cannot be placed), then its clock tree is built and it is routed
# ("pnr_passes"). Returns the frequency it is constrained at.
proc odatix_fc_place_route {signature} {
    odatix_fc_start_from_elab $signature
    set frequency [odatix_fc_constrain $signature]
    odatix_read_user_constraints pnr read_sdc $signature
    odatix_fc_physical_setup $signature

    puts "<bold>"
    puts "**************************************"
    puts "   Physical Synthesis and Placement"
    puts "**************************************"
    puts "<end>"

    set options [odatix_flow_param compile_fusion_options [list]]
    puts "$signature <cyan>strategy: compile_fusion $options<end>"
    if {[catch {compile_fusion {*}$options} errmsg]} {
        odatix_fc_fail compile_fusion $errmsg $signature
    }

    puts "<bold>"
    puts "**************************************"
    puts "     Clock Tree and Routing"
    puts "**************************************"
    puts "<end>"

    foreach pass [odatix_flow_param pnr_passes [list clock_opt route_auto route_opt]] {
        puts "$signature <cyan>pnr: $pass<end>"
        if {[catch {uplevel #0 $pass} errmsg]} {
            odatix_fc_fail "'$pass'" $errmsg $signature
        }
    }
    return $frequency
}

# report_power gives its totals in the units of the libraries (nW, uW...).
# Their sum in mW is added at the end of the report, where metrics.yml reads it:
#   "Odatix power (mW): internal <x> switching <y> leakage <z> total <t>"
proc odatix_fc_power_summary {power_rep signature} {
    set scale {pW 1e-9 nW 1e-6 uW 1e-3 mW 1.0 W 1e3}
    set file [open $power_rep r]
    set totals ""
    while {[gets $file line] >= 0} {
        if {[regexp {^Total\s+(\S+)\s+(\w+)\s+(\S+)\s+(\w+)\s+(\S+)\s+(\w+)\s+(\S+)\s+(\w+)} $line -> a au b bu c cu d du]} {
            set totals [list $a $au $b $bu $c $cu $d $du]
        }
    }
    close $file
    if {$totals eq ""} {
        puts "$signature <bold><yellow>warning: no power totals in $power_rep<end>"
        return
    }
    set values [list]
    foreach {value unit} $totals {
        if {![dict exists $scale $unit] || ![string is double -strict $value]} {
            puts "$signature <bold><yellow>warning: unknown power unit '$unit' in $power_rep<end>"
            return
        }
        lappend values [format %.6g [expr {$value * [dict get $scale $unit]}]]
    }
    set file [open $power_rep a]
    puts $file ""
    puts $file [format "Odatix power (mW): internal %s switching %s leakage %s total %s" {*}$values]
    close $file
}

# Reports of a step, written where the metrics read them (report/*.rep) and
# kept under report/<stage>/: a run that goes on to place and route keeps the
# post-synthesis numbers, as with Vivado.
proc odatix_fc_reports {frequency stage signature} {
    global report_path power_rep area_rep utilization_rep timing_rep freq_rep ref_rep

    puts "<bold>"
    puts "**************************************"
    puts "            Write Reports"
    puts "**************************************"
    puts "<end>"

    set reports [list \
        power     $power_rep  {report_power} \
        area      $area_rep   {report_area -nosplit -hierarchy} \
        timing    $timing_rep {report_timing -delay_type max -max_paths 1 -significant_digits 4} \
        reference $ref_rep    {report_references -nosplit -hierarchical} \
    ]
    if {$stage eq "pnr"} {
        lappend reports utilization $utilization_rep {report_utilization}
    } else {
        file delete -force $utilization_rep
    }

    set written [list]
    foreach {label file command} $reports {
        puts "Writing $label report file '$file'."
        if {[catch {redirect $file $command} errmsg]} {
            puts "$signature <bold><red>error: could not write $label report<end>"
            puts "$signature tool says -> $errmsg"
            continue
        }
        lappend written $file
    }
    if {[lsearch -exact $written $power_rep] >= 0} {
        odatix_fc_power_summary $power_rep $signature
    }
    set file [open $freq_rep w]
    puts -nonewline $file "Target frequency:               $frequency"
    close $file
    lappend written $freq_rep

    set stage_path [file join $report_path $stage]
    file delete -force $stage_path
    file mkdir $stage_path
    foreach report $written {
        catch {file copy -force $report $stage_path}
    }
}

proc odatix_fc_netlist {signature} {
    global result_path top_level_module

    set basename ${top_level_module}_gates_fc

    puts "<bold>"
    puts "**************************************"
    puts "  Export Netlist, SDC and SDF files"
    puts "**************************************"
    puts "<end>"

    change_names -rules verilog -hierarchy
    write_verilog ${result_path}/${basename}.v
    write_sdc -output ${result_path}/${basename}.sdc
    write_sdf ${result_path}/${basename}.sdf

    odatix_publish_handoff \
        ${result_path}/${basename}.v \
        ${result_path}/${basename}.sdc \
        ${result_path}/${basename}.sdf \
        $signature
}
