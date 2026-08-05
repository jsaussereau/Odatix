########################################################################
#                                Odatix                                #
########################################################################
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
########################################################################
#
# ModelSim/QuestaSim script for the CORDIC simulation.
#
# It is deliberately language agnostic: it looks at what Odatix copied into
# "rtl", compiles VHDL sources with vcom and Verilog/SystemVerilog sources
# with vlog, and runs the very same SystemVerilog testbench on top of either.
# The mixed language support of the simulator binds the testbench to the VHDL
# entity or to the SystemVerilog module, whichever was compiled.
#
# Run with:
#   vsim -c -do scripts/sim.do

########################################################
# Parameters
########################################################

set module     "cordic"
set tb_module  "tb_$module"

set rtl_dir    "rtl"
set tb_dir     "tb"
set log_dir    "log"
set vcd_dir    "vcd"
set work_lib   "work"

set progress_file "$log_dir/progress.log"
set result_file   "results.yml"
set vcd_file      "$vcd_dir/$module.vcd"
set transcript_file "$log_dir/sim.log"

# Language standards
set vhdl_std   "-2008"
set vlog_std   "-sv"

########################################################
# Helpers
########################################################

proc report_progress {percent} {
  global progress_file
  if {[catch {
    set fh [open $progress_file "w"]
    puts $fh "progress: $percent%"
    close $fh
  } err]} {
    puts "Warning: could not write progress file: $err"
  }
}

proc die {msg} {
  puts "Error: $msg"
  quit -code 1
}

# Recursively collect the files of "dir" matching one of the "patterns"
proc find_files {dir patterns} {
  set found {}
  if {![file isdirectory $dir]} {
    return $found
  }
  foreach pattern $patterns {
    foreach f [lsort [glob -nocomplain -directory $dir $pattern]] {
      lappend found $f
    }
  }
  foreach sub [lsort [glob -nocomplain -type d -directory $dir *]] {
    foreach f [find_files $sub $patterns] {
      lappend found $f
    }
  }
  return $found
}

# Read back a parameter Odatix wrote in the RTL file. Both the VHDL generic
# form ("WIDTH : integer := 16") and the Verilog parameter form
# ("parameter WIDTH = 16") are accepted, so that the same script serves both
# versions of the design.
proc read_parameter {file name} {
  set fh [open $file "r"]
  set content [read $fh]
  close $fh

  # VHDL: WIDTH : integer := 16
  if {[regexp -line "$name\\s*:\\s*\[a-zA-Z_\]+\\s*:=\\s*(\[0-9\]+)" $content -> value]} {
    return $value
  }
  # Verilog / SystemVerilog: parameter [type] WIDTH = 16
  if {[regexp -line "parameter\\s+(?:\[a-zA-Z_\]\[a-zA-Z0-9_\]*\\s+)?$name\\s*=\\s*(\[0-9\]+)" $content -> value]} {
    return $value
  }
  return ""
}

########################################################
# Setup
########################################################

file mkdir $log_dir
file mkdir $vcd_dir

transcript file $transcript_file
if {[file exists $result_file]} {
  file delete $result_file
}

report_progress 1

########################################################
# Source files
########################################################

set vhdl_sources [find_files $rtl_dir {*.vhd *.vhdl}]
set vlog_sources [find_files $rtl_dir {*.v *.sv *.svh}]

if {[llength $vhdl_sources] == 0 && [llength $vlog_sources] == 0} {
  die "no source file found in '$rtl_dir'"
}

# The top level file, used to read the configuration back
set top_file ""
foreach f [concat $vhdl_sources $vlog_sources] {
  if {[file rootname [file tail $f]] eq $module} {
    set top_file $f
    break
  }
}
if {$top_file eq ""} {
  die "could not find the top level file of '$module' in '$rtl_dir'"
}

########################################################
# Configuration
########################################################

# The testbench needs to know the parameters Odatix wrote in the RTL file, so
# that it can build its reference model. They are read back from the source and
# forwarded to the elaboration of the testbench.
set cfg_width      [read_parameter $top_file "WIDTH"]
set cfg_iterations [read_parameter $top_file "ITERATIONS"]

if {$cfg_width eq "" || $cfg_iterations eq ""} {
  die "could not read WIDTH/ITERATIONS back from '$top_file'"
}

puts ""
puts "######################################"
puts "              Compiling               "
puts "######################################"
puts ""
puts "top level file = $top_file"
puts "WIDTH = $cfg_width, ITERATIONS = $cfg_iterations"

########################################################
# Compilation
########################################################

if {[file isdirectory $work_lib]} {
  vdel -all -lib $work_lib
}
vlib $work_lib

if {[llength $vhdl_sources] > 0} {
  if {[catch {eval vcom $vhdl_std -work $work_lib $vhdl_sources} err]} {
    die "VHDL compilation failed: $err"
  }
}
report_progress 2

if {[llength $vlog_sources] > 0} {
  if {[catch {eval vlog $vlog_std -work $work_lib $vlog_sources} err]} {
    die "Verilog compilation failed: $err"
  }
}
report_progress 3

# The testbench itself is always SystemVerilog: it drives the design through
# its ports only, so it does not care which language the design is written in.
set tb_sources [find_files $tb_dir {*.v *.sv *.svh}]
if {[llength $tb_sources] == 0} {
  die "no testbench source found in '$tb_dir'"
}
if {[catch {eval vlog $vlog_std -work $work_lib $tb_sources} err]} {
  die "testbench compilation failed: $err"
}

report_progress 5

########################################################
# Simulation
########################################################

puts ""
puts "######################################"
puts "              Simulating              "
puts "######################################"
puts ""

if {[catch {
  vsim -quiet -t 1ps \
    -gWIDTH=$cfg_width -gITERATIONS=$cfg_iterations \
    $work_lib.$tb_module
} err]} {
  die "elaboration failed: $err"
}

# Waveform, in the same format as the other example simulations, so that the
# result can be opened with gtkwave. Only the design is dumped: the testbench
# also holds its reference model, whose types have no vcd representation.
set dump_waves 1
if {$dump_waves} {
  if {[catch {
    vcd file $vcd_file
    vcd add -r /$tb_module/uut/*
  } err]} {
    puts "Warning: could not set up the vcd dump: $err"
  }
}

if {[catch {run -all} err]} {
  die "simulation failed: $err"
}

if {$dump_waves} {
  catch {vcd flush}
}

########################################################
# Results
########################################################

if {![file exists $result_file]} {
  die "the testbench did not write '$result_file'"
}

report_progress 100

quit -code 0
