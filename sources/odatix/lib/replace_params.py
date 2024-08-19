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

import os
import re
import sys
import argparse

import odatix.lib.printc as printc

script_name = os.path.basename(__file__)

def read_file(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        return content
    except:
        printc.error("could not open input file \"" + file_path + "\"", script_name)
        sys.exit(1)

def write_file(file_path, content):
    try:
        with open(file_path, 'w') as file:
            file.write(content)
    except Exception as e:
        printc.error("could not write output file \"" + file_path + "\": " + str(e), script_name)
        sys.exit(1)

def replace_content(base_text, replacement_text, start_delim, stop_delim, replace_all_occurrences):
    pattern = re.escape(start_delim) + '.*?' + re.escape(stop_delim)

    match_found = re.search(pattern, base_text, flags=re.DOTALL) is not None
    
    if replace_all_occurrences:
        new_text = re.sub(pattern, start_delim + replacement_text + stop_delim, base_text, flags=re.DOTALL)
    else:
        new_text = re.sub(pattern, start_delim + replacement_text + stop_delim, base_text, count=1, flags=re.DOTALL)
    return new_text, match_found

def replace_params(base_text_file, replacement_text_file, output_file, start_delimiter, stop_delimiter, replace_all_occurrences=False, silent=False):
    # Read the contents of text files
    base_text = read_file(base_text_file)
    replacement_text = read_file(replacement_text_file)

    # Replace content between delimiters
    new_text, match_found = replace_content(base_text, replacement_text, start_delimiter, stop_delimiter, replace_all_occurrences)

    # Write the new content to the output file
    write_file(output_file, new_text)

    if not match_found:
        printc.warning("could not find pattern \"", script_name=script_name, end="")
        printc.red(start_delimiter, end="")
        printc.grey("[…]", end="")
        printc.red(stop_delimiter, end="")
        printc.yellow("\" in \"" + base_text_file + "\"")

    if not silent and match_found:
        if new_text != base_text:
            printc.say("content replaced successfully, output saved to \"" + output_file + "\"", script_name)
        else:
            printc.say("nothing to be done, input copied to \"" + output_file + "\"", script_name)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Replace content between delimiters in a text file.")
    parser.add_argument("-s", "--startdel", dest="start_delimiter", required=True, help="Start delimiter")
    parser.add_argument("-S", "--stopdel", dest="stop_delimiter", required=True, help="Stop delimiter")
    parser.add_argument("-i", "--input", dest="base_text_file", required=True, help="Input base text file")
    parser.add_argument("-o", "--output", dest="output_file", required=True, help="Output text file")
    parser.add_argument("-r", "--replace", dest="replacement_text_file", required=True, help="Replacement text file")
    parser.add_argument("-a", "--all", dest="replace_all_occurrences", action="store_true", help="Replace all occurrences")
    return parser.parse_args()


######################################
# Main
######################################

def main():
    args = parse_arguments()
    replace_params(args.base_text_file, args.replacement_text_file, args.output_file, args.start_delimiter, args.stop_delimiter, args.replace_all_occurrences)

if __name__ == "__main__":
    main()