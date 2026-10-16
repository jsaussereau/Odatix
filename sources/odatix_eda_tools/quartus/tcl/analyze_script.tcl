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


# The source files of the design, for the project to compile (see
# odatix_quartus_create_project in quartus_common.tcl).
#
# Nothing is read here: Quartus reads the sources itself, from the project, in
# each executable that needs them. What this script does is list them, from the
# filelist of the design when it has one, from its source directory otherwise,
# and the directories an `include may look into.

if {[catch {

    source scripts/settings.tcl

    set signature "<grey>\[analyze_script.tcl\]<end>"

    set ::odatix_quartus_sources [list]
    set ::odatix_quartus_search_path [list]

    proc odatix_quartus_source_kind {source_file} {
        switch -- [string tolower [file extension $source_file]] {
            .v    { return VERILOG_FILE }
            .sv   { return SYSTEMVERILOG_FILE }
            .vhd  - .vhdl { return VHDL_FILE }
            .qip  { return QIP_FILE }
            .ip   { return IP_FILE }
        }
        # Headers (.vh, .svh) are included, not compiled
        return ""
    }

    if {[file exists "$rtl_path/filelist.f"]} {
        puts "$signature <cyan>Using filelist: $rtl_path/filelist.f<end>"
        set source_files [read_filelist "$rtl_path/filelist.f"]
    } else {
        set source_files [get_files_recursive [file normalize $rtl_path] {*.v *.sv *.vh *.svh *.vhd *.vhdl}]
    }

    puts "$signature <cyan>Source files:<end>"
    foreach source_file $source_files {
        set source_file [file normalize $source_file]
        set dir [file dirname $source_file]
        if {[lsearch -exact $::odatix_quartus_search_path $dir] < 0} {
            lappend ::odatix_quartus_search_path $dir
        }
        set kind [odatix_quartus_source_kind $source_file]
        if {$kind eq ""} {
            continue
        }
        puts "  - $source_file"
        lappend ::odatix_quartus_sources $source_file $kind
    }

    if {[llength $::odatix_quartus_sources] == 0} {
        puts "$signature <bold><red>error: no verilog, systemverilog or vhdl file in source directory, exiting<end>"
        exit -1
    }

} ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    puts "$signature <cyan>tcl error detail:<red>"
    puts "$errorInfo"
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}
