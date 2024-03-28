proc update_freq {freq constraints_file} {
  set period [expr {(1.0/$freq)*1000.0}]
  set constraints_file_handler [open $constraints_file w]
  puts -nonewline $constraints_file_handler {create_clock -period }
  puts -nonewline $constraints_file_handler $period 
  puts $constraints_file_handler { [get_ports $clock_signal]}
  close $constraints_file_handler
}