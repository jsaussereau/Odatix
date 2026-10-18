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
from typing import List

import odatix.lib.printc as printc
from odatix.lib.param_domain import ParamDomain

script_name = os.path.basename(__file__)

def add_arguments(parser):
    """Add command-line arguments."""
    parser.add_argument("-s", "--startdel", dest="start_delimiter", required=True, help="start delimiter (supports \\n, \\r, \\t escape sequences)")
    parser.add_argument("-S", "--stopdel", dest="stop_delimiter", required=True, help="stop delimiter (supports \\n, \\r, \\t escape sequences)")
    parser.add_argument("-i", "--input", dest="base_text_file", required=True, help="input base text file")
    parser.add_argument("-o", "--output", dest="output_file", required=True, help="output text file")
    parser.add_argument("-r", "--replace", dest="replacement_text_file", required=True, help="replacement text file")
    parser.add_argument("-a", "--all", dest="replace_all_occurrences", action="store_true", help="replace all occurrences")

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

def get_first_appearance(text, substring, start_line=1, start_char=1):
    """Returns the line and character number of the first appearance of a substring in the text."""
    lines = text.splitlines()
    for line_number, line in enumerate(lines[start_line-1:], start=start_line-1):
        start = start_char - 1 if line_number == start_line-1 else 0
        char_index = line.find(substring, start)
        if char_index != -1:
            return line_number + 1, char_index
    return -1, -1  # Not found

escape_sequences = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "\\": "\\"}

def unescape_delimiter(delimiter):
    """
    Converts escape sequences written literally in a delimiter into the characters they represent.

    This allows delimiters such as a single line break to be written as "\\n" in settings files
    or in the GUI, where an actual line break cannot easily be typed.
    Unknown sequences are kept as-is, so a lone backslash remains a lone backslash.

    Args:
        delimiter (str): The delimiter, possibly containing escape sequences.

    Returns:
        str: The delimiter with escape sequences replaced by the corresponding characters.
    """
    if not delimiter:
        return delimiter
    return re.sub(
        r"\\(.)",
        lambda match: escape_sequences.get(match.group(1), match.group(0)),
        delimiter,
    )

def keep_line_count(replaced, replacement_text):
    """
    `replacement_text`, followed by as many line breaks as it lacks to span the
    lines of the text it `replaced`. The lines after the block then keep their
    number, so a line an EDA tool or the analysis reports in the work copy is
    the same line in the source. A replacement longer than the block still
    shifts what follows it: nothing can be taken out of it.
    """
    missing = replaced.count("\n") - replacement_text.count("\n")
    return replacement_text + "\n" * missing if missing > 0 else replacement_text


def replace_content(base_text, replacement_text, start_delim, stop_delim, replace_all_occurrences, keep_lines=True):
    """
    Replaces text between specified delimiters in the base text with the
    replacement text. With `keep_lines`, a replacement shorter than the block
    is padded with line breaks (see :func:`keep_line_count`).
    """
    if start_delim == "" or stop_delim == "":
        return base_text, False

    start_delim = unescape_delimiter(start_delim)
    stop_delim = unescape_delimiter(stop_delim)

    pattern = re.escape(start_delim) + '.*?' + re.escape(stop_delim)

    match_found = re.search(pattern, base_text, flags=re.DOTALL) is not None

    # Use a function as replacement so backslashes in the replacement text are kept literal
    def replacement(match):
        text = replacement_text
        if keep_lines:
            text = keep_line_count(match.group(0)[len(start_delim):len(match.group(0)) - len(stop_delim)], text)
        return start_delim + text + stop_delim

    if replace_all_occurrences:
        new_text = re.sub(pattern, replacement, base_text, flags=re.DOTALL)
    else:
        new_text = re.sub(pattern, replacement, base_text, count=1, flags=re.DOTALL)
    return new_text, match_found

#: The line comment of each kind of file, by extension. A file Odatix does not
#: know is read as C-like: "#" would mistake a Verilog "#(" for a comment.
LINE_COMMENTS = {
    ".v": "//", ".vh": "//", ".sv": "//", ".svh": "//", ".c": "//", ".h": "//", ".cpp": "//",
    ".hpp": "//", ".cc": "//", ".scala": "//", ".sc": "//", ".java": "//", ".js": "//",
    ".vhd": "--", ".vhdl": "--",
    ".py": "#", ".tcl": "#", ".sh": "#", ".yml": "#", ".yaml": "#", ".mk": "#", ".cmake": "#",
    ".xdc": "#", ".sdc": "#",
}


def line_comment_of(file_name):
    """The line comment marker of a file, from its extension (C-like when unknown)."""
    base = os.path.basename(str(file_name or ""))
    if base in ("Makefile", "makefile", "CMakeLists.txt"):
        return "#"
    return LINE_COMMENTS.get(os.path.splitext(base)[1].lower(), "//")


def comment_after_start(base_text, start_delim, stop_delim, file_name=""):
    """
    The line comment the start delimiter ends inside of, or None.

    The text of a configuration is written right after the start delimiter. When
    that delimiter is part of a line comment ("  // <regs>") and does not end
    with a line break, the first line of the configuration lands in the comment:
    a parameter written there is silently commented out.

    Returns:
        str: the comment marker ("//", "--", "#"), or None when what follows the
        delimiter is code -- or when the delimiters match nothing.
    """
    if not start_delim or not stop_delim:
        return None
    start = unescape_delimiter(start_delim)
    stop = unescape_delimiter(stop_delim)
    if start.endswith("\n") or start.endswith("\r"):
        return None
    match = re.search(re.escape(start) + '.*?' + re.escape(stop), base_text or "", flags=re.DOTALL)
    if match is None:
        return None
    line_start = base_text.rfind("\n", 0, match.start()) + 1
    # The line the delimiter ends on, from its very beginning.
    line = (base_text[line_start:match.start()] + start).split("\n")[-1]
    marker = line_comment_of(file_name)
    return marker if marker in line else None


def first_line_of(replacement_text):
    """The first line of a configuration, stripped -- empty when it starts with a line break."""
    return re.split(r"\r?\n", replacement_text or "", maxsplit=1)[0].strip()


def commented_out_message(line, start_delim, file_name=""):
    """What to say about a configuration whose first line lands in a comment."""
    where = ' of "' + str(file_name) + '"' if file_name else ""
    return (
        'The start delimiter "' + str(start_delim) + '" ends inside a line comment' + where
        + ', and the configuration does not start with a line break: "' + line + '" ends up commented out. '
        + 'Start the configuration with an empty line, or end the start delimiter with "\\n".'
    )


def commented_out_warning(base_text, replacement_text, start_delim, stop_delim, file_name=""):
    """
    The warning to give when writing `replacement_text` between the delimiters
    would comment its first line out (see :func:`comment_after_start`), or None.
    """
    if comment_after_start(base_text, start_delim, stop_delim, file_name) is None:
        return None
    line = first_line_of(replacement_text)
    if not line:
        return None
    return commented_out_message(line, start_delim, file_name)


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
        printc.warning("Could not find pattern \"", script_name=script_name, end="")
        printc.red(start_delimiter, end="")
        printc.grey("[…]", end="")
        printc.red(stop_delimiter, end="")
        printc.yellow("\" in \"" + base_text_file + "\"")
    else:
        commented = commented_out_warning(
            base_text, replacement_text, start_delimiter, stop_delimiter, base_text_file,
        )
        if commented:
            printc.warning(commented, script_name)

    if not silent and match_found:
        if new_text != base_text:
            printc.say("Content replaced successfully, output saved to \"" + output_file + "\"", script_name)
        else:
            printc.say("Nothing to be done, input copied to \"" + output_file + "\"", script_name)

    return match_found

def replace_param_domain(param_domain: ParamDomain, design_path: str, silent: bool=False, debug: bool=False):
    """
    Replace parameters in a specific domain based on the provided ParamDomain object.

    Args:
        param_domain (ParamDomain): The ParamDomain object containing domain-specific information.
        design_path (str): The directory where the base file is located.
        silent (bool, optional): If True, suppresses output messages. Defaults to False.
        debug (bool, optional): If True, enables debug output. Defaults to False.
    """
    success = False
    if param_domain.use_parameters:
        param_target_file = os.path.join(design_path, param_domain.param_target_file)

        if debug: 
            printc.subheader("Replace parameters for \"" + param_domain.domain + "/" + param_domain.domain_value+ "\"")
        success = replace_params(
            base_text_file=param_target_file,
            replacement_text_file=param_domain.param_file,
            output_file=param_target_file,
            start_delimiter=param_domain.start_delimiter,
            stop_delimiter=param_domain.stop_delimiter,
            replace_all_occurrences=False,
            silent=False if debug else True,
        )
    return success

def replace_param_domains(param_domains: List[ParamDomain], design_path: str, timestamp=False, silent=False, debug=False):
    """
    Replace parameters for multiple ParamDomain objects and return a dictionary of domain values.

    Args:
        param_domains (List[ParamDomain]): A list of ParamDomain objects.
        design_path (str): The directory where the base file is located.
        timestamp (bool, optional): If True, includes a timestamp in the returned dictionary. Defaults to False.
        silent (bool, optional): If True, suppresses output messages. Defaults to False.
        debug (bool, optional): If True, enables debug output. Defaults to False.
    """
    domain_dict = {}
    if timestamp is not None:
        domain_dict["__timestamp__"] = timestamp 
    for param_domain in param_domains:
        success = replace_param_domain(param_domain, design_path, silent, debug)
        if success:
            domain_dict[param_domain.domain] = param_domain.domain_value
        if debug: 
            print()
    return domain_dict

######################################
# Main
######################################

def main(args):
    """Main function to handle argument parsing and execution of text replacement."""
    # Delimiters that match nothing leave the output a copy of the input: the
    # command did not do what it was asked.
    return replace_params(args.base_text_file, args.replacement_text_file, args.output_file, args.start_delimiter, args.stop_delimiter, args.replace_all_occurrences)

if __name__ == "__main__":
    args = parse_arguments()
    main(args)
