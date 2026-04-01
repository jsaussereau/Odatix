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

class Theme:
    theme = {
        'Color_Boxes': {
            'bar'               : '─',
            'border_left'       : ' ┊',
            'border_right'      : '┊ ',
            'progress_empty'    : '▅',
            'progress_full'     : '▅',
            'ballot_check'      : '➜ ',
            'ballot_empty'      : '  ',
            'spacer'            : ' ∙ ',
            'ellipsis'          : '…',
            'selected_bold'     : True,
            'selected_reverse'  : False,
            'colored_bar'       : True,
            'dim_empty_bar'     : True,
            'reserved_space'    : 32,
        },
        'ASCII_Highlight': {
            'bar'               : '-',
            'border_left'       : ' [',
            'border_right'      : '] ',
            'progress_empty'    : ' ',
            'progress_full'     : '#',
            'ballot_check'      : ' ',
            'ballot_empty'      : ' ',
            'spacer'            : '  ',
            'ellipsis'          : '...',
            'selected_bold'     : True,
            'selected_reverse'  : True,
            'colored_bar'       : False,
            'dim_empty_bar'     : False,
            'reserved_space'    : 29,
        },
        'ASCII_Highlight_Color': {
            'bar'               : '-',
            'border_left'       : ' [',
            'border_right'      : '] ',
            'progress_empty'    : ' ',
            'progress_full'     : '#',
            'ballot_check'      : ' ',
            'ballot_empty'      : ' ',
            'spacer'            : '  ',
            'ellipsis'          : '...',
            'selected_bold'     : True,
            'selected_reverse'  : True,
            'colored_bar'       : True,
            'dim_empty_bar'     : False,
            'reserved_space'    : 29,
        },
        'Color_Lines': {
            'bar'               : '─',
            'border_left'       : ' ┊',
            'border_right'      : '┊ ',
            'progress_empty'    : '━',
            'progress_full'     : '━',
            'ballot_check'      : ' ➜ ',
            'ballot_empty'      : '   ',
            'spacer'            : '  ',
            'ellipsis'          : '…',
            'selected_bold'     : True,
            'selected_reverse'  : False,
            'colored_bar'       : True,
            'dim_empty_bar'     : True,
            'reserved_space'    : 31,
        },
        'Legacy': {
            'bar'               : '─',
            'border_left'       : ' ┊',
            'border_right'      : '┊ ',
            'progress_empty'    : '🮏',
            'progress_full'     : '▅',
            'ballot_check'      : ' ✔ ',
            'ballot_empty'      : ' ❏ ',
            'spacer'            : '  ',
            'ellipsis'          : '…',
            'selected_bold'     : True,
            'selected_reverse'  : False,
            'colored_bar'       : False,
            'dim_empty_bar'     : False,
            'reserved_space'    : 31,
        },
        'Rectangles': {
            'bar'               : '─',
            'border_left'       : ' ┊',
            'border_right'      : '┊ ',
            'progress_empty'    : ' ',
            'progress_full'     : '▮',
            'ballot_check'      : ' ➜ ',
            'ballot_empty'      : '   ',
            'spacer'            : '  ',
            'ellipsis'          : '…',
            'selected_bold'     : True,
            'selected_reverse'  : False,
            'colored_bar'       : False,
            'dim_empty_bar'     : False,
            'reserved_space'    : 31,
        },
        'Rectangles_Color': {
            'bar'               : '─',
            'border_left'       : ' ┊',
            'border_right'      : '┊ ',
            'progress_empty'    : '▮',
            'progress_full'     : '▮',
            'ballot_check'      : ' ➜ ',
            'ballot_empty'      : '   ',
            'spacer'            : '  ',
            'ellipsis'          : '…',
            'selected_bold'     : True,
            'selected_reverse'  : False,
            'colored_bar'       : True,
            'dim_empty_bar'     : True,
            'reserved_space'    : 31,
        },
        'Simple': {
            'bar'               : '─',
            'border_left'       : ' ┊',
            'border_right'      : '┊ ',
            'progress_empty'    : '▭',
            'progress_full'     : '■',
            'ballot_check'      : ' ✔ ',
            'ballot_empty'      : ' ❏ ',
            'spacer'            : '  ',
            'ellipsis'          : '…',
            'selected_bold'     : True,
            'selected_reverse'  : False,
            'colored_bar'       : False,
            'dim_empty_bar'     : False,
            'reserved_space'    : 31,
        },
    }
    
    themes = list(theme.keys())

    def __init__(self, theme):
        if theme in Theme.themes:
            self.theme = theme
        else:
            raise ValueError(f"Unknown theme '{theme}'")

    def get(self, key):
        if self.theme not in Theme.themes:
            return '?'
        if key not in Theme.theme[self.theme]:
            return '?'
        return Theme.theme[self.theme][key]

    def next_theme(self):
        current_index = Theme.themes.index(self.theme)
        next_index = (current_index + 1) % len(Theme.themes)
        self.theme = Theme.themes[next_index]
        