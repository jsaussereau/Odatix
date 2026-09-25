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
    set filelist_path [file join $rtl_path "filelist.f"]

    if {[file exists $filelist_path]} {
        puts "$signature <cyan>filelist.f found, analyzing RTL from filelist<end>"
        set fp [open $filelist_path r]
        set rtl_files {}
        while {[gets $fp line] >= 0} {
            set line [string trim $line]
            # Ignore empty lines
            if {$line eq ""} {
                continue
            }
            # Ignore comments
            if {[string match "#*" $line]} {
                continue
            }
            # If path is relative, make it relative to rtl_path
            if {[file pathtype $line] eq "relative"} {
                set line [file join $rtl_path $line]
            }
            lappend rtl_files $line
        }
        close $fp
        analyze \
            -format vhdl \
            -hdl_library WORK \
            $rtl_files
    } else {
        puts "$signature <cyan>No filelist.f found, using autoread<end>"
        analyze -autoread \
            -recursive \
            -hdl_library WORK \
            -top $top_level_module \
            $rtl_path
    }
    report_progress 20 $synth_statusfile

    ###########################################################################
    # Elaborate
    ###########################################################################

    puts "$signature <cyan>Elaborating $top_level_module<end>"
    elaborate \
        -hdl_library WORK \
        $top_level_module
    puts "$signature <cyan>Elaboration done<end>"
    report_progress 40 $synth_statusfile

    ###########################################################################
    # Set top
    ###########################################################################

    puts "$signature <cyan>Setting top module<end>"
    set_top_module $top_level_module
    puts "$signature <cyan>Top module set successfully<end>"
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