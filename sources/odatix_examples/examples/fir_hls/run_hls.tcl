#
# High-Level Synthesis script for the FIR example.
#
# Odatix runs this from the job's work directory, as the architecture's
# "generate_command":
#
#   vitis_hls -f run_hls.tcl -tclargs ${taps} ${ii} ${partition}
#
# The three arguments come from the "taps", "ii" and "partition" variables of
# the architecture, so one point of the design space is one run of this script.
# "ii" and "partition" are both HLS pragmas: the first is the value of a
# directive, the second selects which directive is applied at all.
# What it produces is the Verilog Vivado (or any other supported eda tool) then
# synthesizes: the script copies it into "rtl/", where Odatix reads the design
# from.

######################################
# Arguments
######################################

# Defaults, so the script stays runnable by hand outside Odatix.
set taps      16       ; # number of filter taps  -> "-DTAPS=<n>" (generation parameter)
set ii        1        ; # initiation interval of the MAC loop -> pipeline directive (pragma)
set partition "complete" ; # how the tap delay line is stored    -> array_partition directive (pragma)

# Vitis HLS hands the whole command line over in "argv" ("-f run_hls.tcl 16 2"),
# not just what followed "-tclargs", so its own options are dropped first.
set args {}
if {[info exists argv]} {
  set args $argv
  set marker [lsearch -exact $args "-tclargs"]
  if {$marker >= 0} {
    set args [lrange $args [expr {$marker + 1}] end]
  }
  set marker [lsearch -exact $args "-f"]
  if {$marker >= 0} {
    set args [lrange $args [expr {$marker + 2}] end]
  }
}

if {[llength $args] > 0} { set taps      [lindex $args 0] }
if {[llength $args] > 1} { set ii        [lindex $args 1] }
if {[llength $args] > 2} { set partition [lindex $args 2] }

# The FPGA part HLS estimates against. It only drives HLS scheduling: the
# numbers Odatix reports come from the real synthesis that follows, on the
# target declared in "odatix_userconfig/targets/target_vivado.yml".
set part   "xc7a100tcsg324-1"
set period 5.0 ; # ns

puts "\[run_hls.tcl\] taps=$taps ii=$ii partition=$partition part=$part period=${period}ns"

######################################
# Project
######################################

open_project -reset hls_proj
set_top fir

# TAPS is passed to the C++ front end instead of being written in the source,
# so the sweep needs no parameter file and no delimiters.
add_files src/fir.cpp -cflags "-Isrc -DTAPS=$taps"

open_solution -reset "solution" -flow_target vivado
set_part $part
create_clock -period $period -name default

######################################
# Directives (the pragmas being explored)
######################################

# Pipelining the MAC loop at a given initiation interval is the knob that
# trades throughput against area: II=1 unrolls one tap per cycle and needs a
# multiplier per issue slot, larger IIs let the operators be shared.
set_directive_pipeline -II $ii "fir/mac_loop"

# How the tap delay line is stored. Unlike the initiation interval, this knob
# is not a number but a *choice of pragma*: "none" applies no directive at all
# and leaves the delay line in a bram (two accesses per cycle at most, so the
# requested II is unreachable for long filters), "cyclic" splits it into a few
# banks, "complete" turns it into registers readable in parallel.
switch -exact -- $partition {
  none {
    # No directive: this is the point of comparison the two others are read
    # against.
  }
  cyclic {
    set_directive_array_partition -type cyclic -factor 4 -dim 1 "fir" shift_reg
  }
  complete {
    set_directive_array_partition -type complete -dim 1 "fir" shift_reg
  }
  default {
    puts "\[run_hls.tcl\] error: unknown partition '$partition' (none|cyclic|complete)"
    exit 1
  }
}

######################################
# Synthesis
######################################

csynth_design

######################################
# Export the RTL where Odatix reads it
######################################

# Odatix always reads the design from the "rtl" directory of the work
# directory, whatever produced it (see "generate_output" in "_settings.yml").
file mkdir rtl
foreach rtl_file [glob -nocomplain hls_proj/solution/syn/verilog/*.v] {
  file copy -force $rtl_file rtl
}

if {[llength [glob -nocomplain rtl/*.v]] == 0} {
  puts "\[run_hls.tcl\] error: high-level synthesis produced no verilog file"
  exit 1
}

exit 0
