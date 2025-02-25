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
This script allows replacing content between specified delimiters in a text file.

Functions:
    - parse_arguments: Parses command-line arguments.
    - read_file: Reads the contents of a file.
    - write_file: Writes content to a file.
    - replace_content: Replaces text between specified delimiters.
    - replace_params: Reads input, replaces content, and writes output.
    - main: Executes the script logic based on command-line arguments.
"""

import os
import re
import sys
import argparse

import odatix.lib.printc as printc

script_name = os.path.basename(__file__)

def add_arguments(parser):
    """Add command-line arguments."""
    parser.add_argument("-s", "--startdel", dest="start_delimiter", required=True, help="Start delimiter")
    parser.add_argument("-S", "--stopdel", dest="stop_delimiter", required=True, help="Stop delimiter")
    parser.add_argument("-i", "--input", dest="base_text_file", required=True, help="Input base text file")
    parser.add_argument("-o", "--output", dest="output_file", required=True, help="Output text file")
    parser.add_argument("-r", "--replace", dest="replacement_text_file", required=True, help="Replacement text file")
    parser.add_argument("-a", "--all", dest="replace_all_occurrences", action="store_true", help="Replace all occurrences")

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Replace content between delimiters in a text file.")
    add_arguments(parser)
    return parser.parse_args()

def read_file(file_path):
    """Reads the contents of a text file and returns it as a string."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except Exception:
        printc.error("Could not open input file \"" + file_path + "\"", script_name)
        sys.exit(1)

def write_file(file_path, content):
    """Writes content to a specified text file."""
    try:
        with open(file_path, 'w') as file:
            file.write(content)
    except Exception as e:
        printc.error("Could not write output file \"" + file_path + "\": " + str(e), script_name)
        sys.exit(1)

def replace_content(base_text, replacement_text, start_delim, stop_delim, replace_all_occurrences):
    """Replaces text between specified delimiters in the base text with the replacement text."""
    pattern = re.escape(start_delim) + '.*?' + re.escape(stop_delim)

    match_found = re.search(pattern, base_text, flags=re.DOTALL) is not None
    
    if replace_all_occurrences:
        new_text = re.sub(pattern, start_delim + replacement_text + stop_delim, base_text, flags=re.DOTALL)
    else:
        new_text = re.sub(pattern, start_delim + replacement_text + stop_delim, base_text, count=1, flags=re.DOTALL)
    return new_text, match_found

def replace_params(base_text_file, replacement_text_file, output_file, start_delimiter, stop_delimiter, replace_all_occurrences=False, silent=False):
    """
    Reads the base file, replaces the text between delimiters by the text from the replacement file, and writes the updated content to the output file.

    Args:
        base_text_file (str): Path to the input text file where replacements will be made.
        replacement_text_file (str): Path to the file containing the replacement text.
        output_file (str): Path to the output text file where the modified content will be saved.
        start_delimiter (str): The starting delimiter marking the beginning of the replaceable section.
        stop_delimiter (str): The ending delimiter marking the end of the replaceable section.
        replace_all_occurrences (bool, optional): If True, replaces all occurrences of the pattern in the text. Defaults to False (only replaces the first occurrence).
        silent (bool, optional): If True, suppresses output messages. Defaults to False.
    """    
    # Read the contents of base and replacement files
    base_text = read_file(base_text_file)
    replacement_text = read_file(replacement_text_file)

    # Replace content between delimiters
    new_text, match_found = replace_content(base_text, replacement_text, start_delimiter, stop_delimiter, replace_all_occurrences)

    # Write the new content to the output file
    write_file(output_file, new_text)

    if not match_found:
        printc.warning("Could not find pattern ", script_name=script_name, end="")
        printc.red(start_delimiter, end="")
        printc.grey("[…]", end="")
        printc.red(stop_delimiter, end="")
        printc.yellow("\" in \"" + base_text_file + "\"")

    if not silent and match_found:
        if new_text != base_text:
            printc.say("Content replaced successfully, output saved to \"" + output_file + "\"", script_name)
        else:
            printc.say("Nothing to be done, input copied to \"" + output_file + "\"", script_name)

    return match_found

######################################
# Main
######################################

def main(args):
    """Main function to handle argument parsing and execution of text replacement."""
    replace_params(args.base_text_file, args.replacement_text_file, args.output_file, args.start_delimiter, args.stop_delimiter, args.replace_all_occurrences)

if __name__ == "__main__":
    args = parse_arguments()
    main(args)
