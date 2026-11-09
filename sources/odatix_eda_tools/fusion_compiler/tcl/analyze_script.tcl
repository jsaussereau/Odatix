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


# Read the sources of the design into the design library of the job. Sourced
# before the synthesis (fmax search, "elaborate" step), and alone for an RTL
# analysis ("odatix_mode analysis"), which also elaborates and checks the design.

if {[catch {

    set signature "<grey>\[analyze_script.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    set analysis_mode [expr {[info exists odatix_mode] && $odatix_mode == "analysis"}]

    # An analysis needs no technology: without one, the design library has no
    # reference library, which is enough to check the RTL.
    odatix_fc_create_lib $signature $analysis_mode

    ######################################
    # Read source files
    ######################################

    set read_error 0

    # The file list of the design, when it has one ("filelist" in its settings,
    # or filelist.f at the root of its RTL): its order, include directories and
    # macros are kept. Consecutive files of a same language are analyzed
    # together, as a compiler given the list would.
    set design_sources [odatix_design_sources $signature]
    set define_list [dict get $design_sources defines]
    set define_option [expr {[llength $define_list] ? [list -define $define_list] : {}}]
    if {[llength [dict get $design_sources incdirs]]} {
        set_app_var search_path [concat [dict get $design_sources incdirs] [get_app_var search_path]]
    }

    set batches [list]
    if {[dict get $design_sources filelist] ne ""} {
        puts "$signature <cyan>Using filelist: [dict get $design_sources filelist]<end>"
        set batch_format ""
        set batch_files [list]
        foreach line [dict get $design_sources files] {
            set format [odatix_hdl_format $line]
            if {$format eq "" || [string match "*.svh" $line] || [string match "*.vh" $line]} {
                continue
            }
            if {$format ne $batch_format && [llength $batch_files]} {
                lappend batches [list $batch_format $batch_files]
                set batch_files [list]
            }
            set batch_format $format
            lappend batch_files $line
        }
        if {[llength $batch_files]} {
            lappend batches [list $batch_format $batch_files]
        }
    } else {
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
            lappend batches [list $format $filenames]
        }
    }

    foreach batch $batches {
        lassign $batch format files
        if {[catch {analyze -format $format -hdl_library $lib_name {*}$define_option $files} errmsg]} {
            puts "$signature <bold><red>error: failed reading the $format source files<end>"
            puts "$signature tool says -> $errmsg"
            set read_error 1
        }
    }

    if {$read_error && !$continue_on_error} {
        exit -1
    }

    if {$analysis_mode} {

        report_progress 20 $synth_statusfile

        if {[catch {elaborate -hdl_library $lib_name $top_level_module}]} {
            exit -1
        }
        report_progress 40 $synth_statusfile

        # What does not link (a module defined nowhere, a port it lacks) is a
        # finding: the design is checked all the same
        catch {set_top_module $top_level_module}
        report_progress 60 $synth_statusfile

        # Reports: what they say is in the log too, where analysis.yml reads it
        # check_netlist: floating nets and pins, multiple drivers, unbound
        # references. Not every one of these checks exists in every version:
        # one that fails is left out of the report.
        catch {check_netlist}
        catch {redirect $design_analysis {check_netlist}}
        catch {redirect $unresolved_report {report_reference -hierarchy}}

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
