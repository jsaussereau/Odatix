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

# Run the fmax search (find_fmax.tcl) at the depth ::odatix_synth_depth.
#
# find_fmax.tcl exits when the search ends, wherever it ends. Its log is copied
# under report/<depth> on the way out, so that the frequency each depth found
# survives the search of the next one ("Fmax" reads report/$step/).

rename exit odatix_tcl_exit
proc exit {{code 0}} {
    global report_path logfile
    catch {
        set stage_path [file join $report_path $::odatix_synth_depth]
        file mkdir $stage_path
        file copy -force $logfile $stage_path
    }
    odatix_tcl_exit $code
}

source scripts/settings.tcl
source scripts/find_fmax.tcl
