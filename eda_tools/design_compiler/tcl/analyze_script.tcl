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
    source scripts/synopsys_dc.setup

    ######################################
    # Read source files
    ######################################
    suppress_message { AUTOREAD-303 AUTOREAD-107 AUTOREAD-105 AUTOREAD-102 AUTOREAD-100 VER-26 }

    #set filenames [split [exec find $rtl_path/ -type f ( -name *.sv -o -name *.v )] \n]
    #set filenames [split [exec find $rtl_path/core $rtl_path/soc -type f -name *.sv ! -name soc_config.sv ] \n]

    # read verilog source files
    if {[catch {analyze -library WORK -f verilog -autoread -recursive $tmp_path/rtl/} errmsg]} {
        if {$verilog_filenames == ""} {
            puts "<green>analyze_script.tcl<end>: <cyan>note: no verilog file in source directory<end>"
        } {
            puts "<green>analyze_script.tcl<end>: <bold><red>error: failed reading verilog source files<end>"
            puts "<green>analyze_script.tcl<end>: tool says -> $errmsg"
        }
        set verilog_error 1
    }

    # read systemverilog source files
    if {[catch {analyze -library WORK -f sverilog -autoread -recursive $tmp_path/rtl/} errmsg]} {
        if {$verilog_filenames == ""} {
            puts "<green>analyze_script.tcl<end>: <cyan>note: no verilog file in source directory<end>"
        } {
            puts "<green>analyze_script.tcl<end>: <bold><red>error: failed reading verilog source files<end>"
            puts "<green>analyze_script.tcl<end>: tool says -> $errmsg"
        }
        set verilog_error 1
    }

    # read vhdl source files
    if {[catch {analyze -library WORK -f vhdl -autoread -recursive $tmp_path/rtl/} errmsg]} {
        if {$vhdl_filenames == ""} {
            puts "<green>analyze_script.tcl<end>: <cyan>note: no vhdl file in source directory<end>"
        } else {
            puts "<green>analyze_script.tcl<end>: <bold><red>error: failed reading vhdl source files<end>"
            puts "<green>analyze_script.tcl<end>: tool says -> $errmsg"
        }
        if {$verilog_error == 1} {
            puts "<green>analyze_script.tcl<end>:<red>error: failed reading both verilog and vhdl source files, exiting"
            exit_now
        }
    }

} ]} {
    puts "<green>analyze_script.tcl<end>: <bold><red>error: unhandled tcl error, exiting<end>"
    puts "<green>analyze_script.tcl<end>: <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    puts "<green>analyze_script.tcl<end>: <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit_now
}