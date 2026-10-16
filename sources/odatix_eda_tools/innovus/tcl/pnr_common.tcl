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

# Helpers shared by the steps of the Innovus place & route flow.
#
# Steps run as separate Innovus processes, so each one saves the design when it
# is done and the next one restores it. That is the only state handed over
# inside a run; what comes *into* the run is the synthesis netlist, reached
# through $source_netlist / $source_sdc (see the _common settings.tcl).

proc odatix_apply_flow_modes {signature} {
    # The strategy of the flow this job runs with (see "parameters" in
    # tool.yml). Each step applies it again after restoring the design, so a
    # step does not depend on what the database kept of the previous one.
    setDesignMode -flowEffort [odatix_flow_param flow_effort standard] \
                  -powerEffort [odatix_flow_param power_effort none]
    foreach {command parameter} {setDesignMode design_options setPlaceMode place_options setOptMode opt_options setNanoRouteMode route_options} {
        set options [odatix_flow_param $parameter [list]]
        if {[llength $options] > 0} {
            $command {*}$options
        }
    }
    puts "$signature flow effort <cyan>[odatix_flow_param flow_effort standard]<end>, power effort <cyan>[odatix_flow_param power_effort none]<end>"
}

proc odatix_design_path {name} {
    global result_path
    return [file join $result_path $name]
}

proc odatix_save {name signature} {
    file mkdir [file dirname [odatix_design_path $name]]
    saveDesign [odatix_design_path $name]
    puts "$signature saved design <cyan>$name<end>"
}

proc odatix_restore {name signature} {
    global top_level_module
    set path [odatix_design_path $name]
    if {![file exists ${path}.dat] && ![file exists $path]} {
        puts "$signature <bold><red>error: missing design $name from the previous step<end>"
        exit -1
    }
    restoreDesign ${path}.dat $top_level_module
    puts "$signature restored design <cyan>$name<end>"
}

proc odatix_box_area {box} {
    lassign $box x1 y1 x2 y2
    return [expr {($x2 - $x1) * ($y2 - $y1)}]
}

proc odatix_report_floorplan {file} {
    # Die and core areas and the core utilization: what the floorplan of the
    # flow (utilization, aspect ratio, margin) sets, and report_area does not say.
    set die_area  [odatix_box_area [lindex [dbGet top.fPlan.box] 0]]
    set core_area [odatix_box_area [lindex [dbGet top.fPlan.coreBox] 0]]
    set cell_area 0.0
    foreach area [dbGet -e top.insts.area] {
        set cell_area [expr {$cell_area + $area}]
    }
    set fp [open $file w]
    puts $fp [format "Die area: %.2f" $die_area]
    puts $fp [format "Core area: %.2f" $core_area]
    puts $fp [format "Cell area: %.2f" $cell_area]
    if {$core_area > 0} {
        puts $fp [format "Core utilization: %.4f" [expr {$cell_area / $core_area}]]
    }
    close $fp
}

proc odatix_write_reports {stage signature} {
    global report_path
    file mkdir [file join $report_path $stage]
    report_area   > [file join $report_path $stage area.rep]
    report_power  > [file join $report_path $stage power.rep]
    report_timing > [file join $report_path $stage timing.rep]
    odatix_report_floorplan [file join $report_path $stage floorplan.rep]

    # The metrics.yml of this tool reads the flat copies, so the last stage to
    # run is the one the results describe.
    report_area   > [file join $report_path area.rep]
    report_power  > [file join $report_path power.rep]
    report_timing > [file join $report_path timing.rep]
    odatix_report_floorplan [file join $report_path floorplan.rep]
    puts "$signature wrote the <cyan>$stage<end> reports"
}
