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
    # Create a local copy of source files
    ######################################
    exec /bin/sh -c "rm -rf $tmp_path/rtl"
    exec /bin/sh -c "mkdir -p $tmp_path/rtl"
    exec /bin/sh -c "rsync -av --exclude=\".*\" $rtl_path/* $tmp_path/rtl"

    ######################################
    # copy file (optionnaly)
    ######################################
    # get target 
    if {[catch {
        set f [open $target_file]
        set target [gets $f]
        close $f
    } errmsg]} {
        error "<green>init_script.tcl<end>: <bold><red>could not open target file '$target_file'<end>"
        puts "<green>init_script.tcl<end>: tool says -> $errmsg <end>"
        exit -1
    }

    set verilog_error 0

    if {bool($file_copy_enable) == bool(true)} {
        if {[catch {
            exec /bin/sh -c "cp $file_copy_source $tmp_path/$file_copy_dest"
        } errmsg]} {
            error "<green>init_script.tcl<end>: <bold><red>error: could not copy '$file_copy_source' into '$tmp_path/$file_copy_dest'<end>"
            puts "<green>init_script.tcl<end>: tool says -> $errmsg <end>"
            exit -1
        }
    }

    if {bool($script_copy_enable) == bool(true)} {
        if {[catch {
            exec /bin/sh -c "cp $script_copy_source $tmp_path/$script_path"
        } errmsg]} {
            error "<green>init_script.tcl<end>: <bold><red>error: could not copy '$script_copy_source' into '$tmp_path/$script_path'<end>"
            puts "<green>init_script.tcl<end>: tool says -> $errmsg <end>"
            exit -1
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
                puts "<green>init_script.tcl<end>: <bold><red>error: could not find start delimiter '$start_delimiter' for parameters in top level, exiting <end>"
                puts "<green>init_script.tcl<end>: <cyan>note: make sure start/stop delimiters specified in the '_settings.yml' file of the architecture match the top level description in '$top_level_file'<end>"
                exit -1
            }
            set return_code_stop [exec /bin/sh -c "sed -n '/$stop_delimiter/p' $tmp_path/rtl/$top_level_file"]
            if {$return_code_stop == ""} {
                puts "<green>init_script.tcl<end>: <bold><red>error: could not find stop delimiter '$stop_delimiter' for parameters in top level, exiting <end>"
                puts "<green>init_script.tcl<end>: <cyan>note: make sure start/stop delimiters specified in the '_settings.yml' file of the architecture match the top level description in '$top_level_file'<end>"
                exit -1
            }

            # copy to top level file
            if {[catch {
                exec /bin/sh -c "sed -i '/$start_delimiter/,/$stop_delimiter/!b;//!d;/$stop_delimiter/e cat ./${arch_path}/$architecture.txt' $tmp_path/rtl/$top_level_file"
            } errmsg]} {
                puts "<green>init_script.tcl<end>: <bold><red>error: error while copy parameters to top level file, exiting <end>"
                puts "<green>init_script.tcl<end>: <cyan>note: you might use unsupported characters<end>"
                puts "<green>init_script.tcl<end>: tool says -> $errmsg <end>"
                exit -1
            }
        } else {
            #puts "init_script.tcl: <bold><yellow>warning: architecture specified in '$architecture_file' ($target) has no assiociated target config file in directory '${arch_path}', using default parameters <end>"
            puts "<green>init_script.tcl<end>: <bold><red>error: architecture specified in '$architecture_file' ($target) has no assiociated parameter file in directory '${arch_path}', exiting <end>"
            puts "<green>init_script.tcl<end>: <cyan>note: make sure the file '$architecture.txt' in '${arch_path}'<end>"
            exit -1
        }
    }

} ]} {
    puts "<green>init_script.tcl<end>: <bold><red>error: unhandled tcl error, exiting<end>"
    puts "<green>init_script.tcl<end>: <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    puts "<green>init_script.tcl<end>: <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit_now
}