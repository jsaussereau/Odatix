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
The two pages that configure and start an exploration: the campaign list
("/dse") and the campaign editor ("/dse_campaign").

What they edit is what "odatix dse" reads -- "dse_settings.yml" for how the
exploration is run and which campaigns it runs, one file per campaign for what
each of them is looking for (see :mod:`odatix.dse.settings`) -- and what they
start is the very same exploration a command line would (see
:mod:`odatix.dse.driver`).
"""
