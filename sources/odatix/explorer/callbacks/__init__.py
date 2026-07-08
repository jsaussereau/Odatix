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
Explorer callback registration. All callbacks use dash.callback (module
level), so they register into whichever Dash app exists in the process
(Odatix GUI or the standalone shell). Registration is idempotent.
"""

_registered = False


def register_callbacks():
  global _registered
  if _registered:
    return

  import odatix.explorer.callbacks.data as data
  import odatix.explorer.callbacks.controls as controls
  import odatix.explorer.callbacks.filters as filters
  import odatix.explorer.callbacks.figure as figure

  data.register_callbacks()
  controls.register_callbacks()
  filters.register_callbacks()
  figure.register_callbacks()

  _registered = True
