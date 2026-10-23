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

# Helpers shared by the steps of a Design Compiler synthesis.
#
# Each step is its own dc_shell process, so nothing survives in memory from one
# step to the next: a step hands its design over through a .ddc database, and
# the next step reads it back instead of starting again from the RTL.

source scripts/settings.tcl

proc odatix_ddc_path {name} {
    global result_path
    return [file join $result_path $name]
}

# The technology library setup every process needs, whether it reads the RTL or
# a database written by an earlier step. The setup file is sourced at global
# level: it sets application variables (target_library, link_library...) and
# reads others (synthetic_library), which a proc body would only see as locals.
proc odatix_dc_setup {signature} {
    global lib_name work_path
    define_design_lib $lib_name -path $work_path
    if {[catch {
        uplevel #0 {source scripts/synopsys_dc_setup.tcl}
    } errmsg]} {
        puts "$signature <bold><red>error: could not source 'synopsys_dc_setup.tcl'<end>"
        puts "$signature <cyan>note: design compiler needs a technology file, make sure you added one in 'target_design_compiler.yml'<end>"
        exit -1
    }
}

proc odatix_write_ddc {name signature} {
    global result_path
    file mkdir $result_path
    set path [odatix_ddc_path $name]
    if {[catch {
        write -hierarchy -format ddc -output $path
    } errmsg]} {
        puts "$signature <bold><red>error: failed writing database $name<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        exit -1
    }
    puts "$signature <cyan>wrote database $path<end>"
}

proc odatix_read_ddc {name signature previous_step} {
    global top_level_module
    set path [odatix_ddc_path $name]
    if {![file exists $path]} {
        puts "$signature <bold><red>error: missing database $name<end>"
        puts "$signature <cyan>note: this step continues the \"$previous_step\" step, which has to run first<end>"
        exit -1
    }
    if {[catch {
        read_ddc $path
        current_design $top_level_module
        link
    } errmsg]} {
        puts "$signature <bold><red>error: failed reading database $name<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        exit -1
    }
    puts "$signature <cyan>read database $path<end>"
}

# Elaboration, resolution of references and uniquification: everything that
# turns the analyzed RTL into a design ready to be constrained and compiled.
proc odatix_dc_elaborate {signature} {
    global top_level_module lib_name continue_on_error

    puts "<bold>"
    puts "**************************************"
    puts "          Elaborate Design"
    puts "**************************************"
    puts "<end>"

    redirect -variable result {
        elaborate ${top_level_module} -library $lib_name
    }
    set result [string trimright $result "\n0"]
    puts $result
    if {[regexp -nocase -line {^Error:} $result]} {
        puts "$signature <bold><red>error: failed elaborating design<end>"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }

    link

    puts "<bold>"
    puts "**************************************"
    puts "          Uniquify Design"
    puts "**************************************"
    puts "<end>"
    uniquify

    # remove "remove constant", "merge register" and "complemented port" information
    suppress_message { OPT-1206 OPT-319 OPT-1215 }
}

# Timing constraints, read from the frequency Odatix wrote in the constraints
# file. Returns the target frequency in MHz.
proc odatix_dc_constrain {signature} {
    global constraints_file clock_signal reset_signal continue_on_error

    puts "<bold>"
    puts "**************************************"
    puts "           Create Clock "
    puts "**************************************"
    puts "<end>"

    # Get frequency from constraints file
    set frequency [read [open $constraints_file r]]

    # Timing Constraints - Clock Frequency
    set clock_period [expr 1000.0 / $frequency]

    set clock_skew  0.1
    set jitter 0.0
    set margin 0.0
    set clock_uncertainty [expr $clock_skew + $jitter + $margin]

    set input_delay [expr 0.1 * $clock_period]
    set output_delay [expr 0.1 * $clock_period]

    redirect -variable result {
        create_clock -name $clock_signal -period $clock_period -waveform [list 0.0 [expr $clock_period / 2.0]] [list $clock_signal]
    }
    set result [string trimright $result "\n0"]
    puts $result
    if {[regexp -nocase -line {^Error:} $result]} {
        puts "$signature <bold><red>error: failed creating clock<end>"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }

    set_wire_load_mode segmented
    set_clock_uncertainty -hold $clock_skew $clock_signal
    set_clock_uncertainty -setup $clock_skew $clock_signal
    set_max_transition 0.5 $reset_signal

    # Input and output delays, so that the paths between the ports and the
    # registers are timed too. Without them those paths are unconstrained: a
    # strategy that moves registers (retiming) can then push logic onto them and
    # report a frequency the design does not reach.
    set data_inputs [remove_from_collection [all_inputs] [get_ports [list $clock_signal $reset_signal]]]
    if {[sizeof_collection $data_inputs] > 0} {
        set_input_delay $input_delay -clock $clock_signal $data_inputs
    }
    if {[sizeof_collection [all_outputs]] > 0} {
        set_output_delay $output_delay -clock $clock_signal [all_outputs]
    }

    check_timing

    return $frequency
}

# The compilation, run the way the flow says (its "parameters" in tool.yml):
#
#   compile               "compile" or "compile_ultra"
#   compile_options       what is passed to it
#   max_area              an area constraint, usually 0 to recover all the area
#                         the timing allows ("" for none)
#   leakage_optimization  leakage / dynamic power optimization (Power Compiler)
#   dynamic_optimization
#   gate_clock            clock gating insertion
#   incremental           a second, incremental pass on the mapped design
#   incremental_options   what is passed to that pass
#   post_compile_passes   commands run on the mapped design afterwards
#
# Without parameters, this is a plain "compile", as it always was.
proc odatix_dc_compile {signature} {
    global continue_on_error

    puts "<bold>"
    puts "**************************************"
    puts "     Synthesis and Optimization"
    puts "**************************************"
    puts "<end>"

    set_fix_multiple_port_nets -all [all_designs]
    set_fix_multiple_port_nets -outputs -feedthroughs -constants

    set compile_command [odatix_flow_param compile compile]
    set options [odatix_flow_param compile_options [list]]

    set max_area [odatix_flow_param max_area ""]
    if {$max_area ne ""} {
        set_max_area $max_area
    }
    # Power optimization is licensed apart: a flow asking for it on a
    # installation without it still synthesizes, and says what it skipped.
    foreach {parameter command} {
        leakage_optimization set_leakage_optimization
        dynamic_optimization set_dynamic_optimization
    } {
        if {[odatix_flow_param $parameter 0]} {
            if {[catch {$command true} errmsg]} {
                puts "$signature <bold><yellow>warning: $command failed, going on without it<end>"
                puts "$signature tool says -> $errmsg"
            }
        }
    }
    if {[odatix_flow_param gate_clock 0]} {
        lappend options -gate_clock
    }

    puts "$signature <cyan>strategy: $compile_command $options<end>"
    if {[catch {$compile_command {*}$options} errmsg]} {
        puts "$signature <bold><red>error: $compile_command failed<end>"
        puts "$signature tool says -> $errmsg"
        if {$continue_on_error == 1} {
            return -code continue "continue"
        } else {
            exit -1
        }
    }

    if {[odatix_flow_param incremental 0]} {
        set incremental_options [odatix_flow_param incremental_options [list]]
        if {$compile_command eq "compile_ultra"} {
            set incremental [list compile_ultra -incremental {*}$incremental_options]
        } else {
            set incremental [list compile -incremental_mapping {*}$incremental_options]
        }
        puts "$signature <cyan>incremental pass: $incremental<end>"
        if {[catch {{*}$incremental} errmsg]} {
            puts "$signature <bold><yellow>warning: incremental pass failed, keeping the first one<end>"
            puts "$signature tool says -> $errmsg"
        }
    }

    # Commands run on the mapped design, in order. One the installed version
    # does not know is skipped: the design is valid without it.
    foreach pass [odatix_flow_param post_compile_passes [list]] {
        puts "$signature <cyan>post-compile pass: $pass<end>"
        if {[catch {uplevel #0 $pass} errmsg]} {
            puts "$signature <bold><yellow>warning: '$pass' failed, skipping it<end>"
            puts "$signature tool says -> $errmsg"
        }
    }
}

# The cell count of the design, then that of each hierarchical instance, laid
# out like the hierarchical distribution of the area report. "Global" counts
# every cell below an instance, "Local" those at its own level. Both count the
# hierarchical instances themselves, as the total always did.
proc odatix_dc_write_cell_counts {path} {
    set top [current_design_name]
    set total [sizeof_collection [get_cells -quiet -hierarchical *]]
    set rows [list [list $top $total [sizeof_collection [get_cells -quiet *]] $top]]
    set instances [get_cells -quiet -hierarchical * -filter "is_hierarchical == true"]
    foreach_in_collection cell [sort_collection $instances full_name] {
        set name [get_attribute $cell full_name]
        redirect /dev/null {current_instance $name}
        set global [sizeof_collection [get_cells -quiet -hierarchical *]]
        set local [sizeof_collection [get_cells -quiet *]]
        redirect /dev/null {current_instance}
        lappend rows [list $name $global $local [get_attribute $cell ref_name]]
    }

    set width [string length "Hierarchical cell"]
    foreach row $rows {
        set width [expr {max($width, [string length [lindex $row 0]])}]
    }
    set line [format "%-${width}s  %10s  %7s  %10s  %s" [string repeat - $width] ---------- ------- ---------- ------]
    set file [open $path w]
    puts $file [format "Cell count:                     %d" $total]
    puts $file ""
    puts $file "Hierarchical cell count distribution"
    puts $file "------------------------------------"
    puts $file ""
    puts $file [format "%-${width}s  %10s  %7s  %10s  %s" "Hierarchical cell" "Global" "Percent" "Local" "Design"]
    puts $file $line
    foreach row $rows {
        lassign $row name global local design
        set percent [expr {$total > 0 ? 100.0 * $global / $total : 0.0}]
        puts $file [format "%-${width}s  %10d  %7.1f  %10d  %s" $name $global $percent $local $design]
    }
    puts $file $line
    close $file
}

# Metrics are exported when the run ends, whichever step it ended on, so the
# step that compiles the design writes the reports the metrics are read from.
proc odatix_dc_reports {frequency signature} {
    global power_rep area_rep utilization_rep timing_rep freq_rep ref_rep

    puts "<bold>"
    puts "**************************************"
    puts "            Write Reports"
    puts "**************************************"
    puts "<end>"

    if {[catch {
        # Report Power
        puts "Writing power report file '$power_rep'."
        report_power > $power_rep
    } errmsg]} {
        puts "$signature <bold><red>error: could not write power report<end>"
        puts "$signature tool says -> $errmsg"
    }
    if {[catch {
        # Report Area
        puts "Writing area report file '$area_rep'."
        report_area -nosplit -hierarchy > $area_rep
        odatix_dc_write_cell_counts $utilization_rep
    } errmsg]} {
        puts "$signature <bold><red>error: could not write area report<end>"
        puts "$signature tool says -> $errmsg"
    }
    if {[catch {
        # Report Timing
        puts "Writing timing report file '$timing_rep'."
        report_timing -path full -delay max -nworst 1 -max_paths 1 -significant_digits 4 -sort_by group > $timing_rep
        echo -n "Target frequency:               $frequency" > $freq_rep
    } errmsg]} {
        puts "$signature <bold><red>error: could not write timing report<end>"
        puts "$signature tool says -> $errmsg"
    }
    if {[catch {
        # Report Reference
        puts "Writing reference report file '$ref_rep'."
        report_reference -hierarchy > $ref_rep
    } errmsg]} {
        puts "$signature <bold><red>error: could not write reference report<end>"
        puts "$signature tool says -> $errmsg"
    }
}

# The gate level netlist, its constraints and its delays, published under the
# names "odatix pnr" looks for so this synthesis can be placed & routed by
# Innovus, ICC2 or any other tool declaring a pnr flow.
proc odatix_dc_netlist {signature} {
    global result_path top_level_module

    set basename ${top_level_module}
    set runname gates_dc

    puts "<bold>"
    puts "**************************************"
    puts "       Export Verilog Netlist "
    puts "**************************************"
    puts "<end>"

    # Verilog output settings
    set verilogout_equation	false
    set verilogout_no_tri	true
    set verilogout_single_bit  false
    set verilogout_show_unconnected_pins true

    change_names -rules verilog -hierarchy -verbose > change_names_verilog

    write -hierarchy -format verilog -output ${result_path}/${basename}_${runname}.v

    puts "<bold>"
    puts "**************************************"
    puts "     Generate SDF and SDC files"
    puts "**************************************"
    puts "<end>"

    write_sdf ${result_path}/${basename}_${runname}.sdf
    write_sdc ${result_path}/${basename}_${runname}.sdc

    odatix_publish_handoff \
        ${result_path}/${basename}_${runname}.v \
        ${result_path}/${basename}_${runname}.sdc \
        ${result_path}/${basename}_${runname}.sdf \
        $signature
}
