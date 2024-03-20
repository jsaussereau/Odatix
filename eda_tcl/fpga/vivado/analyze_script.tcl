#
# Copyright(C) 2022 by Jonathan Saussereau. All rights reserved.
# 
# All source codes and documentation contain proprietary confidential
# information and are distributed under license. It may be used, copied
# and/or disclosed only pursuant to the terms of a valid license agreement
# with Jonathan Saussereau. This copyright must be retained at all times.
#
# Last edited: 2022/07/07 13:10
#

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

if {bool($file_copy_enable) == bool(true)} {
    if {[file exists $file_copy_source]} {
        exec /bin/sh -c "cp $file_copy_source $tmp_path/$file_copy_dest"
    } else {
        error "<bold><red>script error: target specified in '$target_file' ($target) has no assiociated target config file in './config' <end>"
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

if {[file exists ./parameters/$architecture.txt]} {
    set rc [catch {exec /bin/sh -c "sed -i '/$start_delimiter/,/$stop_delimiter/!b;//!d;/$stop_delimiter/e cat ./parameters/$architecture.txt' $tmp_path/rtl/$top_level_file"}]
    if {$rc != 0} {
        puts "<bold><yellow>script warning: bad start/stop delimiters for parameters, using default parameters <end>"
        #exit_now
    }
} else {
    puts "<bold><yellow>script warning: architecture specified in '$architecture_file' ($target) has no assiociated target config file in directory 'parameters', using default parameters <end>"
    #exit_now
}

######################################
# Read source files
######################################
#set filenames [split [exec find $rtl_path/ -type f ( -name *.sv -o -name *.v )] \n]
#set filenames [split [exec find $rtl_path/core $rtl_path/soc -type f -name *.sv ! -name soc_config.sv ] \n]
set filenames [split [exec find $tmp_path/rtl/ -type f -name *$rtl_file_format] \n]

read_verilog $filenames
