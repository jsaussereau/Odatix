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

import urllib.parse
import re
from dash import html

def get_key_from_url(url, key):
    """
    Extract the value of a specific key from a URL query string.
    """
    if not url:
        return None
    params = urllib.parse.parse_qs(url.lstrip("?"))
    return params.get(key, [None])[0]

_ANSI_PATTERN = re.compile(r"[\x1b\033]\[[0-9;]*m")

_ANSI_COLORS = {
    30: "var(--terminal-black)",
    31: "var(--terminal-red)",
    32: "var(--terminal-green)",
    33: "var(--terminal-yellow)",
    34: "var(--terminal-blue)",
    35: "var(--terminal-magenta)",
    36: "var(--terminal-cyan)",
    37: "var(--terminal-white)",
    90: "var(--terminal-bright-black)",
    91: "var(--terminal-bright-red)",
    92: "var(--terminal-bright-green)",
    93: "var(--terminal-bright-yellow)",
    94: "var(--terminal-bright-blue)",
    95: "var(--terminal-bright-magenta)",
    96: "var(--terminal-bright-cyan)",
    97: "var(--terminal-bright-white)",
}

_ANSI_BG_COLORS = {
    40: "var(--terminal-black)",
    41: "var(--terminal-red)",
    42: "var(--terminal-green)",
    43: "var(--terminal-yellow)",
    44: "var(--terminal-blue)",
    45: "var(--terminal-magenta)",
    46: "var(--terminal-cyan)",
    47: "var(--terminal-white)",
    100: "var(--terminal-bright-black)",
    101: "var(--terminal-bright-red)",
    102: "var(--terminal-bright-green)",
    103: "var(--terminal-bright-yellow)",
    104: "var(--terminal-bright-blue)",
    105: "var(--terminal-bright-magenta)",
    106: "var(--terminal-bright-cyan)",
    107: "var(--terminal-bright-white)",
}

def ansi_to_html_spans(text: str):
    """
    Convert ANSI-colored terminal output into a list of colored spans.
    Supports standard color codes like ESC[31m and reset ESC[0m.
    """
    if text is None:
        text = ""

    spans = []
    pos = 0
    style = {}
    last_style = None

    def _push_chunk(chunk: str, chunk_style: dict):
        nonlocal spans, last_style
        if chunk == "":
            return
        if spans and last_style == chunk_style:
            spans[-1].children += chunk
            return
        spans.append(html.Span(chunk, style=chunk_style or None))
        last_style = dict(chunk_style) if chunk_style else {}

    for match in _ANSI_PATTERN.finditer(text):
        if match.start() > pos:
            _push_chunk(text[pos:match.start()], style)

        codes = match.group()[2:-1]
        if codes == "":
            codes_list = [0]
        else:
            try:
                codes_list = [int(c) for c in codes.split(";") if c != ""]
            except Exception:
                codes_list = []

        if not codes_list:
            pos = match.end()
            continue

        for code in codes_list:
            if code == 0:
                style = {}
            elif code == 1:
                style = {**style, "fontWeight": "bold"}
            elif code in _ANSI_COLORS:
                style = {**style, "color": _ANSI_COLORS[code]}
            elif code in _ANSI_BG_COLORS:
                style = {**style, "backgroundColor": _ANSI_BG_COLORS[code]}
            elif code == 39:
                if "color" in style:
                    style = {k: v for k, v in style.items() if k != "color"}
            elif code == 49:
                if "backgroundColor" in style:
                    style = {k: v for k, v in style.items() if k != "backgroundColor"}

        pos = match.end()

    if pos < len(text):
        _push_chunk(text[pos:], style)

    return spans

