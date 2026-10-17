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

# Reads the sources. A synthesis then elaborates them (step_elaborate.tcl); an
# RTL analysis (odatix_mode "analysis") elaborates and checks them here. What
# the analysis found is read from the log by analysis.yml.

if {[catch {

    set signature "<grey>\[analyze_script.tcl\]<end>"

    source scripts/settings.tcl

    define_design_lib $lib_name -path $work_path

    set analysis_mode [expr {[info exists odatix_mode] && $odatix_mode == "analysis"}]

    # An analysis targets no technology: without a setup script, the design is
    # elaborated into generic cells (GTECH), which is all checking it needs.
    if {$analysis_mode && ![file exists $script_path/synopsys_dc_setup.tcl]} {
        puts "$signature <cyan>note: no technology, elaborating into generic cells<end>"
        set target_library ""
        set link_library "*"
    } elseif {[catch {
        source scripts/synopsys_dc_setup.tcl
    } errmsg]} {
        puts "$signature <bold><red>error: could not source 'synopsys_dc_setup.tcl'<end>"
        puts "$signature <cyan>note: design compiler needs a technology file, make sure you added one in 'target_design_compiler.yml'<end>"
        exit -1
    }

    ######################################
    # Read source files
    ######################################

    set read_error 0

    # Read from filelist (the file must be named filelist.f)
    if {[file exists "$rtl_path/filelist.f"]} {

        puts "$signature <cyan>Using filelist: $rtl_path/filelist.f<end>"
        foreach line [read_filelist "$rtl_path/filelist.f"] {
            if {[string match "*.v" $line]} {
                set format verilog
            } elseif {[string match "*.sv" $line] || [string match "*.svh" $line]} {
                set format sverilog
            } elseif {[string match "*.vhd" $line] || [string match "*.vhdl" $line]} {
                set format vhdl
            } else {
                continue
            }
            if {![analyze -library $lib_name -f $format $line]} {
                set read_error 1
            }
        }
    } else {
        #read from sources
        suppress_message { AUTOREAD-303 AUTOREAD-107 AUTOREAD-105 AUTOREAD-102 AUTOREAD-100 VER-26 }

        set rtl_path [file normalize $rtl_path]

        foreach {format label patterns} {
            verilog  Verilog       {*.v}
            sverilog SystemVerilog {*.sv}
            vhdl     VHDL          {*.vhd *.vhdl}
        } {
            set filenames [get_files_recursive $rtl_path $patterns]
            if {[llength $filenames] == 0} {
                continue
            }
            puts "$signature <cyan>$label files:<end>"
            foreach file $filenames {
                puts "  <cyan>- $file<end>"
            }
            if {[catch {analyze -library $lib_name -f $format $filenames} result] || !$result} {
                puts "$signature <bold><red>error: failed reading $label source files<end>"
                set read_error 1
            }
        }
    }

    if {$analysis_mode} {

        report_progress 20 $synth_statusfile

        if {$read_error} {
            exit -1
        }

        if {![elaborate ${top_level_module} -library $lib_name]} {
            exit -1
        }
        report_progress 40 $synth_statusfile

        if {[catch {current_design $top_level_module}]} {
            exit -1
        }
        # What does not link (a module defined nowhere, a port it lacks) is a
        # finding: the design is checked all the same
        link
        report_progress 60 $synth_statusfile

        # Reports: what they say is in the log too, where analysis.yml reads it
        check_design
        check_design > $design_analysis
        report_reference > $unresolved_report

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
