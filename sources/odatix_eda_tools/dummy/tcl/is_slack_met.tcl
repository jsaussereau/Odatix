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
  set tfile [open $timing_rep]
  #check if we can find "slack (MET)" in the timing report
  while {[gets $tfile data] != -1} {
    if {[string match *[string toupper "slack (MET)"]* [string toupper $data]]} {
      close $tfile
      return 1  
    }
  }
  close $tfile
  return 0
}

proc is_slack_inf {timing_rep} {
  set tfile [open $timing_rep]
  #check if we can find "Slack:                    inf" in the timing report
  while {[gets $tfile data] != -1} {
    if {[string match *[string toupper "Slack:                    inf"]* [string toupper $data]]} {
      close $tfile
      return 1  
    }
  }
  close $tfile
  return 0
}
