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

# Former entry script of the "power_opt" flow, kept for the flows of a
# workspace that still source it: automatic clock gating at synthesis, then a
# power optimization pass. The built-in flows now set these through their
# "parameters" in tool.yml, which odatix_vivado_synthesize reads.
set ::odatix_synth_options "-gated_clock_conversion auto"
set ::odatix_power_opt 1
