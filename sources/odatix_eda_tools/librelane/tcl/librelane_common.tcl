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

#################################################################################
# Odatix - LibreLane common procedures
#################################################################################
#
# The scripts of this tool run in tclsh, not in an EDA tool: LibreLane is a
# command line program, and every job only writes its configuration and runs
# it on part of the Classic flow ("--from" / "--to"). What LibreLane computes
# stays in its run directory ("runs/<tag>"); librelane_state.py reads it back
# into reports Odatix extracts metrics from.
#
# The flow of the job ("parameters" in tool.yml) is passed to LibreLane as
# configuration overrides: every parameter named in capitals is a LibreLane
# variable (SYNTH_STRATEGY, FP_CORE_UTIL, PL_TARGET_DENSITY_PCT, ...), given
# with "-c NAME=value" unless it is empty. So any variable of LibreLane can be a
# strategy, or an axis of a design space exploration, without changing a script.

source scripts/settings.tcl

set librelane_config_file  $tmp_path/config.json
set librelane_runs_path    $tmp_path/runs
set librelane_state_path   $tmp_path/state
set librelane_state_script $script_path/librelane_state.py

# Where each step of a job starts and stops in the Classic flow. The two ends
# are LibreLane step ids ("" for the start or the end of the flow); a step id
# appearing several times in the flow takes a "-<n>" suffix from its second
# occurrence on. VHDLClassic is Classic without the Verilog linting steps, so
# the same ranges hold for both.
set librelane_step_ranges [dict create \
    synthesis [list ""                       "OpenROAD.STAPrePNR"]   \
    floorplan [list "OpenROAD.Floorplan"     "Odb.ApplyDEFTemplate"] \
    place     [list "OpenROAD.GlobalPlacement" "OpenROAD.DetailedPlacement"] \
    cts       [list "OpenROAD.CTS"           "OpenROAD.STAMidPNR-2"] \
    route     [list "OpenROAD.GlobalRouting" "OpenROAD.STAPostPNR"]  \
    signoff   [list "OpenROAD.IRDropReport"  ""]                     \
]
set librelane_step_order [list synthesis floorplan place cts route signoff]

######################################
# Technology
######################################

proc odatix_librelane_technology {signature} {
    # The PDK and standard cell library of the job's target, set by the
    # technology script the target file copies in (technology_setup.tcl). An
    # analysis has no target: it lints and elaborates against sky130A.
    global librelane_pdk librelane_scl librelane_pdk_root
    set librelane_pdk      ""
    set librelane_scl      ""
    set librelane_pdk_root ""
    if {[file exists scripts/technology_setup.tcl]} {
        if {[catch {uplevel #0 {source scripts/technology_setup.tcl}} errmsg]} {
            puts "$signature <bold><red>error: could not source 'technology_setup.tcl'<end>"
            puts "$signature tool says -> $errmsg"
            exit -1
        }
    }
    if {$librelane_pdk eq ""} {
        set librelane_pdk sky130A
        puts "$signature <cyan>no technology script for this target, using PDK $librelane_pdk<end>"
    }
}

######################################
# Configuration
######################################

proc odatix_json_string {text} {
    set map [list "\\" "\\\\" "\"" "\\\"" "\n" "\\n" "\r" "\\r" "\t" "\\t"]
    return "\"[string map $map $text]\""
}

proc odatix_json_list {items} {
    set quoted [list]
    foreach item $items {
        lappend quoted [odatix_json_string $item]
    }
    return "\[[join $quoted ", "]\]"
}

proc odatix_librelane_sources {signature} {
    # The HDL sources of the design, as {verilog_files vhdl_files include_dirs}.
    # A filelist ("filelist.f" at the root of the RTL directory) gives them in
    # order; otherwise every source file under the RTL directory is taken.
    global rtl_path
    set root [file normalize $rtl_path]

    if {[file exists "$root/filelist.f"]} {
        puts "$signature <cyan>Using filelist: $root/filelist.f<end>"
        set files [read_filelist "$root/filelist.f"]
    } else {
        set files [get_files_recursive $root {*.v *.sv *.vhd *.vhdl}]
    }

    set verilog [list]
    set vhdl [list]
    foreach file $files {
        switch -glob -- $file {
            *.v - *.sv { lappend verilog [file normalize $file] }
            *.vhd - *.vhdl { lappend vhdl [file normalize $file] }
        }
    }

    # Every directory holding a source or a header, for `include
    set include_dirs [list $root]
    foreach file [get_files_recursive $root {*.v *.sv *.vh *.svh}] {
        set dir [file normalize [file dirname $file]]
        if {[lsearch -exact $include_dirs $dir] < 0} {
            lappend include_dirs $dir
        }
    }
    return [list $verilog $vhdl $include_dirs]
}

proc odatix_librelane_write_config {signature} {
    # Write the LibreLane configuration of the design (config.json). What
    # changes from one run to the next (the clock period, the strategy of the
    # flow) is not in it: it is given on the command line of each run (see
    # odatix_librelane_overrides), so this file is written once per job.
    global librelane_config_file top_level_module clock_signal
    global librelane_flow

    lassign [odatix_librelane_sources $signature] verilog vhdl include_dirs

    if {[llength $verilog] == 0 && [llength $vhdl] == 0} {
        puts "$signature <bold><red>error: no Verilog, SystemVerilog or VHDL source found in the RTL directory<end>"
        exit -1
    }
    if {[llength $verilog] != 0 && [llength $vhdl] != 0} {
        puts "$signature <bold><red>error: LibreLane cannot synthesize mixed Verilog and VHDL designs<end>"
        exit -1
    }

    set flow [odatix_flow_param flow ""]
    set entries [list]
    if {[llength $vhdl] != 0} {
        if {$flow eq ""} { set flow VHDLClassic }
        puts "$signature <cyan>VHDL files:<end>"
        foreach file $vhdl { puts "  <cyan>- $file<end>" }
        lappend entries "\"VHDL_FILES\": [odatix_json_list $vhdl]"
    } else {
        if {$flow eq ""} { set flow Classic }
        puts "$signature <cyan>Verilog/SystemVerilog files:<end>"
        foreach file $verilog { puts "  <cyan>- $file<end>" }
        lappend entries "\"VERILOG_FILES\": [odatix_json_list $verilog]"
        lappend entries "\"VERILOG_INCLUDE_DIRS\": [odatix_json_list $include_dirs]"
    }
    set librelane_flow $flow

    lappend entries "\"DESIGN_NAME\": [odatix_json_string $top_level_module]"
    lappend entries "\"CLOCK_PORT\": [odatix_json_string $clock_signal]"
    lappend entries "\"CLOCK_PERIOD\": [odatix_librelane_period]"

    set f [open $librelane_config_file w]
    puts $f "\{"
    puts $f "  \"meta\": \{\"version\": 2, \"flow\": [odatix_json_string $flow]\},"
    puts $f "  [join $entries ",\n  "]"
    puts $f "\}"
    close $f
    puts "$signature wrote <cyan>$librelane_config_file<end> ($flow flow)"
}

proc odatix_librelane_period {} {
    # The clock period of the current run, in ns, as update_freq.tcl wrote it
    global constraints_file
    set f [open $constraints_file r]
    set content [read $f]
    close $f
    if {[regexp {"CLOCK_PERIOD"\s*:\s*([0-9.eE+-]+)} $content -> period]} {
        return $period
    }
    error "no CLOCK_PERIOD in $constraints_file"
}

proc odatix_librelane_overrides {} {
    # "-c NAME=value" for the clock period and every LibreLane variable the
    # flow of the job sets (the parameters named in capitals)
    set overrides [list -c "CLOCK_PERIOD=[odatix_librelane_period]"]
    if {[info exists ::odatix_flow_parameters]} {
        dict for {name value} $::odatix_flow_parameters {
            if {![regexp {^[A-Z][A-Z0-9_]*$} $name]} { continue }
            if {$value eq ""} { continue }
            lappend overrides -c "$name=$value"
        }
    }
    return $overrides
}

######################################
# Running LibreLane
######################################

proc odatix_librelane_run {signature tag from to args} {
    # Run the Classic flow from step id `from` to step id `to` ("" for either
    # end) in the run directory runs/<tag>. Other options go in `args`, such as
    # "--overwrite" or "-i <state>". Returns 1 if LibreLane succeeded.
    global librelane_config_file librelane_pdk librelane_scl librelane_pdk_root
    global single_thread

    set command [list librelane --hide-progress-bar --run-tag $tag]
    lappend command --pdk $librelane_pdk
    if {$librelane_scl ne ""}      { lappend command --scl $librelane_scl }
    if {$librelane_pdk_root ne ""} { lappend command --pdk-root $librelane_pdk_root }
    if {$single_thread}            { lappend command -j 1 }
    if {$from ne ""}               { lappend command --from $from }
    if {$to ne ""}                 { lappend command --to $to }
    foreach option [odatix_librelane_overrides] { lappend command $option }
    foreach option [odatix_flow_param extra_args [list]] { lappend command $option }
    foreach option $args { lappend command $option }
    lappend command $librelane_config_file

    puts "$signature <bold>> [join $command " "]<end>"
    flush stdout

    # The errors LibreLane logs, for the caller to report: an "ERROR" line and
    # the lines continuing it (indented, without a time stamp)
    set ::odatix_librelane_errors [list]
    set in_error 0

    set chan [open "|$command 2>@1" r]
    while {[gets $chan line] >= 0} {
        # Steps a run does not go up to: one line each, for the whole flow
        if {[string match "*INFO     Skipping step *" $line]} {
            continue
        }
        puts $line
        flush stdout
        if {[regexp {^\[[0-9:]+\] ERROR\s+(.*?)\s+\S+\.py:[0-9]+\s*$} $line -> message]} {
            lappend ::odatix_librelane_errors [string trim $message]
            set in_error 1
        } elseif {$in_error && [regexp {^\s{10,}(\S.*?)\s*$} $line -> more]} {
            set last [expr {[llength $::odatix_librelane_errors] - 1}]
            lset ::odatix_librelane_errors $last "[lindex $::odatix_librelane_errors $last] $more"
        } else {
            set in_error 0
        }
    }
    if {[catch {close $chan} errmsg]} {
        puts "$signature <bold><red>LibreLane failed<end>"
        return 0
    }
    return 1
}

proc odatix_librelane_collect {signature tag report_dir {state_copy ""}} {
    # Write the metrics of the last step that completed in runs/<tag> to
    # report_dir (see librelane_state.py)
    global librelane_runs_path librelane_state_script
    set command [list python3 $librelane_state_script collect $librelane_runs_path/$tag $report_dir]
    if {$state_copy ne ""} { lappend command $state_copy }
    if {[catch {exec {*}$command 2>@1} output]} {
        puts "$signature <bold><red>error: could not read the results of LibreLane<end>"
        puts "$signature tool says -> $output"
        return 0
    }
    return 1
}

proc odatix_librelane_view {state format} {
    # The path of a view of a LibreLane state ("nl" for the netlist), or ""
    global librelane_state_script
    if {[catch {exec python3 $librelane_state_script view $state $format} output]} {
        return ""
    }
    return [string trim $output]
}

proc odatix_librelane_publish_handoff {signature state} {
    # Publish the netlist of a state for "odatix pnr", with the constraints of
    # the job: the clock of the current period
    global result_path clock_signal top_level_module
    set netlist [odatix_librelane_view $state nl]
    file mkdir $result_path
    set sdc $result_path/${top_level_module}.sdc
    set f [open $sdc w]
    puts $f "create_clock -name $clock_signal -period [odatix_librelane_period] \[get_ports $clock_signal\]"
    close $f
    odatix_publish_handoff $netlist $sdc "" $signature
}
