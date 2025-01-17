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

import dash
from dash import html, dcc, callback, Input, Output

import odatix.explorer.legend as legend
import odatix.explorer.navigation as navigation

dash.register_page(
  __name__,
  path='/columns',
  title='Odatix - Columns',
  name='Columns',
  order=2,
)

layout = html.Div(
  [
    html.Div(
      id="graph-columns",
      style={"width": "100%", "height": "100%"},
      className="graph-container"
    )
  ],
  id = f"{__name__}-content",
  style={"width": "100%", "height": f"calc(100vh - {navigation.top_bar_height})"},
)
