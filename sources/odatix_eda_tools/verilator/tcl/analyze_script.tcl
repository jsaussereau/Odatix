source scripts/settings.tcl

puts ""
puts "----------------------------------------"
puts "Running Verilator RTL Analysis"
puts "----------------------------------------"
puts ""

puts "Top module: $top_level_module"
puts "Top file  : $top_level_file"

set cmd [list verilator \
    --cc \
    --top-module $top_level_module \
    rtl/$top_level_file]

puts "Command: $cmd"

set result [catch {eval exec $cmd} output]

puts $output

if {$result != 0} {
    exit 1
}

puts "Verilator analysis completed successfully"
report_progress 99 $synth_statusfile