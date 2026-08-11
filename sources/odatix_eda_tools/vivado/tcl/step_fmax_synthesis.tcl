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

# Step "synthesis" of an fmax search: search on post-synthesis timing.
#
# Every iteration of the binary search stops after logic optimization, so the
# frequency it converges to is the one the synthesized netlist meets — much
# faster to obtain than the implemented one, and optimistic. That is what makes
# it worth running on a whole design space before implementing the part of it
# that turns out to be interesting.
#
# The next step searches again on post-route timing (see step_fmax_pnr.tcl):
# both searches start from the RTL, so nothing is handed over between them
# beyond the result already exported.

set ::odatix_synth_depth "synthesis"

source scripts/find_fmax.tcl
