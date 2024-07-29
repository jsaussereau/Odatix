#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

import os
import sys
import dash
from dash import dcc, html

def navigation_bar():
    return html.Div([
        dcc.Link('Asterism Explorer', href='/', className='title'),
        html.Div([
            dcc.Link('XY', href='/xy', className='nav-link'),
            dcc.Link('VS', href='/vs', className='nav-link'),
            dcc.Link('Radar', href='/radar', className='nav-link'),
            # dcc.Link('Help', href='/help', className='nav-link')
        ], className='nav-links')
    ], className='navbar')