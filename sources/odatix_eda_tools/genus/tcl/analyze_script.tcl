#################################################################################
# Odatix - Genus Analyze Script
#################################################################################

source scripts/is_slack_met.tcl

if {[catch {

    set signature "<grey>\[analyze_script.tcl\]<end>"

    source scripts/settings.tcl
    report_progress 5 $synth_statusfile

    #-----------------------------------------------------------------------------
    # Load technology setup
    #-----------------------------------------------------------------------------


    #################################################################################
    # GENUS SETUP 
    #################################################################################

    set analysis_mode [expr {[info exists odatix_mode] && $odatix_mode == "analysis"}]

    # Noise for a synthesis, but what an analysis looks for (VLOGPT-37 is an
    # undeclared variable): the messages of an analysis are all kept, the
    # normal ones being declared expected in analysis.yml.
    if {!$analysis_mode} {
        suppress_messages {LBR-9 VLOGPT-6 HPT-76 CDFG-818 VHDL-639 VLOGPT-37 VHDLPT-800 VHDLPT-801}
    }

    # An analysis targets no technology: without a setup script, the design is
    # elaborated with the generic library of the scripts, which is all checking
    # it needs (Genus elaborates nothing without a library).
    if {[file exists $script_path/genus_setup.tcl] || !$analysis_mode} {
        if { [catch { source scripts/genus_setup.tcl } errmsg] } {
            puts "$signature <bold><red>error: could not source 'genus_setup.tcl'<end>"
            puts "$signature tool says -> $errmsg"
            exit -1
        }
    } else {
        puts "$signature <cyan>note: no technology, elaborating with a generic library<end>"
        read_libs $script_path/analysis_library.lib
    }

    #-----------------------------------------------------------------------------
    # RTL PATH
    #-----------------------------------------------------------------------------
    set rtl_path [file normalize $rtl_path]

    #-----------------------------------------------------------------------------
    # First we check if there is a filelist with the order of compilation
    # If there is no filelist, we use the get_files_recursive function
    # NOTE: Relative paths in filelist.f are relative to the filelist itself
    #-----------------------------------------------------------------------------



    #suppress_messages LBR-9


    if {[file exists "$rtl_path/filelist.f"]} {

        puts "$signature <cyan>Using filelist: $rtl_path/filelist.f<end>"

        foreach line [read_filelist "$rtl_path/filelist.f"] {
            if {[string match "*.v" $line]} {
                read_hdl -language v2001 $line
            } elseif {[string match "*.sv" $line] || [string match "*.svh" $line]} {
                read_hdl -language sv $line
            } elseif {[string match "*.vhd" $line] || [string match "*.vhdl" $line]} {
                read_hdl -language vhdl $line
            }
        }

    } else {

        #-----------------------------------------------------------------------------
        # READ VERILOG
        #-----------------------------------------------------------------------------
        set verilog_filenames [get_files_recursive $rtl_path {*.v}]

        if {[llength $verilog_filenames] != 0} {

            puts "$signature <cyan>Verilog files:<end>"

            foreach file $verilog_filenames {
                puts "  <cyan>- $file<end>"
            }
            if {[catch {
                read_hdl -language v2001 $verilog_filenames
            } errmsg ]} {
                puts "Error: for more info, please check the <bold><cyan>.log<end> file avaible in: $log_path/analyze_script.tcl.log"
                exit -1
            }  

            report_progress 8 $synth_statusfile
        }

        #-----------------------------------------------------------------------------
        # READ SYSTEMVERILOG
        #-----------------------------------------------------------------------------
        set sverilog_filenames [get_files_recursive $rtl_path {*.sv *.svh}]

        if {[llength $sverilog_filenames] != 0} {

            puts "$signature <cyan>SystemVerilog files:<end>"

            foreach file $sverilog_filenames {
                puts "  <cyan>- $file<end>"
            }
            if {[catch {
                read_hdl -language sv $sverilog_filenames
            } errmsg ]} {
                exit -1
            }

            report_progress 8 $synth_statusfile
        }

        
        

        #-----------------------------------------------------------------------------
        # READ VHDL
        #-----------------------------------------------------------------------------
        set vhdl_filenames [get_files_recursive $rtl_path {*.vhd *.vhdl}]

        if {[llength $vhdl_filenames] != 0} {

            puts "$signature <cyan>VHDL files:<end>"

            foreach file $vhdl_filenames {
                puts "  <cyan>- $file<end>"
            }
            if {[catch {
                read_hdl -language vhdl $vhdl_filenames
            } errmsg ]} {
                exit -1
            } 

            #read_hdl -language vhdl $vhdl_filenames
            report_progress 8 $synth_statusfile
            #report_progress 20 $analysis_statusfile
        }
    }

    #################################################################################
    # ELABORATE
    #################################################################################

    # A design that does not elaborate: the tool said why, there is no more to
    # check (analysis.yml reads it from the log)
    if {[catch {elaborate $top_level_module}]} {
        if {$analysis_mode} {
            exit -1
        }
        error "could not elaborate '$top_level_module'"
    }
    report_progress 15 $synth_statusfile

    if {$analysis_mode} {

        # Every check of the elaborated design, and its latches, which Genus
        # names nowhere else: analysis.yml reads both reports
        puts ""
        puts "============================================================"
        puts "<bold><cyan> DESIGN CHECK <end>"
        puts "============================================================"

        check_design -all > $design_analysis
        check_design -all

        set fp_latches [open $report_path/latches.rep w]
        foreach inst [get_db insts -if {.is_latch == true}] {
            puts $fp_latches $inst
        }
        close $fp_latches

        report_progress 100 $synth_statusfile

    } else {

        puts ""
        puts "============================================================"
        puts "<bold><cyan> DESIGN CHECK <end>"
        puts "============================================================"

        check_design > $design_analysis
        check_design

        puts ""
        puts "============================================================"
        puts "<bold><cyan> UNRESOLVED REFERENCES <end>"
        puts "============================================================"

        check_design -unresolved > $unresolved_report
        check_design -unresolved

        report_progress 20 $synth_statusfile
    }

} ]} {

    puts "$signature <bold><red>error: unhandled tcl error<end>"
    puts "$errorInfo"
    exit -1
}
