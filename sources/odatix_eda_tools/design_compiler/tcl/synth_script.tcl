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

if {[catch {
    
    source scripts/settings.tcl

    set signature "<grey>\[synth_script.tcl\]<end>"

    set basename ${top_level_module}
    set runname gates_dc

    report_progress 2 $synth_statusfile

    #puts "<bold>"
    #puts "**************************************"
    #puts "          Analyze RTL files"
    #puts "**************************************"
    #puts "<end>"
    #
    #source ./dc_analyze.tcl


    puts "<bold>"
    puts "**************************************"
    puts "          Elaborate Design"
    puts "**************************************"
    puts "<end>"

    elaborate ${top_level_module} -library $lib_name

    link
    report_progress 8 $synth_statusfile

    puts "<bold>"
    puts "**************************************"
    puts "          Uniquify Design"
    puts "**************************************"
    puts "<end>"
    uniquify

    report_progress 10 $synth_statusfile

    # remove "remove constant", "merge register" and "complemented port" information
    suppress_message { OPT-1206 OPT-319 OPT-1215 }

    puts "<bold>"
    puts "**************************************"
    puts "  Save Database for further loading"
    puts "**************************************"
    puts "<end>"

    write -hierarchy -format ddc -output ${result_path}/${basename}.ddc

    report_progress 13 $synth_statusfile

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


    create_clock -name $clock_signal -period $clock_period -waveform [list 0.0 [expr $clock_period / 2.0]] [list $clock_signal]

    set_wire_load_mode segmented
    set_clock_uncertainty -hold $clock_skew $clock_signal
    set_clock_uncertainty -setup $clock_skew $clock_signal
    set_max_transition 0.5 $reset_signal

    check_timing

    report_progress 10 $synth_statusfile

    puts "<bold>"
    puts "**************************************"
    puts "     Synthesis and Optimization"
    puts "**************************************"
    puts "<end>"

    set_fix_multiple_port_nets -all [all_designs]
    set_fix_multiple_port_nets -outputs -feedthroughs -constants
    #compile -map_effort medium -boundary_optimization
    #compile_ultra -area_high_effort_script -retime 
    #compile
    compile_ultra -timing_high_effort_script -retime

    report_progress 90 $synth_statusfile

    write -hierarchy -format ddc -output ${result_path}/${basename}_gates.ddc

    report_progress 93 $synth_statusfile

    puts "<bold>"
    puts "**************************************"
    puts "            Write Reports"
    puts "**************************************"
    puts "<end>"

    if {[catch {
        # Report Power 
        #puts "Writing power report file '${REPORT_DIR}/${OUTPUT_PREFIX}power.rep'."
        #report_power -analysis_effort high > ${REPORT_DIR}/${OUTPUT_PREFIX}power.rep
    } errmsg]} {
        puts "$signature <bold><red>error: could not write power report<end>"
        puts "$signature tool says -> $errmsg"
    }
    if {[catch {
        # Report Area 
        puts "Writing area report file '$area_rep'."
        report_area -nosplit -hierarchy > $area_rep
        # create the utilization_rep file 
        close [open $utilization_rep w]
        echo -n "Cell count:                     " > $utilization_rep
        sizeof_collection [ get_cells  -hier  *] >> $utilization_rep
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

    report_progress 96 $synth_statusfile

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


    report_progress 0 $synth_statusfile

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