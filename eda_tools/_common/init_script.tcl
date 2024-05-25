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

    set signature "<grey>\[init_script.tcl\]<end>"

    ######################################
    # Create directories
    ######################################

    exec /bin/sh -c "mkdir -p $tmp_path"
    exec /bin/sh -c "mkdir -p $report_path"
    exec /bin/sh -c "mkdir -p $result_path"
    exec /bin/sh -c "mkdir -p $log_path"

    ######################################
    # copy file (optionnaly)
    ######################################
    # get target 
    if {[catch {
        set f [open $target_file]
        set target [gets $f]
        close $f
    } errmsg]} {
        error "$signature <bold><red>could not open target file '$target_file'<end>"
        puts "$signature tool says -> $errmsg <end>"
        exit -1
    }

    set verilog_error 0

    # quick and dirty bool conversion in case bool is not supported
    set file_copy_enable_bool [expr {!!$file_copy_enable}]
    set script_copy_enable_bool [expr {!!$script_copy_enable}]

    if {$file_copy_enable_bool == 1} {
        if {[catch {
            exec /bin/sh -c "cp $file_copy_source $tmp_path/$file_copy_dest"
        } errmsg]} {
            error "$signature <bold><red>error: could not copy '$file_copy_source' into '$tmp_path/$file_copy_dest'<end>"
            puts "$signature tool says -> $errmsg <end>"
            exit -1
        }
    }

    if {$script_copy_enable_bool == 1} {
        if {[catch {
            exec /bin/sh -c "cp $script_copy_source $script_path"
        } errmsg]} {
            error "$signature <bold><red>error: could not copy '$script_copy_source' into '$script_path'<end>"
            puts "$signature tool says -> $errmsg <end>"
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