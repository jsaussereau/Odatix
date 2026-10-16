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

# Helpers shared by the Quartus scripts.
#
# Quartus is not one process holding the design in memory, as Vivado is: each
# stage of the compilation is an executable of its own (quartus_syn,
# quartus_fit, quartus_sta, quartus_pow, quartus_asm), and the design goes from
# one to the next through the project database, on disk. The scripts run in
# quartus_sh, which creates the project and runs these executables on it
# (execute_module). A step that stops a run therefore leaves nothing to save: the
# next one, in a later process, opens the project and finds the design where the
# previous step left it.
#
# The project lives in the "work" directory of the job, under the name below.
# Every path handed to Quartus is absolute, since its executables run from the
# project directory.

source scripts/settings.tcl

load_package flow

set ::odatix_quartus_project odatix

proc odatix_quartus_project_dir {} {
    global work_path
    return [file normalize $work_path]
}

proc odatix_quartus_project_file {suffix} {
    return [file join [odatix_quartus_project_dir] "$::odatix_quartus_project.$suffix"]
}

proc odatix_quartus_target {} {
    global target_file
    set f [open $target_file]
    set target [string trim [gets $f]]
    close $f
    return $target
}

######################################
# Project
######################################

# Open the project of this job, creating it when "create" is set. The working
# directory is the project directory until odatix_quartus_close.
proc odatix_quartus_open {signature {create 0}} {
    set dir [odatix_quartus_project_dir]
    file mkdir $dir
    set ::odatix_quartus_caller_dir [pwd]
    cd $dir
    set name $::odatix_quartus_project
    if {[catch {
        if {$create} {
            project_new $name -revision $name -overwrite
        } else {
            if {![project_exists $name]} {
                error "no project in $dir"
            }
            project_open $name -revision $name
        }
    } errmsg]} {
        cd $::odatix_quartus_caller_dir
        puts "$signature <bold><red>error: failed opening the Quartus project<end>"
        puts "$signature tool says -> $errmsg"
        exit -1
    }
}

proc odatix_quartus_close {} {
    catch {export_assignments}
    catch {project_close}
    if {[info exists ::odatix_quartus_caller_dir]} {
        cd $::odatix_quartus_caller_dir
    }
}

# Constraint files of the user are added to the project rather than read: the
# executables that need them (synthesis, fitter, timing analysis) read the
# project. An sdc file is a timing constraint; a tcl or qsf file holds
# assignments (a pinout, an I/O standard, a location), sourced into the project.
proc odatix_quartus_add_constraint {constraint_file} {
    set constraint_file [file normalize $constraint_file]
    switch -- [string tolower [file extension $constraint_file]] {
        .sdc {
            set_global_assignment -name SDC_FILE $constraint_file
        }
        .tcl - .qsf {
            uplevel #0 [list source $constraint_file]
        }
        default {
            error "unknown kind of constraint file (expected .sdc, .tcl or .qsf)"
        }
    }
}

# Create the project of the job: device, sources, constraints and the strategy
# of the flow. Created from scratch each time, which is what an fmax search
# needs: every iteration starts from the same project, the timing constraint
# being the only thing that changed.
proc odatix_quartus_create_project {signature {any_device 0}} {
    global top_level_module constraints_file single_thread

    set target [odatix_quartus_target]

    # Checked against the installed parts: get_part_info only prints an error on
    # a part it does not know, and returns.
    load_package device
    if {[lsearch -exact [get_part_list] $target] < 0} {
        if {!$any_device} {
            puts "$signature <bold><red>error: unknown device \"$target\"<end>"
            puts "$signature <cyan>note: is its device family installed? (\"targets\" in target_quartus.yml)<end>"
            exit -1
        }
        # An RTL analysis has no target, and Quartus elaborates nothing without
        # a device: any installed one does, elaboration does not depend on it.
        set target [lindex [get_part_list -family [lindex [get_family_list] 0]] 0]
        puts "$signature <cyan>no target device: analyzing for $target<end>"
    }

    odatix_quartus_open $signature 1

    # get_part_info gives a list, of one family
    set_global_assignment -name FAMILY [lindex [get_part_info -family $target] 0]
    set_global_assignment -name DEVICE $target
    set_global_assignment -name TOP_LEVEL_ENTITY $top_level_module
    set_global_assignment -name VERILOG_MACRO "QUARTUS=1"

    foreach {source_file kind} $::odatix_quartus_sources {
        set_global_assignment -name $kind $source_file
    }
    foreach dir $::odatix_quartus_search_path {
        set_global_assignment -name SEARCH_PATH $dir
    }

    set_global_assignment -name SDC_FILE [file normalize $constraints_file]
    odatix_read_user_constraints synthesis odatix_quartus_add_constraint $signature

    if {$single_thread == 1} {
        set_global_assignment -name NUM_PARALLEL_PROCESSORS 1
    }

    odatix_quartus_strategy $signature

    export_assignments
    puts "$signature <cyan>created project for $top_level_module on $target<end>"
}

######################################
# Strategy
######################################
# How the design is compiled is the flow's to say, through its "parameters" in
# tool.yml. Every script compiling the design goes through the procs below --
# the steps of a custom frequency synthesis as well as each iteration of an fmax
# search -- so a flow is the same strategy whatever the job:
#
#   optimization_mode             OPTIMIZATION_MODE of synthesis and fitter:
#                                 "BALANCED", "HIGH PERFORMANCE EFFORT",
#                                 "SUPERIOR PERFORMANCE", "SUPERIOR PERFORMANCE
#                                 WITH MAXIMUM PLACEMENT EFFORT", "AGGRESSIVE
#                                 AREA", "AGGRESSIVE POWER", "AGGRESSIVE COMPILE
#                                 TIME"...
#   seed                          fitter seed
#   allow_register_retiming       register retiming, in synthesis and by the
#                                 Hyper-Retimer
#   final_placement_optimization  "ALWAYS", "NEVER" or "" for Quartus' default
#   virtual_pins                  every port but the clock and the reset is a
#                                 virtual pin (see below)
#   power_analysis                quartus_pow after timing analysis
#   assignments                   other global assignments, as "NAME value"
#                                 items

proc odatix_quartus_assign {name value signature} {
    if {[catch {set_global_assignment -name $name $value} errmsg]} {
        puts "$signature <bold><yellow>warning: could not set $name to \"$value\", going on without it<end>"
        puts "$signature tool says -> $errmsg"
        return 0
    }
    puts "$signature <cyan>$name = $value<end>"
    return 1
}

proc odatix_quartus_strategy {signature} {
    global clock_signal reset_signal

    set mode [odatix_flow_param optimization_mode "HIGH PERFORMANCE EFFORT"]
    if {$mode ne ""} {
        odatix_quartus_assign OPTIMIZATION_MODE $mode $signature
    }
    set seed [odatix_flow_param seed ""]
    if {$seed ne ""} {
        odatix_quartus_assign SEED $seed $signature
    }
    set retiming [expr {[odatix_flow_param allow_register_retiming 1] ? "ON" : "OFF"}]
    odatix_quartus_assign ALLOW_REGISTER_RETIMING $retiming $signature
    set placement [odatix_flow_param final_placement_optimization ""]
    if {$placement ne ""} {
        odatix_quartus_assign FINAL_PLACEMENT_OPTIMIZATION $placement $signature
    }

    foreach item [odatix_flow_param assignments [list]] {
        set item [string trim $item]
        set name [lindex [split $item] 0]
        set value [string trim [string range $item [string length $name] end]]
        if {$name eq "" || $value eq ""} {
            puts "$signature <bold><yellow>warning: '$item' is not an assignment and its value, skipping it<end>"
            continue
        }
        odatix_quartus_assign $name $value $signature
    }

    # A design under test is not a chip: its ports are not meant to reach the
    # pins of the device, and a wide bus would not fit on them. A virtual pin is
    # kept inside the fabric instead, so the frequency is the one of the logic,
    # not of the I/Os. The clock stays a real pin, so that it is routed on the
    # clock network; the reset too. A design meant for a board -- whose bitstream
    # matters -- turns this off and gives its pinout as a "pnr" constraint file.
    if {[odatix_flow_param virtual_pins 1]} {
        set_instance_assignment -name VIRTUAL_PIN ON -to *
        foreach port [list $clock_signal $reset_signal] {
            if {$port ne ""} {
                set_instance_assignment -name VIRTUAL_PIN OFF -to $port
            }
        }
        puts "$signature <cyan>ports are virtual pins, but $clock_signal and $reset_signal<end>"
    }
}

######################################
# Compilation
######################################

# Run one executable on the open project. Returns 0 when it failed.
proc odatix_quartus_run {tool arguments signature} {
    puts "$signature <cyan>quartus_$tool $arguments<end>"
    if {[catch {
        if {$arguments eq ""} {
            execute_module -tool $tool
        } else {
            execute_module -tool $tool -args $arguments
        }
    } errmsg]} {
        puts "$signature <bold><red>error: quartus_$tool failed<end>"
        puts "$signature tool says -> $errmsg"
        puts "$signature <cyan>note: look for earlier error to solve this issue<end>"
        return 0
    }
    return 1
}

# Was the design synthesized (or fitted) successfully, as far as the project
# on disk says? What a step continuing the previous one checks first.
proc odatix_quartus_has_snapshot {module} {
    set summary [odatix_quartus_project_file "$module.summary"]
    if {![file exists $summary]} {
        return 0
    }
    set f [open $summary]
    set content [read $f]
    close $f
    return [regexp {Status\s*:\s*Successful} $content]
}

######################################
# Reports
######################################
# Metrics are exported when the run ends, whichever step it ended on, so every
# step that produces meaningful numbers writes the reports the metrics are read
# from. The standard files always hold the latest numbers; a copy is kept per
# stage so the post-synthesis estimates survive place & route.

# The rows of a table of a Quartus report, as "label value" pairs, from the
# first table whose title matches. A row is "; label ; value ; ... ;".
proc odatix_quartus_report_table {report title_pattern} {
    set rows [list]
    if {![file exists $report]} {
        return $rows
    }
    set f [open $report]
    set in_table 0
    set separators 0
    while {[gets $f line] >= 0} {
        if {!$in_table} {
            if {[string match "; *" $line] && [regexp -- $title_pattern $line]} {
                set in_table 1
                set separators 0
            }
            continue
        }
        if {[string match "+*" $line]} {
            # Header, its underline, then the end of the table
            incr separators
            if {$separators >= 3} {
                break
            }
            continue
        }
        if {$line eq ""} {
            break
        }
        set cells [split [string trim $line "; "] ";"]
        if {[llength $cells] >= 2} {
            lappend rows [string trim [lindex $cells 0]] [string trim [lindex $cells 1]]
        }
    }
    close $f
    return $rows
}

# "1,234 / 45,800" -> {1234 45800}; "17" -> {17 ""}
proc odatix_quartus_used_available {value} {
    set value [string map {"," ""} $value]
    if {[regexp {^\s*([0-9.]+)\s*/\s*([0-9.]+)} $value -> used available]} {
        return [list $used $available]
    }
    if {[regexp {^\s*([0-9.]+)} $value -> used]} {
        return [list $used ""]
    }
    return [list "" ""]
}

# Utilization, normalized from the resource usage summary of synthesis or of
# the fitter into one table, whatever the stage and the device family.
# Synthesis only estimates: it knows how many resources the design needs, not
# what the device offers, so its percentages are computed against the device.
proc odatix_quartus_write_utilization {stage signature} {
    global utilization_rep

    if {$stage eq "synthesis"} {
        set report [odatix_quartus_project_file syn.rpt]
        set rows [odatix_quartus_report_table $report {Synthesis Resource Usage Summary}]
        set title "post-synthesis estimates"
    } else {
        set report [odatix_quartus_project_file fit.rpt]
        set rows [odatix_quartus_report_table $report {Fitter Resource Usage Summary}]
        set title "post-fit"
    }
    if {[llength $rows] == 0} {
        puts "$signature <bold><red>error: no resource usage summary in [file tail $report], skipping utilization report<end>"
        return
    }

    # Resource -> patterns of the row labels giving it, first match wins
    set resources {
        ALMs        {{^Logic utilization \(ALMs needed} {^Estimate of Logic utilization \(ALMs needed\)}}
        ALUTs       {{^Combinational ALUT usage for logic$}}
        Registers   {{^-- Primary logic registers$} {^Dedicated logic registers$}}
        M20K        {{^M20K blocks$} {^Total RAM Blocks$} {^M20K}}
        MemoryBits  {{^Total block memory bits$}}
        DSPs        {{^DSP Blocks Needed} {^Total DSP Blocks$}}
        IOs         {{^I/O pins$}}
    }

    array set used {}
    array set available {}
    foreach {resource patterns} $resources {
        foreach pattern $patterns {
            foreach {label value} $rows {
                if {[regexp -- $pattern $label]} {
                    lassign [odatix_quartus_used_available $value] used($resource) available($resource)
                    break
                }
            }
            if {[info exists used($resource)] && $used($resource) ne ""} {
                break
            }
        }
    }

    # What the device offers, for the percentages synthesis cannot give
    # (two primary registers per ALM, as the fitter counts them)
    catch {
        load_package device
        set target [odatix_quartus_target]
        foreach resource {ALMs M20K} {
            if {![info exists available($resource)] || $available($resource) eq ""} {
                if {![catch {get_part_info -resource $resource $target} count] && $count > 0} {
                    set available($resource) $count
                }
            }
        }
        if {(![info exists available(Registers)] || $available(Registers) eq "") && [info exists available(ALMs)]} {
            set available(Registers) [expr {2 * $available(ALMs)}]
        }
    }

    set f [open $utilization_rep w]
    puts $f "Quartus utilization ($title)"
    puts $f ""
    puts $f "+--------------+------------+------------+---------+"
    puts $f "| Resource     |       Used |  Available |   Util% |"
    puts $f "+--------------+------------+------------+---------+"
    foreach {resource patterns} $resources {
        if {![info exists used($resource)] || $used($resource) eq ""} {
            continue
        }
        set total ""
        set percent ""
        if {[info exists available($resource)] && [string is double -strict $available($resource)] && $available($resource) > 0} {
            set total $available($resource)
            set percent [format "%.2f" [expr {100.0 * $used($resource) / $available($resource)}]]
        }
        puts $f [format "| %-12s | %10s | %10s | %7s |" $resource $used($resource) $total $percent]
    }
    puts $f "+--------------+------------+------------+---------+"
    close $f
    puts "$signature <cyan>wrote report $utilization_rep<end>"
}

# Timing, from quartus_sta: a summary of the worst slacks across every corner
# Quartus analyzes, in a format of our own, followed by the worst paths. The
# analysis runs a script of ours (sta_report.tcl) in the timing analyzer, which
# alone can query the timing netlist.
#
# "post_syn" analyzes the synthesized netlist with a rough delay model, which
# is what a search on post-synthesis timing converges on.
proc odatix_quartus_timing {stage post_syn signature} {
    global timing_rep report_path script_path constraints_file

    set sdc_files [list [file normalize $constraints_file]]
    foreach constraint_file [concat $::user_constraints_synthesis $::user_constraints_pnr] {
        if {[string tolower [file extension $constraint_file]] eq ".sdc"} {
            lappend sdc_files [file normalize $constraint_file]
        }
    }

    set wrapper [file join [odatix_quartus_project_dir] odatix_sta.tcl]
    set f [open $wrapper w]
    puts $f [list set ::odatix_sta_stage $stage]
    puts $f [list set ::odatix_sta_post_syn $post_syn]
    puts $f [list set ::odatix_sta_sdc_files $sdc_files]
    puts $f [list set ::odatix_sta_timing_rep [file normalize $timing_rep]]
    puts $f [list set ::odatix_sta_fmax_rep [file normalize [file join $report_path fmax.rep]]]
    puts $f [list source [file normalize [file join $script_path sta_report.tcl]]]
    close $f

    set arguments "--report_script=$wrapper"
    if {$post_syn} {
        set arguments "--post_syn $arguments"
    }
    return [odatix_quartus_run sta $arguments $signature]
}

# Power, from quartus_pow, with the default toggle rates: an estimate of the
# implemented design, as Vivado's report_power is.
proc odatix_quartus_power {signature} {
    global power_rep
    if {![odatix_flow_param power_analysis 1]} {
        puts "$signature <cyan>power analysis disabled by the flow<end>"
        return 1
    }
    if {![odatix_quartus_run pow "" $signature]} {
        return 0
    }
    set summary [odatix_quartus_project_file pow.summary]
    if {[file exists $summary]} {
        file copy -force $summary $power_rep
        puts "$signature <cyan>wrote report $power_rep<end>"
    }
    return 1
}

# Keep a copy of the reports under the stage they describe, along with the
# reports of Quartus itself, for the details.
proc odatix_quartus_keep_reports {stage {modules {}}} {
    global report_path utilization_rep timing_rep power_rep
    set stage_path [file join $report_path $stage]
    file mkdir $stage_path
    foreach report [list $utilization_rep $timing_rep $power_rep [file join $report_path fmax.rep]] {
        if {[file exists $report]} {
            catch {file copy -force $report $stage_path}
        }
    }
    foreach module $modules {
        foreach suffix [list "$module.rpt" "$module.summary"] {
            set report [odatix_quartus_project_file $suffix]
            if {[file exists $report]} {
                catch {file copy -force $report [file join $stage_path "quartus.$suffix"]}
            }
        }
    }
}

# Reports of a stage that is over: the ones it can give are rewritten, the ones
# it cannot are removed, so that the numbers of a previous run (power after a
# fit) are not exported as this one's.
proc odatix_quartus_clear_reports {kinds} {
    global utilization_rep timing_rep power_rep report_path
    foreach kind $kinds {
        switch -- $kind {
            utilization { file delete -force $utilization_rep }
            timing      { file delete -force $timing_rep [file join $report_path fmax.rep] }
            power       { file delete -force $power_rep }
        }
    }
}

######################################
# Stages
######################################
# One compilation, as far as "depth" says: "synthesis" stops after synthesis and
# reports on the synthesized netlist, "pnr" fits the design and reports on the
# routed one. Returns 0 when a stage failed.

proc odatix_quartus_synthesize {signature {progressfile ""} {from 0} {to 100}} {
    odatix_quartus_clear_reports {utilization timing power}
    if {![odatix_quartus_run syn "" $signature]} {
        return 0
    }
    if {$progressfile ne ""} {
        report_progress $to $progressfile
    }
    return 1
}

proc odatix_quartus_report_synthesis {signature} {
    odatix_quartus_write_utilization synthesis $signature
    if {![odatix_quartus_timing synthesis 1 $signature]} {
        return 0
    }
    odatix_quartus_keep_reports synthesis {syn}
    return 1
}

proc odatix_quartus_implement {signature {progressfile ""} {from 0} {to 100}} {
    odatix_quartus_clear_reports {utilization timing power}
    odatix_read_user_constraints pnr odatix_quartus_add_constraint $signature
    export_assignments
    if {![odatix_quartus_run fit "" $signature]} {
        return 0
    }
    if {$progressfile ne ""} {
        report_progress $to $progressfile
    }
    return 1
}

proc odatix_quartus_report_implementation {signature {progressfile ""} {from 0} {to 100}} {
    odatix_quartus_write_utilization pnr $signature
    if {![odatix_quartus_timing pnr 0 $signature]} {
        return 0
    }
    if {$progressfile ne ""} {
        report_progress [expr {($from + $to) / 2}] $progressfile
    }
    # A design whose power cannot be estimated is still implemented
    odatix_quartus_power $signature
    odatix_quartus_keep_reports pnr {fit sta pow}
    return 1
}

# The programming file, from the fitted design. Quartus refuses to write one
# for a design whose pins have no location or no I/O standard -- one given no
# pinout -- and says so only as a critical warning: the file is what tells.
# Virtual pins are not pins: with "virtual_pins", only the clock and the reset
# need one.
proc odatix_quartus_assemble {signature} {
    global result_path top_level_module
    set sof [odatix_quartus_project_file sof]
    file delete -force $sof
    if {![odatix_quartus_run asm "" $signature]} {
        return 0
    }
    if {![file exists $sof]} {
        puts "$signature <bold><red>error: Quartus wrote no programming file<end>"
        puts "$signature <cyan>note: every pin needs a location and an I/O standard (with \"virtual_pins\", the clock and the reset only): give them in a \"pnr\" constraint file (see target_quartus.yml)<end>"
        return 0
    }
    file mkdir $result_path
    set bitstream [file join $result_path "${top_level_module}.sof"]
    file copy -force $sof $bitstream
    puts "$signature <cyan>wrote programming file $bitstream<end>"
    return 1
}
