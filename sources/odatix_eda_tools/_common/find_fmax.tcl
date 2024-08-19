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

if {[catch {

  ######################################
  # Settings
  ######################################
  source scripts/settings.tcl
  source scripts/init_script.tcl
  source scripts/is_slack_met.tcl
  source scripts/update_freq.tcl

  set signature "<grey>\[find_fmax.tcl\]<end>"

  set lower_bound $fmax_lower_bound
  set upper_bound $fmax_upper_bound


  ######################################
  # Procedures
  ######################################

  proc sleep {N} {
    after [expr {int($N * 1000)}]
  }

  proc pause {{message "Hit Enter to continue..."}} {
    puts $message
    flush stdout
    gets stdin
  }

  proc run_synth_script {synth_script} {
    source $synth_script
  }

  ######################################
  # Algorithm
  ######################################

  #log_file -noappend $log_path/find_fmax.tcl.log

  # sanity checks
  if {$upper_bound < $lower_bound} {
    error "$signature <red>upper bound ($upper_bound) cannot be smaller than lower bound ($lower_bound)<end>"
    exit -1
  }

  # create tmp folders
  exec /bin/sh -c "mkdir -p $tmp_path/report_MET"
  exec /bin/sh -c "mkdir -p $tmp_path/report_VIOLATED"		

  # create logfile
  exec /bin/sh -c "mkdir -p $log_path"
  set logfile_handler [open $logfile w]
  puts $logfile_handler "Binary search for interval \[$lower_bound:$upper_bound\] MHz"
  puts $logfile_handler ""
  close $logfile_handler

  set start_lower_bound $lower_bound
  set start_upper_bound $upper_bound

  set max_runs [expr {int(ceil((log(($start_upper_bound-$start_lower_bound)/$fmax_mindiff)/log(2))))}]
  report_progress 0 $statusfile "(1/$max_runs)"

  set got_met 0
  set got_violated 0

  set fs_start_time [clock seconds]

  # do analyze and elaborate steps once
  source $analyze_script

  # do not analyze rtl after that (try tcsh and bash versions)
  set DO_NOT_ANALYZE_RTL 1
  #setenv DO_NOT_ANALYZE_RTL=1
  #export DO_NOT_ANALYZE_RTL=1

  set runs 0

  while 1 {

    set runs [expr {$runs + 1}]

    # compute current frequency
    set mean [expr {($upper_bound + $lower_bound) / 2}]
    set cur_freq $mean

    set logfile_handler [open $logfile a]
    puts -nonewline $logfile_handler  "$cur_freq MHz: "
    close $logfile_handler

    # run synthesis script with the current frequency
    update_freq $cur_freq $constraints_file
    puts ""  
    puts "<bold><cyan>"
    puts "######################################"
    puts "   Running synthesis at $cur_freq MHz "
    puts "######################################"
    puts "<end>"

    run_synth_script $synth_script

    set frequency_handler [open $freq_rep w]
    puts -nonewline $frequency_handler  "Target frequency:         $cur_freq"
    close $frequency_handler

    # update bounds depending on slack
    if {[is_slack_met $timing_rep]} {
      set lower_bound $cur_freq
      set got_met 1
      puts ""
      #puts "<bold><green>$cur_freq MHz: MET<end>"
      set logfile_handler [open $logfile a]
      puts $logfile_handler  "MET"
      close $logfile_handler
      exec /bin/sh -c "cp -r $report_path/* $tmp_path/report_MET"
    } else {
      set upper_bound $cur_freq
      puts ""
      #puts "<bold><red>$cur_freq MHz: VIOLATED<end>"
      if {[is_slack_inf $timing_rep]} {
        set logfile_handler [open $logfile a]
        puts $logfile_handler  "INFINITE"
        puts ""
        puts "$signature <bold><red>Path is unconstrained. Make sure there are registers at input and output of design. Make sure you select the correct clock signal.<end>"
        puts "$signature <cyan>Both the rtl description and the tool's synthesis choices could be at fault<end>"
        puts $logfile_handler "Path is unconstrained. Make sure there are registers at input and output of design.  Make sure you select the correct clock signal. Both the rtl description and the tool's synthesis choices could be at fault"
        close $logfile_handler
        exit -2
      } else {
        set got_violated 1
        set logfile_handler [open $logfile a]
        puts $logfile_handler  "VIOLATED"
        close $logfile_handler
      }
      exec /bin/sh -c "cp -r $report_path/* $tmp_path/report_VIOLATED"
    }

    set diff [expr {$upper_bound - $lower_bound}]

    # move bounds
    if {$fmax_explore == 1} {
      if {$diff < $fmax_safezone && $runs > 2} {
        if {$got_violated == 0} {
          set upper_bound [expr {$upper_bound + 2*$fmax_safezone}]
          set start_upper_bound $upper_bound
        }
        if {$got_violated == 0} {
          set lower_bound [expr {$lower_bound - 2*$fmax_safezone}]
          set start_lower_bound $lower_bound
        } 
      } 
    }

    # exit condition
    if {[expr abs($diff)] <  [expr {$fmax_mindiff + 1}] } {
      break
    }

    set progress [expr {round(100 * $runs / $max_runs)}]
    report_progress $progress $statusfile "($runs/$max_runs)"
  }

  report_progress 100 $statusfile "($runs/$max_runs)"

  set fs_stop_time [clock seconds]
  set fs_total_time [expr $fs_stop_time - $fs_start_time]

  set s [expr {$fs_total_time % 60}]
  set i [expr {$fs_total_time / 60}]
  set m [expr {$i % 60}]
  set h [expr {$i / 60}]
  set fs_total_time_formatted [format "%02d:%02d:%02d" $h $m $s]
  #set total_time_formatted [clock format $total_time -format %H:%M:%S]
  puts ""
  puts "$signature total time for max frequency search: $fs_total_time_formatted ($fs_total_time seconds)" 

  set logfile_handler [open $logfile a]
  puts $logfile_handler  ""

  if {$got_met == 1 && $got_violated == 1} {
    #restore reports and results from the synthesis meeting timing requirements
    exec /bin/sh -c "cp -r $tmp_path/report_MET/* $report_path"

    update_freq $lower_bound $constraints_file

    puts $logfile_handler "Highest frequency with timing constraints being met: $lower_bound MHz"
    puts ""
    puts "$signature <bold><cyan>Highest frequency with timing constraints being met: $lower_bound MHz<end>"
    puts "$signature Report summaries for this synthesis:"
    source $summary_script
  } elseif {$got_met == 0 && $got_violated == 0} {
    puts ""
    puts "$signature <bold><red>Path is unconstrained. Make sure there are registers at input and output of design<end>"
    puts "$signature <cyan>Both the rtl description and the tool's synthesis choices could be at fault<end>"
    puts $logfile_handler "Path is unconstrained. Make sure there are registers at input and output of design. Both the rtl description and the tool's synthesis choices could be at fault"
    exit -2
  } elseif {$got_violated == 0} {
    puts ""
    puts "$signature <bold><red>No timing violated! Try raising the upper bound ($upper_bound MHz)<end>"
    puts $logfile_handler "No timing violated! Try raising the upper bound ($upper_bound MHz)"
    exit -3
  } else {
    puts ""
    puts "$signature <bold><red>No timing met! Try lowering the lower bound ($lower_bound MHz)<end>"
    puts $logfile_handler "No timing met! Try lowering the lower bound ($lower_bound MHz)"
    exit -4
  }

  close $logfile_handler

  exit

} ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    catch {
      puts "$signature <cyan>tcl error detail:<red>"
      puts "$errorInfo"
    }
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}