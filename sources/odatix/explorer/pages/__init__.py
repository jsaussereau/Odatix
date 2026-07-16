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
Importing this package registers every explorer page (dash.register_page)
into the current Dash app. A dash.Dash(use_pages=True) app must exist first.
"""

import odatix.explorer.pages.home
import odatix.explorer.pages.lines
import odatix.explorer.pages.columns
import odatix.explorer.pages.scatter
import odatix.explorer.pages.scatter3d
import odatix.explorer.pages.radar
import odatix.explorer.pages.overview
