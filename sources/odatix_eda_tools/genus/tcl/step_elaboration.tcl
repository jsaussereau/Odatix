#################################################################################
# ELABORATE STEP
#################################################################################
source scripts/settings.tcl
source scripts/step_analyze_script.tcl

elaborate $top_level_module
report_progress 15 $synth_statusfile
#report progress 30 $analysis_statusfile

puts ""
puts "============================================================"
puts "<bold><cyan> DESIGN CHECK <end>" 
puts "============================================================"

check_design > $design_analysis
check_design
#report_progress 40 $analysis_statusfile

puts ""
puts "============================================================"
puts "<bold><cyan> UNRESOLVED REFERENCES <end>"
puts "============================================================"

check_design -unresolved > $unresolved_report
check_design -unresolved

report_progress 20 $synth_statusfile

puts ""
puts "============================================================"
puts "<bold><cyan> DESIGN INFORMATION <end>"
puts "============================================================"

puts "Top module: $top_level_module"
puts "Current design: [get_db current_design .name]"

if {[info exists odatix_mode] && $odatix_mode == "analysis"} {

    # Define arch_name variable for printing 
    set arch_name "Unknown"
    if {[file exists $architecture_file]} {
        set fp_arch [open $architecture_file r]
        set arch_name [string trim [read $fp_arch]]
        close $fp_arch
    }

    set unresolved_count 0

    if {[file exists $unresolved_report]} {

        set fp_unres [open $unresolved_report r]
        set unresolved_data [read $fp_unres]
        close $fp_unres
        if {[regexp {Total number of unresolved references.*:\s*([0-9]+)} \
            $unresolved_data -> unresolved_count]} {
            # unresolved_count updated
        }
    }

    report_messages -all

    puts " "
    puts " "
    puts "----------------------------------------"
    puts "<bold><cyan>Analysis Summary<end>"
    puts "----------------------------------------"
    puts "Architecture : $arch_name"
    puts "<green> Read Designs         <bold>PASSED<end>"
    if {$unresolved_count == 0} {
        puts "<green> Unresolved Designs      $unresolved_count<end>"
    } else {
        puts "<yellow> Unresolved Designs     $unresolved_count<end>"
    }
    puts ""
    puts "<cyan>Press 'q' to view the analysis summary.<end>"

    report_progress 100 $synth_statusfile

}
