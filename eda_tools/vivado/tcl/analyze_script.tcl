#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

if {[catch {

    source scripts/settings.tcl

    ######################################
    # Read source files
    ######################################
    #set filenames [split [exec find $rtl_path/ -type f ( -name *.sv -o -name *.v )] \n]
    #set filenames [split [exec find $rtl_path/core $rtl_path/soc -type f -name *.sv ! -name soc_config.sv ] \n]

    # read verilog source files
    set verilog_filenames [split [exec find $tmp_path/rtl/ -type f ( -name *.v -o -name *.sv )] \n]
    if {[catch {read_verilog $verilog_filenames} errmsg]} {
        if {$verilog_filenames == ""} {
            puts "<green>analyze_script.tcl<end>: <cyan>note: no verilog file in source directory<end>"
        } {
            puts "<green>analyze_script.tcl<end>: <bold><red>error: failed reading verilog source files<end>"
            puts "<green>analyze_script.tcl<end>: tool says -> $errmsg"
        }
        set verilog_error 1
    }

    # read vhdl source files
    set vhdl_filenames [split [exec find $tmp_path/rtl/ -type f ( -name *.vhd -o -name *.vhdl )] \n]
    if {[catch {read_vhdl $vhdl_filenames} errmsg]} {
        if {$vhdl_filenames == ""} {
            puts "<green>analyze_script.tcl<end>: <cyan>note: no vhdl file in source directory<end>"
        } else {
            puts "<green>analyze_script.tcl<end>: <bold><red>error: failed reading vhdl source files<end>"
            puts "<green>analyze_script.tcl<end>: tool says -> $errmsg"
        }
        if {$verilog_error == 1} {
            puts "<green>analyze_script.tcl<end>:<red>error: failed reading both verilog and vhdl source files, exiting"
            exit -1
        }
    }

} ]} {
    puts "<green>analyze_script.tcl<end>: <bold><red>error: unhandled tcl error, exiting<end>"
    puts "<green>analyze_script.tcl<end>: <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    puts "<green>analyze_script.tcl<end>: <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}