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

    set signature "<grey>\[analyze_script.tcl\]<end>"

    ######################################
    # Read source files
    ######################################


    if {[file exists "$rtl_path/filelist.f"]} {

        puts "$signature <cyan>Using filelist: $rtl_path/filelist.f<end>"

        set fp [open "$rtl_path/filelist.f" r]

        while {[gets $fp line] >= 0} {
            set line [string trim $line]
            if {$line eq ""} {
                continue
            }
            if {[string match "*.v" $line]} {
                read_verilog $line
            } elseif {[string match "*.sv" $line] || [string match "*.svh" $line]} {
                read_verilog $line
            } elseif {[string match "*.vhd" $line]} {
                read_vhdl $line
            }
        }
        close $fp

    } else {

        set rtl_path [file normalize $rtl_path]

        set verilog_error 0
        set sverilog_error 0

        # read verilog source files
        set verilog_filenames [get_files_recursive $rtl_path {*.v *.sv}]
        puts "$signature <cyan>Verilog/SystemVerilog files:<end>"
        foreach file $verilog_filenames {
            puts "  - $file"
        }
        if {[catch {read_verilog $verilog_filenames} errmsg]} {
            if {$verilog_filenames == ""} {
                puts "$signature <cyan>note: no verilog file in source directory<end>"
            } else {
                puts "$signature <bold><red>error: failed reading verilog source files<end>"
                puts "$signature tool says -> $errmsg"
            }
            set verilog_error 1
        }

        # read vhdl source files
        set vhdl_filenames [get_files_recursive $rtl_path {*.vhd *.vhdl}]
        puts "$signature <cyan>VHDL files:<end>"
        foreach file $vhdl_filenames {
            puts "  - $file"
        }
        if {[catch {read_vhdl $vhdl_filenames} errmsg]} {
            if {$vhdl_filenames == ""} {
                puts "$signature <cyan>note: no vhdl file in source directory<end>"
            } else {
                puts "$signature <bold><red>error: failed reading vhdl source files<end>"
                puts "$signature tool says -> $errmsg"
            }
            if {$verilog_error == 1} {
                puts "$signature <red>error: failed reading both verilog and vhdl source files, exiting"
                exit -1
            }
        }
    }


    ## test avec -tclargs du vivado
    set odatix_mode ""

    if {[llength $argv] > 0} {
        set odatix_mode [lindex $argv 0]
    }

    puts "DEBUG mode = $odatix_mode"

    if {$odatix_mode == "analysis"} {
        report_progress 100 $synth_statusfile
    }



} ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    puts "$signature <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}