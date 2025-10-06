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
import re
import sys
import argparse
from dash_svg import Svg, Path, Circle, Rect, Ellipse, Line, Polyline, Polygon
from xml.etree import ElementTree
from typing import Dict

######################################
# SVG to Inline Dash SVG
######################################

def add_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("-i", "--input", default=None, help="input svg file")
    parser.add_argument("-o", "--output", default=None, help="input inline dash svg")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Clean up current directory")
    add_arguments(parser)
    return parser.parse_args()

def kebab_to_camel(s: str) -> str:
    """
    Convert a kebab-case string to camelCase.
    Args:
        s (str): The input kebab-case string.
    """
    return re.sub(r'-([a-z])', lambda m: m.group(1).upper(), s)

def parse_style(style_str: str) -> Dict[str, str]:
    """
    Convert a CSS style string to a dictionary.
    Args:
        style_str (str): The CSS style string (e.g., "fill: #000; stroke: #fff;").
    Returns:
        dict: A dictionary representation of the styles (e.g., {"fill": "#000", "stroke": "#fff"}).
    """
    style_dict = {}
    for item in style_str.split(';'):
        if ':' in item:
            k, v = item.split(':', 1)
            k = kebab_to_camel(k.strip())
            style_dict[k] = v.strip()
    return style_dict

def normalize_attrib_keys(attrib: Dict[str, str]) -> Dict[str, str]:
    """
    Normalize SVG attribute names for Dash:
    - kebab-case to camelCase (e.g. clip-rule -> clipRule)
    - class -> className
    - keep data-* and aria-* as-is
    - strip namespaces
    """
    norm: Dict[str, str] = {}
    for k, v in attrib.items():
        # drop namespace prefix if present
        if "}" in k:
            k = k.split("}", 1)[1]
        # keep data-* / aria-* unchanged (Dash supports them)
        if k.startswith("data-") or k.startswith("aria-"):
            norm[k] = v
            continue
        if k == "class":
            norm["className"] = v
            continue
        norm[kebab_to_camel(k)] = v
    return norm

def svg_to_dashsvg(svg_file: str) -> Svg:
    """
    Convert an SVG file to a Dash SVG component.
    Args:
        svg_file (str): Path to the source SVG file.
    """
    tree = ElementTree.parse(svg_file)
    root = tree.getroot()
    children = []
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        attrib = normalize_attrib_keys(dict(elem.attrib))   
        if 'style' in attrib and isinstance(attrib['style'], str):
            attrib['style'] = parse_style(attrib['style'])
        if tag.endswith('path'):
            children.append(Path(**attrib))
        elif tag.endswith('polygon'):
            children.append(Polygon(**attrib))
        elif tag.endswith('circle'):
            children.append(Circle(**attrib))
        elif tag.endswith('rect'):
            children.append(Rect(**attrib))
        elif tag.endswith('ellipse'):
            children.append(Ellipse(**attrib))
        elif tag.endswith('line'):
            children.append(Line(**attrib))
        elif tag.endswith('polyline'):
            children.append(Polyline(**attrib))
    svg_attrs = {}
    for k, v in root.attrib.items():
        if k.startswith('{'):
            continue
        key = k.split('}')[-1] if '}' in k else k
        key = kebab_to_camel(key)
        if key == "style":
            svg_attrs[key] = parse_style(v)
            pass
        else:
            svg_attrs[key] = v
    return Svg(children, **svg_attrs)

######################################
# Main
######################################

if __name__ == "__main__":
    args = parse_arguments()
    if args.input is None:
        print("Please provide an input svg file with -i/--input")
        sys.exit(1)
    code = svg_to_dashsvg(args.input)
    if args.output is None:
        print(code)
    else:
        with open(args.output, "w") as f:
            f.write(code)
