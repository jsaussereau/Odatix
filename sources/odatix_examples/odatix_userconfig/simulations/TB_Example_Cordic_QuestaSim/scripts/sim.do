
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

########################################################
# Configuration
########################################################

# The testbench needs to know the parameters Odatix wrote in the RTL file, so
# that it can build its reference model. Odatix substitutes the value of each
# parameter domain of the architecture in the command of _settings.yml
# (${width} and ${iterations}), which passes them here as environment
# variables, so nothing has to be read back from the source.
set cfg_width ""
set cfg_iterations ""
if {[info exists ::env(CFG_WIDTH)]} {
  set cfg_width $::env(CFG_WIDTH)
}
if {[info exists ::env(CFG_ITERATIONS)]} {
  set cfg_iterations $::env(CFG_ITERATIONS)
}

if {$cfg_width eq "" || $cfg_iterations eq ""} {
  die "CFG_WIDTH and CFG_ITERATIONS must be set (Odatix passes them from the \"width\" and \"iterations\" parameter domains)"
}

puts ""
puts "######################################"
puts "              Compiling               "
puts "######################################"
puts ""
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
