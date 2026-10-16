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

# Read the worst slacks librelane_state.py wrote in timing.rep

proc odatix_librelane_setup_ws {timing_rep} {
  if {![file exists $timing_rep]} {
    return ""
  }
  set f [open $timing_rep r]
  set content [read $f]
  close $f
  if {[regexp {setup_ws: (\S+)} $content -> value]} {
    return $value
  }
  return ""
}

proc is_slack_met {report_path timing_rep} {
  set ws [odatix_librelane_setup_ws $timing_rep]
  if {$ws eq "" || $ws eq "inf"} {
    return 0
  }
  return [expr {$ws >= 0}]
}

proc is_slack_inf {report_path timing_rep} {
  return [expr {[odatix_librelane_setup_ws $timing_rep] eq "inf"}]
}
