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
What Odatix tells a simulation about the design under test.

Every simulation job gets two files in its work directory, written once the
parameters are replaced (so they describe the RTL that is simulated):

  - "odatix_sim.yml": the sources of the design, by language and in compilation
    order, its top, its clock and reset, the testbench (top and files) and the
    value of each parameter domain;
  - "odatix_sim.f": the same sources as a plain filelist, design first, then
    the testbench, which most simulators read with "-f".

The same values are offered to the simulation's commands as placeholders
(${vhdl_files}, ${tb_top}, ...): see :func:`substitutions`.

Compilation order
-----------------
VHDL needs a package compiled before the units using it, and SystemVerilog a
package before the files importing it. The order is, by priority:

  1. a "filelist.f" at the root of the RTL directory, when there is one: its
     order is kept as written;
  2. otherwise, an order Odatix computes from the sources: what each file
     defines (entities, packages, contexts, configurations; SystemVerilog
     packages) and what it uses (``use work.pkg``, ``entity work.x``, the entity
     of an architecture, the package of a body; ``import pkg::*``, ``pkg::x``).
     Files that depend on nothing keep the order of the directory.

A simulator able to find the order itself (GHDL, with ``ghdl -i`` then
``ghdl -m``) does not need it, and a template can still recompile until
everything passes when the order computed here is wrong.

This module only uses the standard library and PyYAML: a generated RTL only
exists once its generation command has run, so the file is rewritten then, by
running this module as a script in the job's work directory (see
:func:`refresh_command`).
"""

import glob
import os
import re
import sys

import yaml

SIM_INFO_FILENAME = "odatix_sim.yml"
SIM_FILELIST_FILENAME = "odatix_sim.f"
# A filelist the design may hold at the root of its RTL directory, giving the
# compilation order itself.
USER_FILELIST_FILENAME = "filelist.f"
# Where a simulation keeps its testbench, when it does not name its files.
DEFAULT_TESTBENCH_DIR = "tb"

LANGUAGES = ("vhdl", "verilog", "sv")
LANGUAGE_EXTENSIONS = {
  ".vhd": "vhdl",
  ".vhdl": "vhdl",
  ".v": "verilog",
  ".sv": "sv",
}
# Included by other files, never compiled on their own: their directories are
# include directories.
HEADER_EXTENSIONS = (".vh", ".svh")

_HEADER_COMMENT = (
  "# Written by Odatix: what this simulation needs to know about the design under test.\n"
  "# Sources are listed in compilation order. Rewritten on every run.\n"
)


def language_of(path):
  """"vhdl", "verilog" or "sv" for an HDL source file, None for anything else."""
  return LANGUAGE_EXTENSIONS.get(os.path.splitext(str(path))[1].lower())


def _relative(path, root):
  """`path` relative to `root`, with "/" separators whatever the platform."""
  return os.path.relpath(os.path.normpath(path), root).replace(os.sep, "/")


######################################
# Finding the files
######################################

def scan_directory(directory, root):
  """
  The HDL files under `directory`, relative to `root`, in a stable order
  (directories and files sorted by name), and the directories holding headers.

  Returns:
    (files, include_dirs)
  """
  files = []
  include_dirs = []
  if not os.path.isdir(directory):
    return files, include_dirs
  for dirpath, dirnames, filenames in os.walk(directory):
    dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
    has_header = False
    for name in sorted(filenames):
      if language_of(name) is not None:
        files.append(_relative(os.path.join(dirpath, name), root))
      elif name.lower().endswith(HEADER_EXTENSIONS):
        has_header = True
    if has_header:
      include_dirs.append(_relative(dirpath, root))
  return files, include_dirs


def read_filelist(path, root, _seen=None):
  """
  The HDL files and include directories a filelist names, in its order,
  relative to `root`.

  One or more entries per line; "//" and "#" start a comment. "+incdir+a+b"
  adds include directories, "-f"/"-F" another filelist; other options are
  ignored, as are files that are not HDL sources. Relative paths are relative
  to the directory of the filelist naming them, and environment variables are
  expanded.

  Returns:
    (files, include_dirs)
  """
  seen = _seen if _seen is not None else set()
  path = os.path.realpath(path)
  seen.add(path)
  base = os.path.dirname(path)

  def resolve(entry):
    entry = os.path.expandvars(entry)
    if not os.path.isabs(entry):
      entry = os.path.join(base, entry)
    return entry

  tokens = []
  with open(path, "r") as f:
    for line in f:
      line = re.split(r"//|#", line, maxsplit=1)[0]
      tokens.extend(line.split())

  files = []
  include_dirs = []
  # Options followed by an argument that is not a source.
  options_with_argument = ("-y", "-v", "-L", "-work", "-top")
  index = 0
  while index < len(tokens):
    token = tokens[index]
    if token.startswith("+incdir+"):
      for directory in token[len("+incdir+"):].split("+"):
        if directory:
          include_dirs.append(_relative(resolve(directory), root))
    elif token in ("-f", "-F"):
      index += 1
      if index < len(tokens):
        nested = os.path.realpath(resolve(tokens[index]))
        if nested not in seen and os.path.isfile(nested):
          nested_files, nested_dirs = read_filelist(nested, root, seen)
          files.extend(nested_files)
          include_dirs.extend(nested_dirs)
    elif token in options_with_argument:
      index += 1
    elif token.startswith(("-", "+")):
      pass
    elif language_of(token) is not None:
      files.append(_relative(resolve(token), root))
    index += 1
  return _unique(files), _unique(include_dirs)


def _unique(items):
  return list(dict.fromkeys(items))


def split_by_language(files):
  """{language: [files]} for every language of LANGUAGES, in the given order."""
  by_language = {language: [] for language in LANGUAGES}
  for path in files:
    language = language_of(path)
    if language is not None:
      by_language[language].append(path)
  return by_language


######################################
# Compilation order
######################################

_VHDL_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_VHDL_DEFINES = (
  re.compile(r"\bentity\s+(\w+)\s+is\b"),
  re.compile(r"\bpackage\s+(?!body\b)(\w+)\s+is\b"),
  re.compile(r"\bcontext\s+(\w+)\s+is\b"),
  re.compile(r"\bconfiguration\s+(\w+)\s+of\b"),
)
_VHDL_USES = (
  # "use work.pkg.all", "context work.ctx", "entity work.x", and the same from
  # any library the design names: IEEE and STD never hold one of its units.
  re.compile(r"\buse\s+\w+\.(\w+)"),
  re.compile(r"\bcontext\s+\w+\.(\w+)"),
  re.compile(r"\bentity\s+\w+\.(\w+)"),
  re.compile(r"\bconfiguration\s+\w+\.(\w+)"),
  re.compile(r"\bpackage\s+body\s+(\w+)"),
  re.compile(r"\barchitecture\s+\w+\s+of\s+(\w+)"),
  re.compile(r"\bconfiguration\s+\w+\s+of\s+(\w+)"),
  re.compile(r"\bis\s+new\s+\w+\.(\w+)"),
)

_SV_COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_SV_DEFINES = (
  re.compile(r"\bpackage\s+(?:automatic\s+|static\s+)?(\w+)\s*;"),
)
_SV_USES = (
  re.compile(r"\b(\w+)\s*::"),
)

# The units a testbench top can be among.
_VHDL_ENTITIES = re.compile(r"\bentity\s+(\w+)\s+is\b")
_SV_MODULES = re.compile(r"\b(?:module|program)\s+(?:automatic\s+|static\s+)?(\w+)")


def _read_source(path):
  try:
    with open(path, "r", errors="replace") as f:
      return f.read()
  except (IOError, OSError):
    return ""


def _units(text, language):
  """(defined, used) units of an HDL source text."""
  if language == "vhdl":
    text = _VHDL_COMMENTS.sub(" ", text).lower()
    defines, uses = _VHDL_DEFINES, _VHDL_USES
  else:
    text = _SV_COMMENTS.sub(" ", text)
    defines, uses = _SV_DEFINES, _SV_USES
  defined = set()
  for pattern in defines:
    defined.update(pattern.findall(text))
  used = set()
  for pattern in uses:
    used.update(pattern.findall(text))
  return defined, used


def order_by_dependencies(files, root="."):
  """
  The files reordered so that each one comes after the files defining what it
  uses. Files that depend on nothing keep their place; a dependency cycle is
  broken by the original order.

  Args:
    files (list): paths of files of a same language family (VHDL, or Verilog
      and SystemVerilog), relative to `root`.
  """
  units = []
  defined_by = {}
  for index, path in enumerate(files):
    language = language_of(path) or "sv"
    defined, used = _units(_read_source(os.path.join(root, path)), language)
    units.append(used)
    for unit in defined:
      defined_by.setdefault(unit, index)

  depends_on = []
  for index, used in enumerate(units):
    depends_on.append({defined_by[unit] for unit in used if defined_by.get(unit, index) != index})

  ordered = []
  placed = set()
  while len(ordered) < len(files):
    ready = [i for i in range(len(files)) if i not in placed and depends_on[i] <= placed]
    # A cycle: take the first file left, as written.
    index = ready[0] if ready else min(i for i in range(len(files)) if i not in placed)
    ordered.append(index)
    placed.add(index)
  return [files[index] for index in ordered]


def collect_sources(work_dir, rtl_dir="rtl"):
  """
  The sources of the design under test, by language and in compilation order,
  relative to the work directory.

  Returns:
    dict: {"vhdl": [...], "verilog": [...], "sv": [...], "include_dirs": [...],
    "order": "filelist" or "dependencies"}
  """
  filelist = os.path.join(work_dir, rtl_dir, USER_FILELIST_FILENAME)
  if os.path.isfile(filelist):
    files, include_dirs = read_filelist(filelist, work_dir)
    order = "filelist"
  else:
    files, include_dirs = scan_directory(os.path.join(work_dir, rtl_dir), work_dir)
    order = "dependencies"

  if order == "dependencies":
    # A file another one includes is compiled through it, and its directory is
    # where the includer looks for it.
    included, included_dirs = _included_files(files, work_dir)
    files = [path for path in files if path not in included]
    include_dirs = _unique(include_dirs + included_dirs)

  sources = split_by_language(files)
  if order == "dependencies":
    sources["vhdl"] = order_by_dependencies(sources["vhdl"], work_dir)
    # A Verilog file can use a SystemVerilog package: sort them together, then
    # split again.
    ordered = order_by_dependencies(sources["verilog"] + sources["sv"], work_dir)
    sources["verilog"] = [path for path in ordered if language_of(path) == "verilog"]
    sources["sv"] = [path for path in ordered if language_of(path) == "sv"]
  sources["include_dirs"] = include_dirs
  sources["order"] = order
  return sources


_INCLUDE = re.compile(r'`include\s+"([^"]+)"')


def _included_files(files, root):
  """
  The Verilog sources that other sources include ("`include"), and the
  directories they are found in from those includes.
  """
  by_suffix = {}
  for path in files:
    by_suffix.setdefault(os.path.basename(path), []).append(path)
  included = set()
  directories = []
  for path in files:
    if language_of(path) not in ("verilog", "sv"):
      continue
    for name in _INCLUDE.findall(_SV_COMMENTS.sub(" ", _read_source(os.path.join(root, path)))):
      name = name.replace("\\", "/")
      for candidate in by_suffix.get(os.path.basename(name), []):
        if candidate == path or not candidate.endswith(name):
          continue
        included.add(candidate)
        directory = candidate[:-len(name)].rstrip("/") or "."
        directories.append(directory)
  return included, _unique(directories)


def languages_of(sources):
  """The languages a set of sources is written in, in the order of LANGUAGES."""
  return [language for language in LANGUAGES if sources.get(language)]


def source_languages(rtl_dir):
  """The languages of the RTL in a directory, before it is copied anywhere."""
  if not rtl_dir or not os.path.isdir(rtl_dir):
    return []
  filelist = os.path.join(rtl_dir, USER_FILELIST_FILENAME)
  if os.path.isfile(filelist):
    files, _include_dirs = read_filelist(filelist, rtl_dir)
  else:
    files, _include_dirs = scan_directory(rtl_dir, rtl_dir)
  return languages_of(split_by_language(files))


######################################
# Testbench
######################################

def _testbench_units(files, root):
  """Modules, programs and entities defined in the testbench files, in order."""
  units = []
  for path in files:
    text = _read_source(os.path.join(root, path))
    if language_of(path) == "vhdl":
      units.extend(_VHDL_ENTITIES.findall(_VHDL_COMMENTS.sub(" ", text)))
    else:
      units.extend(_SV_MODULES.findall(_SV_COMMENTS.sub(" ", text)))
  return _unique(units)


def guess_testbench_top(files, root, dut_top=""):
  """
  The top of a testbench that does not name it: "tb_<dut>" when one of its
  files defines it, the only unit when there is one, otherwise the only unit no
  other one instantiates. Empty when it cannot be told.
  """
  units = _testbench_units(files, root)
  if not units:
    return ""
  if dut_top:
    for unit in units:
      if unit.lower() == ("tb_" + dut_top).lower():
        return unit
  if len(units) == 1:
    return units[0]
  text = " ".join(
    (_VHDL_COMMENTS if language_of(path) == "vhdl" else _SV_COMMENTS).sub(" ", _read_source(os.path.join(root, path)))
    for path in files
  )
  roots = [unit for unit in units if not _is_instantiated(unit, text)]
  return roots[0] if len(roots) == 1 else ""


def _is_instantiated(unit, text):
  """True when `text` instantiates `unit` (VHDL or Verilog syntax)."""
  name = re.escape(unit)
  vhdl = r":\s*(?:entity\s+\w+\.|component\s+)?" + name + r"\b(?:\s*\(\s*\w+\s*\))?\s*(?:generic|port)\s+map"
  if re.search(vhdl, text, re.I):
    return True
  for match in re.finditer(r"\b" + name + r"\s*(?:#\s*\(.*?\)\s*)?\w+\s*\(", text, re.S):
    before = text[:match.start()].split()
    if not before or before[-1] not in ("module", "program", "interface", "automatic", "static"):
      return True
  return False


def match_files(patterns, root="."):
  """
  The HDL files matching glob patterns, relative to `root`, in the order of
  the patterns, each one's matches sorted.
  """
  if isinstance(patterns, str):
    patterns = [patterns]
  files = []
  for pattern in patterns or []:
    for match in sorted(glob.glob(os.path.join(root, str(pattern)))):
      if os.path.isfile(match) and language_of(match) is not None:
        files.append(_relative(match, root))
  return _unique(files)


def collect_testbench(work_dir, declared=None, dut_top=""):
  """
  The testbench a simulation runs, relative to the work directory.

  Args:
    declared (dict): the "testbench" a simulation declares ({"top", "files",
      "parameters"}), if any. Files may be glob patterns, relative to the work directory, where
      the simulation's own files are copied. Without files, every HDL file of
      its "tb" directory is taken.
    dut_top (str): top of the design under test, used to guess the testbench
      top when it is not given.

  Returns:
    dict: {"top": str, "files": [...], "languages": [...]}
  """
  declared = declared if isinstance(declared, dict) else {}
  patterns = declared.get("files")
  if isinstance(patterns, str):
    patterns = [patterns]

  if patterns:
    files = match_files(patterns, work_dir)
  else:
    files, _include_dirs = scan_directory(os.path.join(work_dir, DEFAULT_TESTBENCH_DIR), work_dir)

  by_language = split_by_language(files)
  vhdl = order_by_dependencies(by_language["vhdl"], work_dir)
  vlog = order_by_dependencies(by_language["verilog"] + by_language["sv"], work_dir)
  files = vhdl + vlog

  top = str(declared.get("top") or "") or guess_testbench_top(files, work_dir, dut_top)
  parameters = declared.get("parameters")
  testbench = {
    "top": top,
    "files": files,
    "languages": languages_of(split_by_language(files)),
    "parameters": {str(name): str(value) for name, value in parameters.items()} if isinstance(parameters, dict) else {},
    "include_dirs": _testbench_include_dirs(files, work_dir),
  }
  if not files:
    # No testbench anywhere: the template generates one when the job starts,
    # once the RTL exists (see odatix.sim.testbench_gen).
    testbench["generated"] = True
    for key, default in GENERATED_TESTBENCH_DEFAULTS.items():
      value = declared.get(key)
      testbench[key] = default if value is None else value
  return testbench


def _testbench_include_dirs(files, root):
  """
  The directories of the Verilog testbench files and those holding headers
  below them: a testbench includes its headers relative to itself.
  """
  directories = _unique(
    os.path.dirname(path) or "." for path in files if language_of(path) in ("verilog", "sv")
  )
  include_dirs = []
  for directory in directories:
    include_dirs.append(directory)
    include_dirs.extend(scan_directory(os.path.join(root, directory), root)[1])
  return _unique(include_dirs)


# What a "testbench" setting holds: its top, its files, and the parameters
# (generics) its top is given, whose values may use the placeholders of the
# simulation commands, ${width} for instance.
TESTBENCH_KEYS = ("top", "files", "parameters", "cycles", "stimulus", "waves")
# What the testbench Odatix generates for a design without one does (see
# odatix.sim.testbench_gen): how many cycles it runs, whether it drives the
# inputs with random values or zeros, and whether it dumps a VCD.
GENERATED_TESTBENCH_DEFAULTS = {"cycles": 1000, "stimulus": "random", "waves": True}
STIMULI = ("random", "zero")


def check_testbench(testbench):
  """
  What is wrong with a "testbench" setting ({"top": name, "files": file or
  list of files, "parameters": {name: value}}), or None when it is valid.
  """
  if not isinstance(testbench, dict):
    return "must be a mapping with the keys \"top\" and \"files\""
  unknown = sorted(str(key) for key in testbench if key not in TESTBENCH_KEYS)
  if unknown:
    return "has unknown keys: \"" + "\", \"".join(unknown) + "\" (expected \"" + "\", \"".join(TESTBENCH_KEYS) + "\")"
  if testbench.get("top") is not None and not isinstance(testbench.get("top"), str):
    return "\"top\" must be the name of a module or an entity"
  files = testbench.get("files")
  if files is not None and not isinstance(files, str) and not (
    isinstance(files, list) and all(isinstance(path, str) for path in files)
  ):
    return "\"files\" must be a file or a list of files"
  parameters = testbench.get("parameters")
  if parameters is not None and not isinstance(parameters, dict):
    return "\"parameters\" must be a mapping of parameter names to values"
  cycles = testbench.get("cycles")
  if cycles is not None and (isinstance(cycles, bool) or not isinstance(cycles, int) or cycles <= 0):
    return "\"cycles\" must be a positive number of cycles"
  stimulus = testbench.get("stimulus")
  if stimulus is not None and stimulus not in STIMULI:
    return "\"stimulus\" must be one of \"" + "\", \"".join(STIMULI) + "\""
  if testbench.get("waves") is not None and not isinstance(testbench.get("waves"), bool):
    return "\"waves\" must be Yes or No"
  return None


_ACTIVE_LOW_RESET = re.compile(r"(_n|_ni|_b|_l)$|(rst|reset)n$|^n_?(rst|reset)", re.I)


def reset_is_active_low(name):
  """What a reset's name says of its polarity: rst_n, resetn, nreset are active low."""
  return bool(_ACTIVE_LOW_RESET.search(str(name or "")))


######################################
# The information file
######################################

def build_info(
  work_dir,
  simulation="",
  architecture="",
  configuration="",
  arch_full="",
  top="",
  clock="",
  reset="",
  param_domains=None,
  testbench=None,
  rtl_generated=False,
  rtl_dir="rtl",
  reset_active_low=None,
):
  """
  Everything a simulation is told about the design under test (the content of
  "odatix_sim.yml").

  Args:
    param_domains (dict): {domain: value} of the configuration under test.
    testbench (dict): the "testbench" the simulation declares, if any.
    rtl_generated (bool): the RTL is generated by the job itself, so the
      sources are only known once it has run (see refresh_command).
    reset_active_low (bool): the polarity of the reset, guessed from its name
      when None.
  """
  sources = collect_sources(work_dir, rtl_dir)
  return {
    "simulation": str(simulation),
    "architecture": str(architecture),
    "configuration": str(configuration),
    "arch_full": str(arch_full),
    "dut": {
      "top": str(top or ""),
      "clock": str(clock or ""),
      "reset": str(reset or ""),
      "reset_active_low": bool(reset_is_active_low(reset) if reset_active_low is None else reset_active_low),
      "languages": languages_of(sources),
      "rtl_dir": rtl_dir,
      "rtl_generated": bool(rtl_generated),
    },
    "sources": sources,
    "testbench": collect_testbench(work_dir, testbench, top),
    "param_domains": {str(name): str(value) for name, value in (param_domains or {}).items()},
  }


def filelist_lines(info):
  """The lines of "odatix_sim.f": include directories, design, testbench."""
  sources = info.get("sources", {})
  lines = ["// Written by Odatix: the design under test, then its testbench, in compilation order"]
  lines.extend("+incdir+" + directory for directory in sources.get("include_dirs", []))
  for language in LANGUAGES:
    lines.extend(sources.get(language, []))
  lines.extend(info.get("testbench", {}).get("files", []))
  return lines


def write_info(work_dir, info):
  """Write "odatix_sim.yml" and "odatix_sim.f" into the work directory."""
  with open(os.path.join(work_dir, SIM_INFO_FILENAME), "w") as f:
    f.write(_HEADER_COMMENT)
    yaml.dump(info, f, default_flow_style=False, sort_keys=False)
  with open(os.path.join(work_dir, SIM_FILELIST_FILENAME), "w") as f:
    f.write("\n".join(filelist_lines(info)) + "\n")


def read_info(work_dir):
  """The content of "odatix_sim.yml" in a work directory, {} when it is missing."""
  path = os.path.join(work_dir, SIM_INFO_FILENAME)
  if not os.path.isfile(path):
    return {}
  with open(path, "r") as f:
    data = yaml.safe_load(f)
  return data if isinstance(data, dict) else {}


def refresh(work_dir):
  """
  Collect the sources again and rewrite the information files: what a job with
  a generated RTL does once it is generated.
  """
  info = read_info(work_dir)
  dut = info.setdefault("dut", {})
  sources = collect_sources(work_dir, dut.get("rtl_dir") or "rtl")
  info["sources"] = sources
  dut["languages"] = languages_of(sources)
  write_info(work_dir, info)
  return info


def refresh_command(work_dir="."):
  """The shell command rewriting the information files of `work_dir`."""
  return '"{}" "{}" "{}"'.format(sys.executable, os.path.abspath(__file__), work_dir)


def substitutions(info):
  """
  The placeholders a simulation command can use, from the information file.
  Lists are joined with spaces, paths are relative to the work directory.
  """
  sources = info.get("sources", {})
  testbench = info.get("testbench", {})
  dut = info.get("dut", {})
  return {
    "vhdl_files": " ".join(sources.get("vhdl", [])),
    "verilog_files": " ".join(sources.get("verilog", [])),
    "sv_files": " ".join(sources.get("sv", [])),
    "include_dirs": " ".join(sources.get("include_dirs", [])),
    "languages": " ".join(dut.get("languages", [])),
    "reset_signal": str(dut.get("reset", "")),
    "tb_top": str(testbench.get("top", "")),
    "tb_files": " ".join(testbench.get("files", [])),
    "python": sys.executable,
  }


if __name__ == "__main__":
  refresh(sys.argv[1] if len(sys.argv) > 1 else ".")
