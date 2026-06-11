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
    #source scripts/genus_setup.tcl


    #################################################################################
    # GENUS SETUP 
    #################################################################################

    #set LIB_SEARCH_PATHS []

    #lappend LIB_SEARCH_PATHS .
    #lappend LIB_SEARCH_PATHS /asic/pdk/ams/AMS_410_CDS/liberty/c35_1.8V

    #set_db init_lib_search_path $LIB_SEARCH_PATHS

    #read_libs c35_CORELIB_WC.lib

    ## Here it's the absolut path, we have to change for scripts/genus_setup.tcl
    if { [catch { source scripts/genus_setup.tcl } errmsg] } { 
            puts "$signature <bold><red>error: could not source 'genus_setup.tcl'<end>" 
            puts "$signature tool says -> $errmsg" 
            exit -1 
            }

    #-----------------------------------------------------------------------------
    # RTL PATH
    #-----------------------------------------------------------------------------
    set rtl_path [file normalize $rtl_path]

    #-----------------------------------------------------------------------------
    # READ VERILOG
    #-----------------------------------------------------------------------------
    set verilog_filenames [get_files_recursive $rtl_path {*.v}]

    if {[llength $verilog_filenames] != 0} {

        puts "$signature <cyan>Verilog files:<end>"

        foreach file $verilog_filenames {
            puts "  <cyan>- $file<end>"
        }

        read_hdl -language v2001 $verilog_filenames
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

        read_hdl -language sv $sverilog_filenames
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

        read_hdl -language vhdl $vhdl_filenames
        report_progress 8 $synth_statusfile
    }

    #################################################################################
    # ELABORATE
    #################################################################################

    elaborate $top_level_module
    report_progress 15 $synth_statusfile


    puts ""
    puts "============================================================"
    puts " DESIGN CHECK"
    puts "============================================================"

    check_design

    puts ""
    puts "============================================================"
    puts " UNRESOLVED REFERENCES"
    puts "============================================================"

    check_design -unresolved


    puts ""
    puts "============================================================"
    puts " TIMING CHECK"
    puts "============================================================"

    check_timing_intent


    puts ""
    puts "============================================================"
    puts " TIMING LINT"
    puts "============================================================"

    report_timing -lint


    puts ""
    puts "============================================================"
    puts " CLOCKS"
    puts "============================================================"

    report_clocks

    report_progress 20 $synth_statusfile


    puts ""
    puts "============================================================"
    puts " DESIGN INFORMATION"
    puts "============================================================"

    puts "Top module: $top_level_module"
    puts "Current design: [get_db current_design .name]"



} ]} {

    puts "$signature <bold><red>error: unhandled tcl error<end>"
    puts "$errorInfo"
    exit -1
}
