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

"""
What a simulation needs besides its own files.

  - :mod:`odatix.sim.design_info`: what Odatix tells a simulation about the
    design under test (its sources in compilation order, its top, its clock and
    reset, the value of each parameter domain), written into the work directory
    of every simulation job;
  - :mod:`odatix.sim.templates`: the simulations Odatix provides for each
    simulator, which a run can name and a simulation can start from;
  - :mod:`odatix.sim.runner`: what the script of a template is written with.
"""
