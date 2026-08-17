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

# Step "pnr" of an fmax search: search on post-route timing.
#
# Every iteration synthesizes and implements, which is the frequency the design
# actually reaches. This is what "odatix fmax" has always done; it is a step of
# its own so that a design space can be screened on synthesis timing first and
# only implemented where it is worth it.
#
# The search restarts from the RTL rather than from what the previous step left:
# a binary search converges to its own frequency, there is no partial result of
# one search that the next can continue from. It overwrites the search log, so
# the exported Fmax becomes the implemented one.

set ::odatix_synth_depth "pnr"

source scripts/find_fmax.tcl
