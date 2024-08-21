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

    define_design_lib WORK -path $work_path

    puts "$signature <cyan>note: you can safely ignore the error message (UID-4) below.<end>"

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
    suppress_message { AUTOREAD-303 AUTOREAD-107 AUTOREAD-105 AUTOREAD-102 AUTOREAD-100 VER-26 }
    
    set verilog_error 0
    set sverilog_error 0

    # read verilog source files
    puts "\n$signature reading verilog...<end>"
    if {![
        analyze -library $lib_name -f verilog -autoread -recursive $tmp_path/rtl/
    ]} {
        puts "$signature <cyan>note: failed reading verilog source files<end>"
        set verilog_error 1
    }

    # read systemverilog source files
    puts "\n$signature reading system verilog...<end>"
    if {![
        analyze -library $lib_name -f sverilog -autoread -recursive $tmp_path/rtl/
    ]} {
        puts "$signature <cyan>note: failed reading systemverilog source files<end>"
        set sverilog_error 1
    }

    # read vhdl source files
    puts "\n$signature reading vhdl verilog...<end>"
    if {![
        analyze -library $lib_name -f vhdl -autoread -recursive $tmp_path/rtl/
    ]} {
        puts "$signature <cyan>note: failed reading vhdl source files<end>"
        if {$verilog_error == 1 && $sverilog_error == 1} {
            puts "$signature <red>error: failed reading verilog, system verilog and vhdl source files, exiting<end>"
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