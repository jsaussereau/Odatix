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

# Step "init" of the Innovus place & route flow.

if {[catch {

    set signature "<grey>\[step_init.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/pnr_common.tcl

    # Read the netlist the synthesis handed over, together with its constraints.
    odatix_require_source $signature

    # Technology setup. This is what you have to adapt to your PDK: the target
    # file of this tool copies your technology script into the job directory
    # (script_copy_enable / script_copy_source), and it is sourced here.
    if {[file exists $script_path/technology_setup.tcl]} {
        source $script_path/technology_setup.tcl
    } else {
        puts "$signature <bold><red>error: no technology_setup.tcl in this job<end>"
        puts "$signature <cyan>note: point script_copy_source at your Innovus technology script in the target file<end>"
        exit -1
    }

    set init_verilog $source_netlist
    set init_design_netlisttype "Verilog"
    set init_top_cell $top_level_module
    init_design

    # A technology script with an MMMC setup reads the synthesis constraints
    # through its constraint mode; without one, they are read here.
    if {![info exists init_mmmc_file] || $init_mmmc_file eq ""} {
        read_sdc $source_sdc
    }

    # Floorplan. Replace with the one your design needs. The technology script
    # names the site of its core rows ($odatix_core_site); without it, Innovus
    # takes the default core site of the LEF.
    if {[info exists odatix_core_site] && $odatix_core_site ne ""} {
        floorPlan -site $odatix_core_site -r 1.0 0.7 10 10 10 10
    } else {
        floorPlan -r 1.0 0.7 10 10 10 10
    }

    # Power: connect the cell supply pins to the power nets the technology
    # script declares ($init_pwr_net, $init_gnd_net), then a ring around the
    # core and the follow-pin rails.
    if {[info exists init_pwr_net] && [info exists init_gnd_net]} {
        globalNetConnect $init_pwr_net -type pgpin -pin $init_pwr_net -all
        globalNetConnect $init_gnd_net -type pgpin -pin $init_gnd_net -all
        globalNetConnect $init_pwr_net -type tiehi
        globalNetConnect $init_gnd_net -type tielo
        # Horizontal then vertical layer of the core ring ($odatix_ring_layers,
        # set by the technology script); no ring without it.
        if {[info exists odatix_ring_layers] && [llength $odatix_ring_layers] == 2} {
            set ring_layers $odatix_ring_layers
            addRing -nets [list $init_pwr_net $init_gnd_net] -type core_rings -follow core \
                -layer [list top [lindex $ring_layers 0] bottom [lindex $ring_layers 0] left [lindex $ring_layers 1] right [lindex $ring_layers 1]] \
                -width 2 -spacing 1 -offset 1
        }
        sroute -connect {corePin} -nets [list $init_pwr_net $init_gnd_net]
    }

    odatix_write_reports "init" $signature
    odatix_save post_init $signature
    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    exit -1
}
