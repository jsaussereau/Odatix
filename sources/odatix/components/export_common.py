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
Shared helpers for the result-export components (synthesis and workflow).

Both odatix.components.export_results and odatix.components.export_workflow_results
extract metric values out of a run directory (regex/csv/yaml/json/xml files),
turn strings into numbers, evaluate "operation" metrics, and merge into an
existing results file. Those low-level building blocks live here so the logic is
defined once.
"""

import os
import re
import csv
import json
import yaml
import xml.etree.ElementTree as ET

import odatix.lib.printc as printc
import odatix.lib.results_schema as results_schema

script_name = os.path.basename(__file__)


######################################
# File value extraction
######################################

def parse_regex(file, pattern, group_id, error_if_missing=True, error_prefix=""):
    """Return the first regex match group in a file, or None."""
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, "r") as f:
        try:
            content = f.read()
            match = re.search(pattern, content)
            if match:
                return match.group(group_id)
        except Exception as e:
            printc.error(error_prefix + 'Could not get value from regex "' + pattern + '" in file "' + file + '": ' + str(e), script_name=script_name)
            return None

    if error_if_missing:
        printc.error(error_prefix + 'No match for regex "' + pattern + '" in file "' + file + '"', script_name=script_name)
    return None


def parse_regex_all(file, pattern, group_id, error_if_missing=True, error_prefix=""):
    """Like parse_regex, but return the list of every match (one per record row)."""
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, "r") as f:
        try:
            content = f.read()
            values = [match.group(group_id) for match in re.finditer(pattern, content)]
        except Exception as e:
            printc.error(error_prefix + 'Could not get values from regex "' + pattern + '" in file "' + file + '": ' + str(e), script_name=script_name)
            return None

    if not values and error_if_missing:
        printc.error(error_prefix + 'No match for regex "' + pattern + '" in file "' + file + '"', script_name=script_name)
    return values


def parse_csv(file, key, error_if_missing=True, error_prefix=""):
    """Return the first row's value for `key` in a CSV file, or None."""
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, mode="r") as csv_file:
        try:
            reader = csv.DictReader(csv_file, skipinitialspace=True)
            for row in reader:
                if key in row:
                    return row[key]
            if error_if_missing:
                printc.error(error_prefix + 'Could not find key "' + key + '" in csv "' + file + '"', script_name=script_name)
        except csv.Error as e:
            printc.error(error_prefix + 'An error occurred while reading csv file "' + file + '": ' + str(e), script_name=script_name)
            return None

    return None


def parse_csv_all(file, key, error_if_missing=True, error_prefix=""):
    """Like parse_csv, but return the list of every row's value for `key`."""
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    values = []
    with open(file, mode="r") as csv_file:
        try:
            reader = csv.DictReader(csv_file, skipinitialspace=True)
            for row in reader:
                if key in row:
                    values.append(row[key])
        except csv.Error as e:
            printc.error(error_prefix + 'An error occurred while reading csv file "' + file + '": ' + str(e), script_name=script_name)
            return None

    if not values and error_if_missing:
        printc.error(error_prefix + 'Could not find key "' + key + '" in csv "' + file + '"', script_name=script_name)
    return values


def parse_yaml(file, key=None, error_if_missing=True, error_prefix=""):
    """Return a YAML file's content, or the value for `key` (None if missing)."""
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, "r") as yaml_file:
        try:
            data = yaml.safe_load(yaml_file)
        except yaml.YAMLError as e:
            printc.error(f'{error_prefix}Could not parse yaml file "{file}": {str(e)}', script_name=script_name)
            return None

    if key is None:
        return data
    if not isinstance(data, dict):
        return None
    value = data.get(key, None)
    if value is None and error_if_missing:
        printc.error(error_prefix + 'Could not find key "' + key + '" in yaml "' + file + '"', script_name=script_name)
    return value


def parse_json(file, key=None, error_if_missing=True, error_prefix=""):
    """Return a JSON file's content, or the value for `key` (None if missing)."""
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, "r") as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError as e:
            printc.error(f'{error_prefix}Could not parse json file "{file}": {str(e)}', script_name=script_name)
            return None

    if key is None:
        return data
    if not isinstance(data, dict):
        if error_if_missing:
            printc.error(error_prefix + 'JSON file "' + file + '" does not contain a dictionary at top level', script_name=script_name)
        return None
    value = data.get(key, None)
    if value is None and error_if_missing:
        printc.error(error_prefix + 'Could not find key "' + key + '" in json "' + file + '"', script_name=script_name)
    return value


def _split_xml_key(key):
    """
    Split an XML key into an (element path, attribute) pair. The optional
    attribute is given with a trailing "@name" (e.g. "results/timing@value").
    An empty path means the document root; a None attribute means the element
    text.
    """
    if key is None:
        return None, None
    if "@" in key:
        path, _, attribute = key.rpartition("@")
        return (path or None), (attribute or None)
    return key, None


def _xml_element_value(element, attribute):
    """Return an element's attribute value, or its (stripped) text."""
    if element is None:
        return None
    if attribute:
        return element.get(attribute)
    text = element.text
    return text.strip() if isinstance(text, str) else text


def parse_xml(file, key=None, error_if_missing=True, error_prefix=""):
    """
    Return a value from an XML file. `key` is an ElementTree path (a subset of
    XPath) locating an element relative to the root, with an optional trailing
    "@attribute" to read an attribute instead of the element text. When `key`
    is None/empty the root element is used.
    """
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    try:
        root = ET.parse(file).getroot()
    except ET.ParseError as e:
        printc.error(f'{error_prefix}Could not parse xml file "{file}": {str(e)}', script_name=script_name)
        return None

    path, attribute = _split_xml_key(key)
    element = root if not path else root.find(path)
    if element is None:
        if error_if_missing:
            printc.error(error_prefix + 'Could not find element "' + str(key) + '" in xml "' + file + '"', script_name=script_name)
        return None

    value = _xml_element_value(element, attribute)
    if value is None and error_if_missing:
        printc.error(error_prefix + 'No value for element "' + str(key) + '" in xml "' + file + '"', script_name=script_name)
    return value


def parse_xml_all(file, key, error_if_missing=True, error_prefix=""):
    """Like parse_xml, but return the list of every matching element's value."""
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    try:
        root = ET.parse(file).getroot()
    except ET.ParseError as e:
        printc.error(f'{error_prefix}Could not parse xml file "{file}": {str(e)}', script_name=script_name)
        return None

    path, attribute = _split_xml_key(key)
    elements = [root] if not path else root.findall(path)
    values = [_xml_element_value(element, attribute) for element in elements]
    values = [value for value in values if value is not None]

    if not values and error_if_missing:
        printc.error(error_prefix + 'Could not find element "' + str(key) + '" in xml "' + file + '"', script_name=script_name)
    return values


######################################
# Value transforms
######################################

def convert_to_numeric(data):
    """Convert a numeric-looking value to int/float, otherwise return it as-is."""
    if isinstance(data, (int, float)):
        return data
    try:
        if "." in str(data):
            return float(data)
        return int(data)
    except Exception:
        return data


def calculate_operation(op_str, results, error_if_missing=True, error_prefix=""):
    """Evaluate an "operation" metric expression against already-extracted values."""
    try:
        local_vars = {k: v for k, v in results.items() if v is not None}
        return eval(op_str, {}, local_vars)
    except (NameError, SyntaxError, TypeError, ZeroDivisionError) as e:
        if error_if_missing:
            printc.error(error_prefix + 'Failed to evaluate operation "' + op_str + '": ' + str(e), script_name)
        return None


######################################
# Existing results file
######################################

def load_existing_results_file(output_file):
    """
    Load an existing results file (any supported format version) as
    (units, records). Older formats are auto-converted to v2 records, so the
    next write upgrades the file in place. Missing/unparsable files start empty.
    """
    if not os.path.isfile(output_file):
        return {}, []

    try:
        results_file = results_schema.load_results_file(output_file)
    except Exception:
        printc.warning('Could not parse existing results file "' + output_file + '", starting over', script_name=script_name)
        return {}, []

    return results_file.units, results_file.records
