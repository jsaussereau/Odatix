#################################################################################
# GENUS SYNTHESIS SCRIPT
#################################################################################
#
# One synthesis at the frequency currently written in the constraints file.
#
# A custom frequency synthesis runs it once, after analyze_script.tcl. An fmax
# search runs it at every iteration of its binary search, in the same Genus
# process: find_fmax.tcl has read and elaborated the RTL once, before the first
# iteration. That first iteration saves the elaborated design, and the next ones
# read it back before synthesizing: each one must start again from the RTL, not
# from the netlist the previous one mapped. Synthesizing on top of it gives
# frequencies the design would not reach, or miss, when synthesized on its own.
#
# An iteration of an fmax search exports its netlist for "odatix pnr" only when
# it meets timing. The search only ever raises its lower bound on such an
# iteration, so the netlist left behind when it ends is the one synthesized at
# the frequency it reports.

source scripts/settings.tcl
source scripts/is_slack_met.tcl
source scripts/synth_common.tcl
report_progress 28 $synth_statusfile

#################################################################################
# ELABORATED DESIGN
#################################################################################

set elaborated_db ${top_level_module}_elaborated.db

if {![info exists ::odatix_genus_elaborated]} {
    write_db $elaborated_db
    set ::odatix_genus_elaborated 1
} else {
    # Also drops the constraints of the previous iteration
    read_db $elaborated_db
}

#################################################################################
# CONSTRAINTS
#################################################################################

read_sdc $constraints_file
report_clocks
report_timing -lint
check_timing_intent

report_progress 40 $synth_statusfile


#################################################################################
# SYNTHESIS
#################################################################################

# The strategy of the flow (see odatix_genus_synthesize in synth_common.tcl)
odatix_genus_synthesize "<grey>\[synth_script.tcl\]<end>"

#################################################################################
# REPORTS
#################################################################################


report_timing > $timing_rep
report_area > $area_rep
report_power -unit mw > $power_rep
report_qor > $report_path/qor.rep
report_area -detail > $utilization_rep


report_timing 
report_area 
report_power -unit mw

report_progress 95 $synth_statusfile


#################################################################################
# NETLIST
#################################################################################

# ::cur_freq is the frequency an fmax search is trying
if {![info exists ::cur_freq] || [is_slack_met $report_path $timing_rep]} {
    write_hdl > $result_path/${top_level_module}_netlist.v
    write_sdf > $result_path/${top_level_module}.sdf
    write_sdc > $result_path/${top_level_module}.sdc

    # Publish them under the names "odatix pnr" looks for, so this synthesis can be
    # placed & routed by Innovus, ICC2 or any other tool declaring a pnr flow.
    odatix_publish_handoff \
        $result_path/${top_level_module}_netlist.v \
        $result_path/${top_level_module}.sdc \
        $result_path/${top_level_module}.sdf \
        "<grey>\[synth_script.tcl\]<end>"
}


report_progress 100 $synth_statusfile
puts "Synthesis completed successfully!"
