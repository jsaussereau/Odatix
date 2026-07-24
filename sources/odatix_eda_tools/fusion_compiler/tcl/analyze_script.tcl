if {[catch {

    set signature "<grey>\[analyze_script.tcl\]<end>"
    source scripts/settings.tcl

    source scripts/fc_setup.tcl


    if {[info exists synthesis_mode] && $synthesis_mode == "physical"} {
        puts "<bold><yellow>Mode: Physical synthesis<end>"
    } else {
        puts "<bold><yellow>Mode: Setting mode for Logical synthesis<end>"
        set_non_physical_mode
    }

    ###########################################################################
    # Read RTL
    ###########################################################################

    puts "$signature <cyan>Reading RTL<end>"

    if {[file exists "$rtl_path/filelist.f"]} {

        puts "$signature <cyan>Using filelist: $rtl_path/filelist.f<end>"

        analyze -autoread \
            -top $top_level_module \
            -f "$rtl_path/filelist.f"

    } else {

        puts "$signature <cyan>Searching RTL sources in $rtl_path<end>"

        analyze -autoread \
            -recursive \
            -top $top_level_module \
            $rtl_path
    }

    report_progress 20 $synth_statusfile

    ###########################################################################
    # Elaborate
    ###########################################################################

    elaborate $top_level_module
    report_progress 40 $synth_statusfile
    set_top_module $top_level_module
    report_progress 60 $synth_statusfile

    ###########################################################################
    # Reports
    ###########################################################################

    report_design        > $design_analysis
    report_hierarchy     > $report_path/hierarchy.rep
    report_ref_libs      > $report_path/ref_libs.rep

    report_progress 80 $synth_statusfile

    ###########################################################################
    # Summary
    ###########################################################################

    puts ""
    puts "----------------------------------------"
    puts "<bold><cyan>Analysis Summary<end>"
    puts "----------------------------------------"
    puts "Top module : $top_level_module"
    puts "<green>RTL analysis completed successfully.<end>"

    report_progress 100 $synth_statusfile

} errmsg] } {

    puts "$signature <bold><red>error:<end> $errmsg"
    puts "$errorInfo"
    exit -1
}