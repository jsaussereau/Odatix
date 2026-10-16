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

# The synthesis strategy of a Genus job, as its flow says (its "parameters" in
# tool.yml).

source scripts/settings.tcl

# Set a root attribute, or say why it could not be: a version that does not know
# it still synthesizes, without it.
proc odatix_genus_set {attribute value signature} {
    if {[catch {set_db $attribute $value} errmsg]} {
        puts "$signature <bold><yellow>warning: could not set $attribute to $value, going on without it<end>"
        puts "$signature tool says -> $errmsg"
        return 0
    }
    puts "$signature <cyan>$attribute = $value<end>"
    return 1
}

# The attributes the strategy sets before the design is synthesized:
#
#   effort                 syn_global_effort: low, medium or high
#   generic_effort         efforts of syn_generic, syn_map and syn_opt ("" for
#   map_effort             the one syn_global_effort gives). syn_opt also takes
#   opt_effort             "extreme"
#   auto_ungroup           none, area, timing or both ("" for the default, both)
#   area_mode              datapath optimizations that favor area (dp_area_mode)
#   tns_opto               optimize every violating endpoint, not only the worst
#                          ("" for the default, true)
#   ultra_optimization     iopt_ultra_optimization, for the incremental pass
#   retime                 retiming of the design registers
#   clock_gating           clock gating insertion, from discrete cells when the
#                          library has no integrated clock gating cell
#   power_effort           design_power_effort: none, low or high
#   leakage_power_effort   none, low, medium, high or auto ("" for the default)
#   attributes             other root attributes, as "name value" items
#
# They are set again at each iteration of an fmax search: reading the elaborated
# design back resets the design attributes (retime), and setting the rest again
# costs nothing.
proc odatix_genus_strategy {signature} {
    global top_level_module

    odatix_genus_set syn_global_effort [odatix_flow_param effort high] $signature
    foreach command {generic map opt} {
        set effort [odatix_flow_param ${command}_effort ""]
        if {$effort ne ""} {
            odatix_genus_set syn_${command}_effort $effort $signature
        }
    }

    foreach {parameter attribute} {
        auto_ungroup         auto_ungroup
        tns_opto             tns_opto
        leakage_power_effort leakage_power_effort
    } {
        set value [odatix_flow_param $parameter ""]
        if {$value ne ""} {
            odatix_genus_set $attribute $value $signature
        }
    }
    odatix_genus_set dp_area_mode [expr {[odatix_flow_param area_mode 0] ? "true" : "false"}] $signature
    odatix_genus_set iopt_ultra_optimization [expr {[odatix_flow_param ultra_optimization 0] ? "true" : "false"}] $signature
    odatix_genus_set design_power_effort [odatix_flow_param power_effort none] $signature

    if {[odatix_flow_param clock_gating 0]} {
        odatix_genus_set lp_insert_clock_gating true $signature
        # Older libraries (AMS C35...) have no integrated clock gating cell
        odatix_genus_set lp_insert_discrete_clock_gating_logic true $signature
    } else {
        odatix_genus_set lp_insert_clock_gating false $signature
    }

    if {[odatix_flow_param retime 0]} {
        if {[catch {set_db [get_db designs $top_level_module] .retime true} errmsg]} {
            puts "$signature <bold><yellow>warning: could not enable retiming, going on without it<end>"
            puts "$signature tool says -> $errmsg"
        } else {
            puts "$signature <cyan>retime = true<end>"
        }
    }

    foreach item [odatix_flow_param attributes [list]] {
        if {[llength $item] != 2} {
            puts "$signature <bold><yellow>warning: '$item' is not an attribute and its value, skipping it<end>"
            continue
        }
        odatix_genus_set [lindex $item 0] [lindex $item 1] $signature
    }
}

# The synthesis itself, run the way the flow says:
#
#   incremental            a second, incremental syn_opt on the optimized design
#   post_opt_passes        commands run on the optimized design afterwards
#
# Without parameters, this is the historical Odatix synthesis: syn_generic,
# syn_map and syn_opt at high global effort.
proc odatix_genus_synthesize {signature} {
    global synth_statusfile continue_on_error

    odatix_genus_strategy $signature

    foreach {command progress} {syn_generic 50 syn_map 70 syn_opt 85} {
        puts "$signature <cyan>running $command<end>"
        if {[catch {$command} errmsg]} {
            puts "$signature <bold><red>error: $command failed<end>"
            puts "$signature tool says -> $errmsg"
            if {$continue_on_error == 1} {
                return -code continue "continue"
            } else {
                exit -1
            }
        }
        report_progress $progress $synth_statusfile
    }

    if {[odatix_flow_param incremental 0]} {
        puts "$signature <cyan>incremental pass: syn_opt -incremental<end>"
        if {[catch {syn_opt -incremental} errmsg]} {
            puts "$signature <bold><yellow>warning: incremental pass failed, keeping the first one<end>"
            puts "$signature tool says -> $errmsg"
        }
    }

    # Commands run on the optimized design, in order. One the installed version
    # does not know is skipped: the design is valid without it.
    foreach pass [odatix_flow_param post_opt_passes [list]] {
        puts "$signature <cyan>post-optimization pass: $pass<end>"
        if {[catch {uplevel #0 $pass} errmsg]} {
            puts "$signature <bold><yellow>warning: '$pass' failed, skipping it<end>"
            puts "$signature tool says -> $errmsg"
        }
    }
    report_progress 90 $synth_statusfile
}
