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

    set signature "<grey>\[analyze_script.tcl\]<end>"

    source scripts/settings.tcl

    define_design_lib $lib_name -path $work_path

    if {[catch {
        source scripts/synopsys_dc_setup.tcl
    } errmsg]} {
        puts "$signature <bold><red>error: could not source 'synopsys_dc_setup.tcl'<end>"
        puts "$signature <cyan>note: design compiler needs a technology file, make sure you added one in 'target_design_compiler.yml'<end>"
        exit -1
    }

    ######################################
    # Read source files
    ######################################


    set verilog_error 0
    set sverilog_error 0
    set vhdl_error 0
    
    # Read from filelist (the file must be named filelist.f)
    if {[file exists "$rtl_path/filelist.f"]} {

        puts "$signature <cyan>Using filelist: $rtl_path/filelist.f<end>"
        set fp [open "$rtl_path/filelist.f" r]

        while {[gets $fp line] >= 0} {
            set line [string trim $line]
            if {$line eq ""} {
                continue
            }
            if {[string match "*.v" $line]} {
                analyze -library $lib_name -f verilog $line
            } elseif {[string match "*.sv" $line] || [string match "*.svh" $line]} {
                analyze -library $lib_name -f sverilog $line
            } elseif {[string match "*.vhd" $line] || [string match "*.vhdl" $line]} {
                analyze -library $lib_name -f vhdl $line
            }
        }
        close $fp
    } else {
        #read from sources
        suppress_message { AUTOREAD-303 AUTOREAD-107 AUTOREAD-105 AUTOREAD-102 AUTOREAD-100 VER-26 }


        
        set rtl_path [file normalize $rtl_path]


        # read verilog source files
        set verilog_filenames [get_files_recursive $rtl_path {*.v}]
        if {[llength $verilog_filenames] == 0} {
            puts "$signature <cyan>note: no Verilog file in source directory<end>"
        } else {
            puts "$signature <cyan>Verilog files:<end>"
            foreach file $verilog_filenames {
                puts "  <cyan>- $file<end>"
            }
            catch {analyze -library $lib_name -f verilog $verilog_filenames} errmsg
            if {[
                catch {analyze -library $lib_name -f verilog $verilog_filenames} errmsg
            ]} {
                puts "$signature <bold><red>error: failed reading Verilog source files<end>"
                puts "$signature tool says -> $errmsg"
                set verilog_error 1
            }
        }

        # read systemverilog source files
        set sverilog_filenames [get_files_recursive $rtl_path {*.sv}]
        puts "length sv files: [llength $sverilog_filenames]"
        if {[llength $sverilog_filenames] == 0} {
            puts "$signature <cyan>note: no SystemVerilog file in source directory<end>"
        } else {
            puts "$signature <cyan>SystemVerilog files:<end>"
            foreach file $sverilog_filenames {
                puts "  <cyan>- $file<end>"
            }
            catch {analyze -library $lib_name -f sverilog $sverilog_filenames} errmsg
            if {[
                catch {analyze -library $lib_name -f sverilog $sverilog_filenames} errmsg
            ]} {
                puts "$signature <bold><red>error: failed reading SystemVerilog source files<end>"
                puts "$signature tool says -> $errmsg"
                set sverilog_error 1
            }
        }

        # read vhdl source files
        set vhdl_filenames [get_files_recursive $rtl_path {*.vhd *.vhdl}]
        if {[llength $vhdl_filenames] == 0} {
            puts "$signature <cyan>note: no VHDL file in source directory<end>"
        } else {
            puts "$signature <cyan>VHDL files:<end>"
            foreach file $vhdl_filenames {
                puts "  <cyan>- $file<end>"
            }
            catch {analyze -library $lib_name -f vhdl  $vhdl_filenames} errmsg
            if {[
                catch {analyze -library $lib_name -f vhdl  $vhdl_filenames} errmsg
            ]} {
                puts "$signature <bold><red>error: failed reading VHDL source files<end>"
                puts "$signature tool says -> $errmsg"
                if {$verilog_error == 1 && $sverilog_error == 1} {
                    puts "$signature <red>error: failed reading both Verilog/SystemVerilog and VHDL source files, exiting"
                    set vhdl_error 1
                }
            }
        }
    }



    if {[info exists odatix_mode] && $odatix_mode == "analysis"} {

        report_progress 20 $synth_statusfile

        # Create design
        elaborate ${top_level_module} -library $lib_name
        report_progress 40 $synth_statusfile


        # Set current design
        current_design $top_level_module

        # Resolve references
        link
        report_progress 60 $synth_statusfile

        # Reports
        check_design > $design_analysis
        report_reference > $unresolved_report
        report_reference
        check_design
        link > $report_path/link.rep

        report_progress 80 $synth_statusfile


        # Define arch_name variable for printing 
        set arch_name "Unknown"
        if {[file exists $architecture_file]} {
            set fp_arch [open $architecture_file r]
            set arch_name [string trim [read $fp_arch]]
            close $fp_arch
        }



        set unresolved_count 0
        set result ""
        set filename ""
        set line_number ""
        set signal_name ""
        set code_error 0


        if {[file exists "$log_path/analysis.log"]} {

            set fp_log [open "$log_path/analysis.log" r]
            set log_data [read $fp_log]
            close $fp_log

        if {[regexp {Error:\s+(.+):([0-9]+):\s+The symbol '([^']+)' is not defined} \
            $log_data \
            -> filename line_number signal_name]} {
                set code_error 1
        } elseif {[regexp {Design '([^']+)' has '([0-9]+)' unresolved references} \
            $log_data \
            -> result unresolved_count]} {
            # Values captured successfully
        }
        }



        puts " "
        puts " "
        puts "----------------------------------------"
        puts "<bold><cyan>Analysis Summary<end>"
        puts "----------------------------------------"

        puts "Architecture: $arch_name"
        puts "Top module: $top_level_module"
        #puts "Configuration: $variant"


        if {!$code_error} { 
            puts "Read Designs: <bold><green>PASSED<end>"
        } else {
                puts "Read Designs     : <bold><red>FAILED<end>"
                puts "Missing signal   : <bold><red>$signal_name<end>"
                puts "File             : <bold><red>[file tail $filename]<end>"
                puts "Line             : <bold><red>$line_number<end>"
        }


        if {!$code_error} {
            if {$unresolved_count == 0} {
                puts "<green>Unresolved Designs: $unresolved_count<end>"

            } else {
                puts "<yellow>Unresolved Designs: $unresolved_count<end>"
            }
        } else {
            puts "<red> There are some errors in the code, please check the full .log avaible in:<end> $log_path/analysis.log"

        }


        puts ""
        puts "<cyan>Press 'q' to view the analysis summary.<end>"

        if {!$vhdl_error && !$sverilog_error && !$verilog_error && !$code_error} {
            report_progress 100 $synth_statusfile
        } else {
            exit -1
        }


    }



} ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    puts "$signature <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}
