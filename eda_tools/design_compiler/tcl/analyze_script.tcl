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

    source scripts/synopsys_dc.setup
    source scripts/settings.tcl

    ######################################
    # Create a local copy of source files
    ######################################
    exec /bin/sh -c "rm -rf $tmp_path/rtl"
    exec /bin/sh -c "mkdir -p $tmp_path/rtl"
    exec /bin/sh -c "rsync -av --exclude=\".*\" $rtl_path/* $tmp_path/rtl"

    ######################################
    # copy file (optionnaly)
    ######################################
    # get target 
    set f [open $target_file]
    set target [gets $f]
    close $f

    set verilog_error 0

    # quick and dirty bool conversion 
    set file_copy_enable_bool [expr {!!$file_copy_enable}]
    
    if {$file_copy_enable_bool == 1} {
        if {[file exists $file_copy_source]} {
            exec /bin/sh -c "cp $file_copy_source $tmp_path/$file_copy_dest"
        } else {
            error "<green>analyze_script.tcl<end>: <bold><red>error: target specified in '$target_file' ($target) has no assiociated target config file in './config' <end>"
            exit_now
        }
    }


    ######################################
    # update top level parameters
    ######################################
    # add escape characters
    set start_delimiter [exec /bin/sh -c "echo \"$start_delimiter\" | sed 's|/|\\\\\\\\/|g'"]
    set stop_delimiter [exec /bin/sh -c "echo \"$stop_delimiter\" | sed 's|/|\\\\\\\\/|g'"]

    # get architecture
    set f [open $architecture_file]
    set architecture [gets $f]
    close $f

    if {bool($use_parameters) == bool(true)} {
        if {[file exists ./${arch_path}/$architecture.txt]} {
            # check if there is a match
            set return_code_start [exec /bin/sh -c "sed -n '/$start_delimiter/p' $tmp_path/rtl/$top_level_file"]
            if {$return_code_start == ""} {
                puts "<green>analyze_script.tcl<end>: <bold><red>error: could not find start delimiter '$start_delimiter' for parameters in top level, exiting <end>"
                puts "<green>analyze_script.tcl<end>: <cyan>note: make sure start/stop delimiters specified in the '_settings.yml' file of the architecture match the top level description in '$top_level_file'<end>"
                exit_now
            }
            set return_code_stop [exec /bin/sh -c "sed -n '/$stop_delimiter/p' $tmp_path/rtl/$top_level_file"]
            if {$return_code_stop == ""} {
                puts "<green>analyze_script.tcl<end>: <bold><red>error: could not find stop delimiter '$stop_delimiter' for parameters in top level, exiting <end>"
                puts "<green>analyze_script.tcl<end>: <cyan>note: make sure start/stop delimiters specified in the '_settings.yml' file of the architecture match the top level description in '$top_level_file'<end>"
                exit_now
            }

            # copy to top level file
            if {[catch {exec /bin/sh -c "sed -i '/$start_delimiter/,/$stop_delimiter/!b;//!d;/$stop_delimiter/e cat ./${arch_path}/$architecture.txt' $tmp_path/rtl/$top_level_file"} errmsg]} {
                puts "<green>analyze_script.tcl<end>: <bold><red>error: error while copy parameters to top level file, exiting <end>"
                puts "<green>analyze_script.tcl<end>: <cyan>note: you might use unsupported characters<end>"
                puts "<green>analyze_script.tcl<end>: tool says -> $errmsg <end>"
                exit_now
            }
        } else {
            #puts "analyze_script.tcl: <bold><yellow>warning: architecture specified in '$architecture_file' ($target) has no assiociated target config file in directory '${arch_path}', using default parameters <end>"
            puts "<green>analyze_script.tcl<end>: <bold><red>error: architecture specified in '$architecture_file' ($target) has no assiociated parameter file in directory '${arch_path}', exiting <end>"
            puts "<green>analyze_script.tcl<end>: <cyan>note: make sure the file '$architecture.txt' in '${arch_path}'<end>"
            exit_now
        }
    }

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