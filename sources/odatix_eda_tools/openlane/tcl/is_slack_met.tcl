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

proc is_slack_met {timing_rep} {
  set timing_rep $report_path/metrics.csv
  set file_handler [open $timing_rep r]
  gets $file_handler header
  
  set wns_value 0.0
  
  set data_line [gets $file_handler]

  close $file_handler
  
  set data_fields [split $data_line ","]
  
  set header_fields [split $header ","]
  set wns_index [lsearch -exact $header_fields "wns"]
  set wns_value [lindex $data_fields $wns_index]
  set wns_value [expr {$wns_value + 0.0}]
  
  if {$wns_value >= 0} {
      return 1
  } else {
      return 0
  }
}

proc is_slack_inf {timing_rep} {
  return 0
}