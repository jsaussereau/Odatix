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

_icons = {
    "save": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M19,0H1C0.448,0,0,0.448,0,1v22c0,0.552,0.448,1,1,1h22c0.552,0,1-0.448,1-1V5L19,0z M6,3c0-0.552,0.448-1,1-1h10 c0.552,0,1,0.448,1,1v6c0,0.552-0.448,1-1,1H7c-0.552,0-1-0.448-1-1V3z M20,22H4v-7c0-0.552,0.448-1,1-1h14c0.552,0,1,0.448,1,1V22 z'), 
            Path(d='M16,9h-4V3h4V9z')
        ], 
        enableBackground='new 0 0 24 24', 
        fill=color,
        version='1.1', 
        viewBox='0 0 24 24', 
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"scale": "0.8", "width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-9px"},
    ),

    "duplicate": lambda color, width, height, className, id: Svg(
        children=[
            Path(id='path1', d='M24,7H6V6c0-1.105,0.895-2,2-2h19c1.105,0,2,0.895,2,2v14c0,1.105-0.895,2-2,2h-1V9C26,7.895,25.105,7,24,7z', style={'fill': '{color}', 'fillOpacity': '1'}), 
            Path(id='path2', d='M22,9H3c-1.105,0-2,0.895-2,2v13c0,1.105,0.895,2,2,2h19c1.105,0,2-0.895,2-2V11C24,9.895,23.105,9,22,9z M16,19h-3v3  c0,0.552-0.448,1-1,1h0c-0.552,0-1-0.448-1-1v-3H8c-0.552,0-1-0.448-1-1v0c0-0.552,0.448-1,1-1h3v-3c0-0.552,0.448-1,1-1h0  c0.552,0,1,0.448,1,1v3h3c0.552,0,1,0.448,1,1v0C17,18.552,16.552,19,16,19z', style={'fill': '{color}', 'fillOpacity': '1'})
        ], 
        version='1.1', 
        viewBox='0 0 30 30', 
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={'enableBackground': 'new 0 0 30 30', "width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),

    "delete": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M 14.984375 2.4863281 A 1.0001 1.0001 0 0 0 14 3.5 L 14 4 L 8.5 4 A 1.0001 1.0001 0 0 0 7.4863281 5 L 6 5 A 1.0001 1.0001 0 1 0 6 7 L 24 7 A 1.0001 1.0001 0 1 0 24 5 L 22.513672 5 A 1.0001 1.0001 0 0 0 21.5 4 L 16 4 L 16 3.5 A 1.0001 1.0001 0 0 0 14.984375 2.4863281 z M 6 9 L 7.7929688 24.234375 C 7.9109687 25.241375 8.7633438 26 9.7773438 26 L 20.222656 26 C 21.236656 26 22.088031 25.241375 22.207031 24.234375 L 24 9 L 6 9 z')
        ], 
        fill=color, 
        viewBox='0 0 30 30', 
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-11px"},
    ),

    "generate": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M454.321,219.727l-38.766-51.947l20.815-61.385c2.046-6.032,0.489-12.704-4.015-17.208 c-4.504-4.504-11.175-6.061-17.208-4.015l-61.384,20.815l-51.951-38.766c-5.103-3.809-11.929-4.392-17.605-1.499 c-5.676,2.893-9.217,8.755-9.136,15.125l0.829,64.815l-52.923,37.426c-5.201,3.678-7.863,9.989-6.867,16.282 c0.996,6.291,5.479,11.471,11.561,13.363l43.844,13.63L14.443,483.432c-6.535,6.534-6.535,17.131,0,23.666s17.131,6.535,23.666,0 l257.073-257.072l13.629,43.843c2.172,6.986,8.638,11.768,15.984,11.768c5.375,0,10.494-2.595,13.66-7.072l37.426-52.923 l64.815,0.828c6.322,0.051,12.233-3.462,15.125-9.136S458.131,224.833,454.321,219.727z'), 
            Polygon(points='173.373,67.274 160.014,42.848 146.656,67.274 122.23,80.632 146.656,93.992 160.014,118.417 173.373,93.992 197.799,80.632 '), 
            Polygon(points='362.946,384.489 352.14,364.731 341.335,384.489 321.577,395.294 341.335,406.1 352.14,425.856 362.946,406.1 382.703,395.294 '), 
            Polygon(points='378.142,19.757 367.337,0 356.531,19.757 336.774,30.563 356.531,41.369 367.337,61.126 378.142,41.369 397.9,30.563 '), 
            Polygon(points='490.635,142.513 484.167,130.689 477.701,142.513 465.876,148.979 477.701,155.446 484.167,167.27 490.635,155.446 502.458,148.979 '), 
            Polygon(points='492.626,294.117 465.876,301.951 439.128,294.117 446.962,320.865 439.128,347.615 465.876,339.781 492.626,347.615 484.791,320.865 ')
        ], 
        fill=color, 
        stroke=color, 
        version='1.1', 
        viewBox='0 0 512 512', 
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),

    "edit": lambda color, width, height, className, id: Svg(
        children=[
            Path(clipRule='evenodd', d='m 1.9999992,4.5524381 c 0,-0.55228 0.44772,-1 1,-1 h 5 c 0.5523,0 1,-0.44771 1,-1 0,-0.55228 -0.4477,-1 -1,-1 h -5 c -1.65685,0 -3.00000001559839,1.34315 -3.00000001559839,3 V 15.552398 c 0,1.6569 1.34315001559839,3 3.00000001559839,3 H 13.999999 c 1.6569,0 3,-1.3431 3,-3 v -5 c 0,-0.5522 -0.4477,-0.9999999 -1,-0.9999999 -0.5523,0 -1,0.4477999 -1,0.9999999 v 5 c 0,0.5523 -0.4477,1 -1,1 H 2.9999992 c -0.55228,0 -1,-0.4477 -1,-1 z'), 
            Path(clipRule='evenodd', d='M 16.198836,5.5077741 17.61855,4.0880593 c 0.431053,-0.4310131 0.64654,-0.6465157 0.761714,-0.878998 0.219202,-0.442317 0.219202,-0.9616275 0,-1.4039525 C 18.26509,1.5726345 18.049603,1.357124 17.61855,0.92611089 c -0.430973,-0.4310131 -0.646539,-0.6465157 -0.879021,-0.7617213 -0.442278,-0.2191862 -0.961628,-0.2191862 -1.403905,0 -0.232483,0.1152056 -0.447969,0.3307082 -0.879022,0.7617213 l -1.43758,1.43762731 c 0.761872,1.304778 1.857645,2.3921404 3.179814,3.1440359 z M 11.869259,3.51347 6.4382172,8.9444951 c -0.336005,0.336036 -0.504007,0.504015 -0.614469,0.710411 -0.110455,0.206396 -0.157054,0.4393529 -0.250245,0.9053449 l -0.442233,2.287923 c -0.04,0.206946 0.03492,0.327339 0.106275,0.40538 0.06958,0.07608 0.219605,0.185561 0.40692,0.167654 l 2.339946,-0.450039 c 0.46596,-0.0932 0.698933,-0.139759 0.905329,-0.250269 0.206396,-0.110431 0.374398,-0.278409 0.710403,-0.614445 L 15.046124,6.6604621 C 13.764214,5.8576437 12.679903,4.7807473 11.869259,3.51347 Z')
        ],
        fill=color, 
        version='1.1', 
        viewBox='0 0 18.544666 18.552398',
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"scale": "0.9", "width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),

    "more": lambda color, width, height, className, id: Svg(
        children=[
            Path(clipRule='evenodd', d='M7.293 9.293a1 1 0 0 1 1.414 0L12 12.586l3.293-3.293a1 1 0 1 1 1.414 1.414l-4 4a1 1 0 0 1-1.414 0l-4-4a1 1 0 0 1 0-1.414Z')
        ],
        fill=color, 
        viewBox='0 0 24 24', 
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"scale": "1.1", "width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),

    "clean": lambda color, width, height, className, id: Svg(
        children=[
            Rect(id='rect243', height='15.193717', rx='1.9656206', ry='1.9656206', width='6.0562363', x='18.168709', y='5.106328'),
            Rect(id='rect245', height='6.5874848', rx='1.96562', ry='1.96562', width='22.2062', x='10.093726', y='21.937542'), 
            Path(id='path247', d='m 10.09375,29.9375 c -0.1612638,8.271839 -2.8773742,13.350762 -5.2070312,18.912109 2.9125172,1.059983 5.7970882,1.76223 8.6582032,2.179688 L 16.363281,41.0625 16.564453,51.361328 C 23.655756,51.906261 30.612187,50.775071 37.505859,48.849609 33.592214,43.215682 32.560187,36.695808 32.300781,29.9375 Z'),
            Rect(id='rect253', height='4.8960323', width='6.0562363', x='18.168709', y='15.404013')
        ],
        fill=color, 
        version='1.1', 
        viewBox='0 0 50 50', 
        transform='rotate(45 0 0)',
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-5px"},
    ),
    
    "gear": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M511.956,308.448L512,206.866l-65.97-7.239c-3.584-12.101-8.323-23.822-14.165-35.037l42.198-52.531l-71.812-71.845    L350.48,81.766c-11.115-6.041-22.751-10.987-34.783-14.783l-7.318-66.961H206.797l-7.21,65.973    c-11.988,3.556-23.608,8.248-34.726,14.021l-52.475-42.265l-71.938,71.72l41.484,51.825c-6.058,11.109-11.02,22.741-14.831,34.763    L0.134,203.29L0,304.872l65.963,7.295c3.573,12.101,8.301,23.826,14.135,35.049L37.856,399.71l71.751,71.907l51.807-41.507    c11.112,6.052,22.744,11.008,34.769,14.815l7.261,66.966l101.582,0.088l7.266-65.967c12.1-3.578,23.826-8.313,35.043-14.149    l52.513,42.22l71.876-71.783l-41.529-51.788c6.046-11.112,10.997-22.747,14.8-34.777L511.956,308.448z M256.021,347.705    c-50.659,0-91.727-41.068-91.727-91.727s41.068-91.727,91.727-91.727c50.659,0,91.727,41.068,91.727,91.727    S306.681,347.705,256.021,347.705z')
        ], 
        fill=color, 
        version='1.1', 
        viewBox='0 0 512 512',
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"scale": "0.85", "width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),

    "back": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M464.344,207.418l0.768,0.168H135.888l103.496-103.724c5.068-5.064,7.848-11.924,7.848-19.124    c0-7.2-2.78-14.012-7.848-19.088L223.28,49.538c-5.064-5.064-11.812-7.864-19.008-7.864c-7.2,0-13.952,2.78-19.016,7.844    L7.844,226.914C2.76,231.998-0.02,238.77,0,245.974c-0.02,7.244,2.76,14.02,7.844,19.096l177.412,177.412    c5.064,5.06,11.812,7.844,19.016,7.844c7.196,0,13.944-2.788,19.008-7.844l16.104-16.112c5.068-5.056,7.848-11.808,7.848-19.008    c0-7.196-2.78-13.592-7.848-18.652L134.72,284.406h329.992c14.828,0,27.288-12.78,27.288-27.6v-22.788    C492,219.198,479.172,207.418,464.344,207.418z')
        ],
        fill=color,
        version='1.1', 
        viewBox='0 0 492 492',
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-5px"},
    ),
    
    "check": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M34.459 1.375a2.999 2.999 0 0 0-4.149.884L13.5 28.17l-8.198-7.58a2.999 2.999 0 1 0-4.073 4.405l10.764 9.952s.309.266.452.359a2.999 2.999 0 0 0 4.15-.884L35.343 5.524a2.999 2.999 0 0 0-.884-4.149z')
        ], 
        fill=color,
        version='1.1', 
        viewBox='0 0 36 36', 
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),

    "tooltip": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm-.696-3.534c.63 0 1.332-.288 2.196-1.458l.911-1.22a.334.334 0 0 0-.074-.472.38.38 0 0 0-.505.06l-1.475 1.679a.241.241 0 0 1-.279.061.211.211 0 0 1-.12-.244l1.858-7.446a.499.499 0 0 0-.575-.613l-3.35.613a.35.35 0 0 0-.276.258l-.086.334a.25.25 0 0 0 .243.312h1.73l-1.476 5.922c-.054.234-.144.63-.144.918 0 .666.396 1.296 1.422 1.296zm1.83-10.536c.702 0 1.242-.414 1.386-1.044.036-.144.054-.306.054-.414 0-.504-.396-.972-1.134-.972-.702 0-1.242.414-1.386 1.044a1.868 1.868 0 0 0-.054.414c0 .504.396.972 1.134.972z')
        ], 
        fill=color,
        version='1.1', 
        viewBox='0 0 24 24', 
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),
    "reset": lambda color, width, height, className, id: Svg(
        children=[
            Path(d='M960 0v213.333c411.627 0 746.667 334.934 746.667 746.667S1371.627 1706.667 960 1706.667 213.333 1371.733 213.333 960c0-197.013 78.4-382.507 213.334-520.747v254.08H640V106.667H53.333V320h191.04C88.64 494.08 0 720.96 0 960c0 529.28 430.613 960 960 960s960-430.72 960-960S1489.387 0 960 0')
        ],  
        fill=color,
        version='1.1', 
        viewBox='0 0 1920 1920',
        width=width, 
        height=height, 
        className=className, 
        id=id,
        style={"scale": "0.85", "width": width, "height": height, "minWidth": width, "minHeight": height, "marginLeft": "-10px"},
    ),
}

def icon(name: str, color: str = "#fff", width: str = "24px", height: str = "24px", className: str = "", id: Union[str, dict]="") -> Svg:
    """
    Return an icon as a Dash SVG component.
    Args:
        name (str): Name of the icon.
        color (str, optional): Color of the icon.
    """
    svg_icon = _icons.get(name)

    if not svg_icon:
        return Svg(width=width, height=height) # Empty SVG

    return svg_icon(color, width, height, className, id)
