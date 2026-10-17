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

# One session of the dummy tool: run the steps it is given, in order, in a
# single process.
#
# Odatix builds the command line from the "custom_freq_synthesis_session" key of
# tool.yml and what each step of the run adds to it ("args"), so this script
# receives the work directory followed by the names of the steps to run:
#
#   tclsh scripts/session.tcl <work_dir> synthesis pnr bitstream
#
# A real tool needs nothing of the sort — Vivado is given one "-source" per step
# and sources them itself. It is here because tclsh runs a single script.

set signature "<grey>\[session.tcl\]<end>"

source scripts/settings.tcl

foreach step [lrange $argv 1 end] {
    source [file join $script_path "step_$step.tcl"]
    # Record the step as soon as it is done rather than letting Odatix record
    # the whole session at the end, so a session dying halfway is resumable.
    odatix_step_done $step $signature
}
