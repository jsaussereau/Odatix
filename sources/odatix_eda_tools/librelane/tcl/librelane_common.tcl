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
    # The HDL sources of the design, as {verilog_files vhdl_files include_dirs
    # defines}. A file list ("filelist" in the settings of the design, or
    # "filelist.f" at the root of the RTL directory) gives them in order, with
    # include directories and macros; otherwise every source file under the RTL
    # directory is taken.
    global rtl_path
    set root [file normalize $rtl_path]

    set design_sources [odatix_design_sources $signature]
    if {[dict get $design_sources filelist] ne ""} {
        puts "$signature <cyan>Using filelist: [dict get $design_sources filelist]<end>"
        set files [dict get $design_sources files]
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

    # The include directories of the file list, then every directory holding
    # a source or a header, for `include
    set include_dirs [concat [dict get $design_sources incdirs] [list $root]]
    foreach file [get_files_recursive $root {*.v *.sv *.vh *.svh}] {
        set dir [file normalize [file dirname $file]]
        if {[lsearch -exact $include_dirs $dir] < 0} {
            lappend include_dirs $dir
        }
    }
    return [list $verilog $vhdl $include_dirs [dict get $design_sources defines]]
}

proc odatix_librelane_write_config {signature} {
    # Write the LibreLane configuration of the design (config.json). What
    # changes from one run to the next (the clock period, the strategy of the
    # flow) is not in it: it is given on the command line of each run (see
    # odatix_librelane_overrides), so this file is written once per job.
    global librelane_config_file top_level_module clock_signal
    global librelane_flow

    lassign [odatix_librelane_sources $signature] verilog vhdl include_dirs defines

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
        if {[llength $defines]} {
            lappend entries "\"VERILOG_DEFINES\": [odatix_json_list $defines]"
        }
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

    odatix_librelane_merge_user_config $signature
}

proc odatix_librelane_user_config_files {} {
    # The constraint files of the job LibreLane reads as configuration: JSON or
    # YAML files of LibreLane variables, such as DIE_AREA. One LibreLane run
    # goes from synthesis to signoff, so it reads the files of both stages.
    global user_constraints_synthesis user_constraints_pnr
    set files [list]
    foreach file [concat $user_constraints_synthesis $user_constraints_pnr] {
        if {[lsearch -exact $files $file] < 0} { lappend files $file }
    }
    return $files
}

proc odatix_librelane_merge_user_config {signature} {
    # Add the variables of the design's constraint files (see
    # odatix_librelane_user_config_files) to config.json: what depends on the
    # design, like the size of its die, as opposed to the strategy of the flow.
    # The flow still has the last word, as its overrides come on the command
    # line. Files of any other kind mean nothing to LibreLane: they are left out.
    global librelane_config_file librelane_state_script
    set configs [list]
    foreach file [odatix_librelane_user_config_files] {
        if {[regexp -nocase {\.(json|ya?ml)$} $file]} {
            lappend configs $file
        } else {
            puts "$signature <yellow>warning: constraint file '[file tail $file]' ignored: LibreLane reads its variables from .json or .yaml files<end>"
        }
    }
    if {[llength $configs] == 0} {
        return
    }
    if {[catch {exec python3 $librelane_state_script merge-config $librelane_config_file {*}$configs 2>@1} output]} {
        puts "$signature <bold><red>error: could not add the constraint files to the LibreLane configuration<end>"
        puts "$signature tool says -> $output"
        exit -1
    }
    foreach file $configs {
        puts "$signature added the variables of <cyan>[file tail $file]<end> to the configuration"
    }
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

proc odatix_librelane_die_area {} {
    # The die the flow asks for, as the LibreLane variables setting it: none
    # when "die_width" and "die_height" are empty, LibreLane then sizing the die
    # itself from the core utilization and the aspect ratio (FP_CORE_UTIL,
    # FP_ASPECT_RATIO); a die of that size, in microns, otherwise.
    set width  [string trim [odatix_flow_param die_width ""]]
    set height [string trim [odatix_flow_param die_height ""]]
    if {$width eq "" && $height eq ""} {
        return [list]
    }
    if {$width eq "" || $height eq ""} {
        error "die_width and die_height go together: set both to fix the size of the die, or neither to let LibreLane size it"
    }
    foreach {name value} [list die_width $width die_height $height] {
        if {![string is double -strict $value] || $value <= 0} {
            error "$name must be a positive number of microns, not \"$value\""
        }
    }
    return [list FP_SIZING absolute DIE_AREA "0 0 $width $height"]
}

proc odatix_librelane_overrides {} {
    # "-c NAME=value" for the clock period, the size of the die and every
    # LibreLane variable the flow of the job sets (the parameters named in
    # capitals)
    set overrides [list -c "CLOCK_PERIOD=[odatix_librelane_period]"]
    foreach {name value} [odatix_librelane_die_area] {
        lappend overrides -c "$name=$value"
    }
    if {[info exists ::odatix_flow_parameters]} {
        dict for {name value} $::odatix_flow_parameters {
            if {![regexp {^[A-Z][A-Z0-9_]*$} $name]} { continue }
            if {$value eq ""} { continue }
            lappend overrides -c "$name=$value"
        }
    }
    # A die enlarged for the IO pins of the design (see odatix_librelane_run)
    # holds for the following runs of the job too, as the next iterations of an
    # fmax search: it comes last, over FP_SIZING set by the flow
    if {[info exists ::odatix_librelane_io_die]} {
        lassign $::odatix_librelane_io_die width height
        lappend overrides -c "FP_SIZING=absolute" -c "DIE_AREA=0 0 $width $height"
    }
    return $overrides
}

######################################
# Die fitted to the IO pins
######################################
# LibreLane sizes the die from the area of the cells. A design with many IO
# pins for few cells (a wide datapath, a fully parallel decoder) then gets a
# die whose perimeter cannot hold its pins, and the IO placement fails
# (PPL-0024), saying which perimeter would. Unless the size of the die is fixed,
# odatix_librelane_run then runs the flow again on a die of that perimeter, plus
# a margin ("die_fit_io" and "die_fit_io_margin" of the flow).

proc odatix_librelane_io_perimeter {} {
    # The die perimeter, in microns, the IO placement of the last run asked
    # for, or "" when it did not fail for lack of room for the pins
    if {![info exists ::odatix_librelane_errors]} {
        return ""
    }
    if {[regexp {PPL-0024.*?Increase the die perimeter from [0-9.]+\s*um to ([0-9.]+)\s*um} \
            [join $::odatix_librelane_errors " "] -> perimeter]} {
        return $perimeter
    }
    return ""
}

proc odatix_librelane_die_is_fixed {} {
    # 1 when the size of the die is not LibreLane's to choose: "die_width" and
    # "die_height" of the flow, FP_SIZING set to absolute by the flow, or by a
    # constraint file of the design (merged into config.json)
    global librelane_config_file
    if {[llength [odatix_librelane_die_area]] != 0} {
        return 1
    }
    if {[string trim [odatix_flow_param FP_SIZING ""]] eq "absolute"} {
        return 1
    }
    if {[info exists librelane_config_file] && [file exists $librelane_config_file]} {
        set f [open $librelane_config_file r]
        set content [read $f]
        close $f
        if {[regexp {"FP_SIZING"\s*:\s*"absolute"} $content]} {
            return 1
        }
    }
    return 0
}

proc odatix_librelane_die_fit_io_enabled {} {
    # "die_fit_io" of the flow: on unless set to false
    set value [string trim [odatix_flow_param die_fit_io ""]]
    if {$value eq ""} {
        return 1
    }
    if {![string is boolean -strict $value]} {
        error "die_fit_io must be true or false, not \"$value\""
    }
    return [string is true $value]
}

proc odatix_librelane_io_die {perimeter attempt} {
    # Width and height, in whole microns, of a die whose perimeter is the one
    # the IO placement asked for plus "die_fit_io_margin" percent per attempt,
    # with the aspect ratio of the flow (FP_ASPECT_RATIO, height / width;
    # square when unset)
    set margin [string trim [odatix_flow_param die_fit_io_margin ""]]
    if {$margin eq ""} {
        set margin 10
    }
    if {![string is double -strict $margin] || $margin < 0} {
        error "die_fit_io_margin must be a percentage, not \"$margin\""
    }
    set ratio [string trim [odatix_flow_param FP_ASPECT_RATIO ""]]
    if {$ratio eq ""} {
        set ratio 1
    }
    if {![string is double -strict $ratio] || $ratio <= 0} {
        error "FP_ASPECT_RATIO must be a positive number, not \"$ratio\""
    }
    set target [expr {$perimeter * (1.0 + $margin / 100.0 * $attempt)}]
    set width  [expr {int(ceil($target / (2.0 * (1.0 + $ratio))))}]
    set height [expr {int(ceil($width * $ratio))}]
    return [list $width $height]
}

######################################
# Running LibreLane
######################################

proc odatix_librelane_run {signature tag from to args} {
    # Run the Classic flow from step id `from` to step id `to` ("" for either
    # end) in the run directory runs/<tag>. Other options go in `args`, such as
    # "--overwrite" or "-i <state>". Returns 1 if LibreLane succeeded.
    #
    # A run whose IO placement fails for lack of room for the pins runs again
    # on a die of the perimeter it asked for, unless the size of the die is
    # fixed or "die_fit_io" is false (see "Die fitted to the IO pins")
    set ok [odatix_librelane_run_once $signature $tag $from $to {*}$args]

    set max_attempts 3
    set attempt 0
    while {!$ok} {
        set perimeter [odatix_librelane_io_perimeter]
        if {$perimeter eq ""} {
            break
        }
        if {[odatix_librelane_die_is_fixed]} {
            puts "$signature <bold><red>error: the die is too small for the IO pins of the design: the IO placement asks for a perimeter of ${perimeter}um. Enlarge the die, or leave its size to LibreLane for Odatix to fit it to the pins<end>"
            break
        }
        if {![odatix_librelane_die_fit_io_enabled]} {
            puts "$signature <bold><red>error: the die is too small for the IO pins of the design: the IO placement asks for a perimeter of ${perimeter}um. Set \"die_fit_io\" to let Odatix enlarge the die<end>"
            break
        }
        if {$attempt >= $max_attempts} {
            puts "$signature <bold><red>error: the IO pins still do not fit after $max_attempts larger dies<end>"
            break
        }
        incr attempt
        lassign [odatix_librelane_io_die $perimeter $attempt] width height
        set ::odatix_librelane_io_die [list $width $height]
        puts "$signature <bold><yellow>the IO pins do not fit on the perimeter of the die: the IO placement asks for ${perimeter}um, running again on a ${width}x${height}um die (attempt $attempt of $max_attempts)<end>"
        set ok [odatix_librelane_run_once $signature $tag $from $to {*}$args]
    }
    return $ok
}

proc odatix_librelane_run_once {signature tag from to args} {
    # One LibreLane run (see odatix_librelane_run). Leaves the errors LibreLane
    # logged in ::odatix_librelane_errors.
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
