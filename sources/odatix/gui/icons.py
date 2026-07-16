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

from dash_svg import Svg, Path, Circle, Rect, Ellipse, Line, Polyline, Polygon
from typing import Union

######################################
# Icon Definitions
######################################
#
# Small line-art UI glyphs, drawn in the clean Odatix Explorer / card
# pictogram style: single-color outlines on a shared 24x24 grid, stroked with
# `currentColor`. The color is driven by the ".icon <color>" CSS classes and
# the button/tooltip context (see style.css, which sets `color`, not `fill`);
# alignment/centering is handled by the container (e.g. ".icon-button").


def _line_icon(children, width, height, className, id, view_box="0 0 24 24", style_extra=None):
    # stroke-width / linecap / linejoin are inherited SVG properties: the Svg
    # component does not accept them as props, so they are set (in camelCase)
    # through the CSS `style` and cascade to the child shapes.
    style = {
        "width": width,
        "height": height,
        "strokeWidth": "1.5",
        "strokeLinecap": "round",
        "strokeLinejoin": "round",
    }
    if style_extra:
        style.update(style_extra)
    return Svg(
        children,
        viewBox=view_box,
        width=width,
        height=height,
        fill="none",
        stroke="currentColor",
        className=className,
        id=id,
        style=style,
    )


_icons = {
    # Floppy disk
    "save": lambda color, width, height, className, offset, id: _line_icon([
        Path(d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"),
        Polyline(points="17 21 17 13 7 13 7 21"),
        Polyline(points="7 3 7 8 15 8"),
    ], width, height, className, id),

    # Two stacked cards + plus
    "duplicate": lambda color, width, height, className, offset, id: _line_icon([
        Rect(x="8", y="8", width="13", height="13", rx="2"),
        Path(d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"),
        Line(x1="14.5", y1="11.5", x2="14.5", y2="17.5"),
        Line(x1="11.5", y1="14.5", x2="17.5", y2="14.5"),
    ], width, height, className, id),

    # Trash can
    "delete": lambda color, width, height, className, offset, id: _line_icon([
        Polyline(points="3 6 5 6 21 6"),
        Path(d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"),
        Line(x1="10", y1="11", x2="10", y2="17"),
        Line(x1="14", y1="11", x2="14", y2="17"),
    ], width, height, className, id),

    # Magic wand + sparkles
    "generate": lambda color, width, height, className, offset, id: _line_icon([
        Path(d="M3 21 L13.75 10.5"),
        Path(d="M15.5 3.5 L17 7 L20.5 8.5 L17 10 L15.5 13.5 L14 10 L10.5 8.5 L14 7 Z"),
        Path(d="M6.5 3.4 v3.2 M4.9 5 h3.2"),
        Path(d="M19.5 13.7 v2.6 M18.2 15 h2.6"),
    ], width, height, className, id),

    # Pencil
    "edit": lambda color, width, height, className, offset, id: _line_icon([
        Path(d="M12 20h9"),
        Path(d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"),
    ], width, height, className, id),

    # Chevron down
    "more": lambda color, width, height, className, offset, id: _line_icon([
        Polyline(points="6 9 12 15 18 9"),
    ], width, height, className, id),

    # Broom
    "clean": lambda color, width, height, className, offset, id: _line_icon([
        Rect(x="10.7", y="2.2", width="2.6", height="7.3", rx="0.9"),
        Line(x1="10.7", y1="6.7", x2="13.3", y2="6.7"),
        Rect(x="7.2", y="9.5", width="9.6", height="3.4", rx="1.1"),
        Path(d="M7.6 12.9 c-0.07 3.5 -1.2 5.6 -2.2 8 1.25 0.45 2.5 0.75 3.7 0.93 L10.3 17.5 l0.09 4.4 c3 0.23 6 -0.25 9 -1.08 -1.7 -2.4 -2.1 -5.1 -2.2 -7.9 Z"),
    ], width, height, className, id),

    # Cog / settings
    "gear": lambda color, width, height, className, offset, id: _line_icon([
        Circle(cx="12", cy="12", r="3"),
        Path(d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"),
    ], width, height, className, id),

    # Arrow left
    "back": lambda color, width, height, className, offset, id: _line_icon([
        Line(x1="19", y1="12", x2="5", y2="12"),
        Polyline(points="12 19 5 12 12 5"),
    ], width, height, className, id),

    # Check mark
    "check": lambda color, width, height, className, offset, id: _line_icon([
        Polyline(points="20 6 9 17 4 12"),
    ], width, height, className, id),

    # Info circle
    "tooltip": lambda color, width, height, className, offset, id: _line_icon([
        Circle(cx="12", cy="12", r="10"),
        Line(x1="12", y1="16", x2="12", y2="11"),
        Line(x1="12", y1="8", x2="12.01", y2="8"),
    ], width, height, className, id),

    # Refresh arrow
    "reset": lambda color, width, height, className, offset, id: _line_icon([
        Polyline(points="23 4 23 10 17 10"),
        Path(d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"),
    ], width, height, className, id),

    # Play triangle
    "play": lambda color, width, height, className, offset, id: _line_icon([
        Polygon(points="6 4 20 12 6 20"),
    ], width, height, className, id),

    # Pause bars
    "pause": lambda color, width, height, className, offset, id: _line_icon([
        Rect(x="6.5", y="4", width="4", height="16", rx="1.5"),
        Rect(x="13.5", y="4", width="4", height="16", rx="1.5"),
    ], width, height, className, id),

    # Close cross
    "cross": lambda color, width, height, className, offset, id: _line_icon([
        Line(x1="18", y1="6", x2="6", y2="18"),
        Line(x1="6", y1="6", x2="18", y2="18"),
    ], width, height, className, id),
}

def icon(name: str, color: str = "#fff", width: str = "24px", height: str = "24px", className: str = "", offset: bool = False, id: Union[str, dict]="") -> Svg:
    """
    Return a small line-art UI glyph as a Dash SVG component. The glyph is
    stroked with `currentColor`; its color comes from the ".icon <color>" CSS
    classes or the button/tooltip context, not from the `color` argument.
    Args:
        name (str): Name of the icon.
    """
    svg_icon = _icons.get(name)

    if not svg_icon:
        return Svg(width=width, height=height) # Empty SVG

    return svg_icon(color, width, height, className, offset, id)


######################################
# Card Pictograms
######################################
#
# Larger line-art pictograms used on menu/card pages, in the clean Odatix
# Explorer style: a primary-colored line drawing (theme accent) with a few
# secondary strokes in the text color. Colors reference theme CSS variables
# directly, so pictograms follow the active theme.

_PRIMARY = "var(--theme-primary-color, #228BE6)"
_TEXT = "var(--theme-text-color, #24292e)"


def _picto(children, size, className="xp-card-pictogram"):
    return Svg(
        children,
        viewBox="0 0 48 48",
        width=size,
        height=size,
        fill="none",
        className=className,
        style={"width": size, "height": size},
    )


_pictograms = {
    # Workflows: connected task nodes
    "workflow": lambda size: _picto([
        Line(x1="14", y1="12", x2="30", y2="12", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5", strokeLinecap="round"),
        Line(x1="14", y1="24", x2="34", y2="24", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5", strokeLinecap="round"),
        Line(x1="14", y1="36", x2="26", y2="36", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5", strokeLinecap="round"),
        Circle(cx="8", cy="12", r="3.5", fill=_PRIMARY),
        Circle(cx="8", cy="24", r="3.5", fill=_PRIMARY),
        Circle(cx="8", cy="36", r="3.5", fill=_PRIMARY),
        Line(x1="8", y1="15.5", x2="8", y2="20.5", stroke=_PRIMARY, strokeWidth="2"),
        Line(x1="8", y1="27.5", x2="8", y2="32.5", stroke=_PRIMARY, strokeWidth="2"),
    ], size),
    # RTL architectures: chip
    "architecture": lambda size: _picto([
        Line(x1="19", y1="11", x2="19", y2="15", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="24", y1="11", x2="24", y2="15", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="29", y1="11", x2="29", y2="15", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="19", y1="33", x2="19", y2="37", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="24", y1="33", x2="24", y2="37", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="29", y1="33", x2="29", y2="37", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="11", y1="19", x2="15", y2="19", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="11", y1="24", x2="15", y2="24", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="11", y1="29", x2="15", y2="29", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="33", y1="19", x2="37", y2="19", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="33", y1="24", x2="37", y2="24", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Line(x1="33", y1="29", x2="37", y2="29", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.6", strokeLinecap="round"),
        Rect(x="15", y="15", width="18", height="18", rx="3", stroke=_PRIMARY, strokeWidth="2.5"),
        Rect(x="21", y="21", width="6", height="6", rx="1", fill=_PRIMARY),
    ], size),
    # Run jobs: play
    "run": lambda size: _picto([
        Circle(cx="24", cy="24", r="16", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.4"),
        Polygon(points="19,16 33,24 19,32", fill=_PRIMARY),
    ], size),
    # Monitor: activity pulse
    "monitor": lambda size: _picto([
        Rect(x="7", y="10", width="34", height="24", rx="3", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5"),
        Polyline(points="12,24 18,24 21,18 26,30 29,24 36,24", stroke=_PRIMARY, strokeWidth="2.5", fill="none", strokeLinecap="round", strokeLinejoin="round"),
        Line(x1="18", y1="40", x2="30", y2="40", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5", strokeLinecap="round"),
    ], size),
    # Explore results: chart + magnifier
    "explorer": lambda size: _picto([
        Rect(x="8", y="8", width="24", height="24", rx="3", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5"),
        Rect(x="13", y="20", width="3.5", height="7", rx="1", fill=_PRIMARY),
        Rect(x="19", y="15", width="3.5", height="12", rx="1", fill=_PRIMARY, fillOpacity="0.7"),
        Rect(x="25", y="18", width="3.5", height="9", rx="1", fill=_PRIMARY, fillOpacity="0.5"),
        Circle(cx="32", cy="32", r="6", stroke=_PRIMARY, strokeWidth="2.5"),
        Line(x1="36.5", y1="36.5", x2="41", y2="41", stroke=_PRIMARY, strokeWidth="2.5", strokeLinecap="round"),
    ], size),
    # Workspace / settings: gear
    "workspace": lambda size: _picto([
        # Same cog outline as the small "gear" icon, scaled onto the 48x48 grid
        Path(d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
             transform="translate(4.8 4.8) scale(1.6)",
             stroke=_PRIMARY, strokeWidth="1.6", strokeLinecap="round", strokeLinejoin="round"),
        Circle(cx="24", cy="24", r="7", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.55"),
    ], size),
    # Documentation: book
    "documentation": lambda size: _picto([
        Path(d="M10 12 a3 3 0 0 1 3-3 h9 v30 h-9 a3 3 0 0 0-3 3 z", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5", strokeLinejoin="round"),
        Path(d="M38 12 a3 3 0 0 0-3-3 h-9 v30 h9 a3 3 0 0 1 3 3 z", stroke=_PRIMARY, strokeWidth="2.5", strokeLinejoin="round"),
        Line(x1="29", y1="16", x2="34", y2="16", stroke=_PRIMARY, strokeWidth="2", strokeLinecap="round"),
        Line(x1="29", y1="22", x2="34", y2="22", stroke=_PRIMARY, strokeWidth="2", strokeLinecap="round"),
    ], size),
    # Generic EDA tool: chip + gear
    "eda_tool": lambda size: _picto([
        Rect(x="10", y="10", width="20", height="20", rx="3", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5"),
        Rect(x="16", y="16", width="8", height="8", rx="1", fill=_TEXT, fillOpacity="0.3"),
        Circle(cx="33", cy="33", r="5", stroke=_PRIMARY, strokeWidth="2.5"),
        Path(d="M33 25 v3 M33 38 v3 M25 33 h3 M38 33 h3", stroke=_PRIMARY, strokeWidth="2", strokeLinecap="round"),
    ], size),
    # Fmax synthesis: rising bars with peak
    "fmax": lambda size: _picto([
        Line(x1="9", y1="39", x2="39", y2="39", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.4", strokeLinecap="round"),
        Rect(x="12", y="28", width="5", height="11", rx="1", fill=_PRIMARY, fillOpacity="0.5"),
        Rect(x="21", y="20", width="5", height="19", rx="1", fill=_PRIMARY, fillOpacity="0.75"),
        Rect(x="30", y="12", width="5", height="27", rx="1", fill=_PRIMARY),
        Polyline(points="14,26 24,18 33,10", stroke=_TEXT, strokeWidth="2", fill="none", strokeOpacity="0.5", strokeLinecap="round", strokeLinejoin="round"),
    ], size),
    # Custom frequency: sine wave
    "custom_freq": lambda size: _picto([
        Path(d="M8 24 q5 -14 10 0 t10 0 t10 0", stroke=_PRIMARY, strokeWidth="2.5", fill="none", strokeLinecap="round"),
        Line(x1="8", y1="34", x2="40", y2="34", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.4", strokeLinecap="round"),
    ], size),
    # RTL analysis: document with lines + magnifier
    "analysis": lambda size: _picto([
        Path(d="M13 8 h14 l8 8 v24 a2 2 0 0 1-2 2 H13 a2 2 0 0 1-2-2 V10 a2 2 0 0 1 2-2 z", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5", strokeLinejoin="round"),
        Line(x1="16", y1="18", x2="24", y2="18", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.4", strokeLinecap="round"),
        Line(x1="16", y1="23", x2="28", y2="23", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.4", strokeLinecap="round"),
        Circle(cx="24", cy="30", r="5", stroke=_PRIMARY, strokeWidth="2.5"),
        Line(x1="27.8", y1="33.8", x2="32", y2="38", stroke=_PRIMARY, strokeWidth="2.5", strokeLinecap="round"),
    ], size),
    # Empty workspace: dashed folder / plus
    "workspace_empty": lambda size: _picto([
        Rect(x="9", y="13", width="30", height="24", rx="3", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.5", strokeDasharray="4 4"),
        Line(x1="24", y1="19", x2="24", y2="31", stroke=_PRIMARY, strokeWidth="2.5", strokeLinecap="round"),
        Line(x1="18", y1="25", x2="30", y2="25", stroke=_PRIMARY, strokeWidth="2.5", strokeLinecap="round"),
    ], size),
    # Workspace with examples: stacked cards
    "workspace_examples": lambda size: _picto([
        Rect(x="14", y="9", width="24", height="18", rx="3", stroke=_TEXT, strokeWidth="2", strokeOpacity="0.4"),
        Rect(x="10", y="15", width="24", height="18", rx="3", fill="var(--theme-element-background-color, #fff)", stroke=_PRIMARY, strokeWidth="2.5"),
        Line(x1="15", y1="21", x2="29", y2="21", stroke=_PRIMARY, strokeWidth="2", strokeOpacity="0.7", strokeLinecap="round"),
        Line(x1="15", y1="26", x2="24", y2="26", stroke=_PRIMARY, strokeWidth="2", strokeOpacity="0.7", strokeLinecap="round"),
    ], size),
}


def pictogram(name: str, size: str = "52px", className: str = "xp-card-pictogram") -> Svg:
    """
    Return a large line-art card pictogram (Odatix Explorer style) as a Dash
    SVG component, colored via theme CSS variables.
    Args:
        name (str): Name of the pictogram.
        size (str): Width/height of the square pictogram.
    """
    builder = _pictograms.get(name)
    if not builder:
        return Svg(viewBox="0 0 48 48", width=size, height=size, className=className, style={"width": size, "height": size})
    return builder(size)
