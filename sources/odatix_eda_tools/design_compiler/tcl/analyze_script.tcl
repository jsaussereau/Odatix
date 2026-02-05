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
    suppress_message { AUTOREAD-303 AUTOREAD-107 AUTOREAD-105 AUTOREAD-102 AUTOREAD-100 VER-26 }
    
    set rtl_path [file normalize $rtl_path]

    set verilog_error 0
    set sverilog_error 0

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
    set sverilog_filenames [get_files_recursive $rtl_path {*.sv *.svh}]
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
                exit -1
            }
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
