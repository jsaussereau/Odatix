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
    set f [open $target_file]
    set target [gets $f]
    close $f

    set verilog_error 0

    if {bool($file_copy_enable) == bool(true)} {
        if {[file exists $file_copy_source]} {
            exec /bin/sh -c "cp $file_copy_source $tmp_path/$file_copy_dest"
        } else {
            error "analyze_script.tcl: <bold><red>error: target specified in '$target_file' ($target) has no assiociated target config file in './config' <end>"
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
                puts "<green>analyze_script.tcl<end>: <bold><red>error: could not find start delimiter '$start_delimiter' for parameters in top level, exiting <end>"
                puts "<green>analyze_script.tcl<end>: <cyan>note: make sure start/stop delimiters specified in the '_settings.yml' file of the architecture match the top level description in '$top_level_file'<end>"
                exit -1
            }
            set return_code_stop [exec /bin/sh -c "sed -n '/$stop_delimiter/p' $tmp_path/rtl/$top_level_file"]
            if {$return_code_stop == ""} {
                puts "<green>analyze_script.tcl<end>: <bold><red>error: could not find stop delimiter '$stop_delimiter' for parameters in top level, exiting <end>"
                puts "<green>analyze_script.tcl<end>: <cyan>note: make sure start/stop delimiters specified in the '_settings.yml' file of the architecture match the top level description in '$top_level_file'<end>"
                exit -1
            }

            # copy to top level file
            if {[catch {exec /bin/sh -c "sed -i '/$start_delimiter/,/$stop_delimiter/!b;//!d;/$stop_delimiter/e cat ./${arch_path}/$architecture.txt' $tmp_path/rtl/$top_level_file"} errmsg]} {
                puts "<green>analyze_script.tcl<end>: <bold><red>error: error while copy parameters to top level file, exiting <end>"
                puts "<green>analyze_script.tcl<end>: <cyan>note: you might use unsupported characters<end>"
                puts "<green>analyze_script.tcl<end>: tool says -> $errmsg <end>"
                exit -1
            }
        } else {
            #puts "analyze_script.tcl: <bold><yellow>warning: architecture specified in '$architecture_file' ($target) has no assiociated target config file in directory '${arch_path}', using default parameters <end>"
            puts "<green>analyze_script.tcl<end>: <bold><red>error: architecture specified in '$architecture_file' ($target) has no assiociated parameter file in directory '${arch_path}', exiting <end>"
            puts "<green>analyze_script.tcl<end>: <cyan>note: make sure the file '$architecture.txt' in '${arch_path}'<end>"
            exit -1
        }
    }

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