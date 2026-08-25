#################################################################################
# Odatix - Genus Analyze Script
#################################################################################

source scripts/is_slack_met.tcl

if {[catch {

    set signature "<grey>\[analyze_script.tcl\]<end>"

    source scripts/settings.tcl
    report_progress 25 $synth_statusfile

    #################################################################################
    # GENUS SETUP 
    #################################################################################

    suppress_messages {LBR-9 VLOGPT-6 HPT-76 CDFG-818 VHDL-639 VLOGPT-37 VHDLPT-800 VHDLPT-801}

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
    # First we check if there is a filelist with the order of compilation
    # If there is no filelist, we use the get_files_recursive function
    # NOTE: The files in the filelist.f must have the absolute path
    #-----------------------------------------------------------------------------

    if {[file exists "$rtl_path/filelist.f"]} {
        puts "$signature <cyan>Using filelist: $rtl_path/filelist.f<end>"
        set fp [open "$rtl_path/filelist.f" r]
        while {[gets $fp line] >= 0} {
            set line [string trim $line]
            if {$line eq ""} {
                continue
            }
            if {[string match "*.v" $line]} {
                read_hdl -language v2001 $line
            } elseif {[string match "*.sv" $line] || [string match "*.svh" $line]} {
                read_hdl -language sv $line
            } elseif {[string match "*.vhd" $line]} {
                read_hdl -language vhdl $line
            }
        }
        close $fp
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
            catch {
                read_hdl -language v2001 $verilog_filenames
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
            catch {
                read_hdl -language sv $sverilog_filenames
            } errmsg
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
            catch {
                read_hdl -language vhdl $vhdl_filenames
            } errmsg
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
    
    report_progress 100 $synth_statusfile

} ]} {
    puts "$signature <bold><red>error: unhandled tcl error<end>"
    puts "$errorInfo"
    exit -1
}
