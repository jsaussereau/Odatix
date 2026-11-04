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
Verilator on Windows, without its Perl front end and without make.

"verilator --binary" verilates the design, then runs make on the makefile it
wrote, which compiles the C++ and links the simulator. The OSS CAD Suite for
Windows ships none of what that needs but Verilator itself: no Perl to run the
"verilator" script, no make, no C++ compiler. Here, "verilator_bin.exe"
verilates, and the C++ is compiled in one command of the compiler the PATH
holds (g++ or clang++: MSYS2, WinLibs, LLVM), from the files and the flags the
makefiles Verilator wrote list. Only the compiler has to be installed.

    sim = SimRunner("verilator", languages=["verilog", "sv"])
    verilator.build(sim, options, executable="odatix_sim")
    sim.run("simulate", [os.path.join("obj_dir", "odatix_sim")])
"""

import os
import re
import shutil

from odatix.lib import programs

#: Where the C++ is written and the simulator built, as "-Mdir" says
OBJ_DIR = "obj_dir"

#: The C++ compilers looked for in the PATH when $CXX names none, in order
COMPILERS = ("g++", "clang++")

#: The flags of the generated makefiles passed on as -D, as verilated.mk does
DEFINES = (
  "VM_COVERAGE", "VM_SC", "VM_TIMING", "VM_TRACE", "VM_TRACE_FST", "VM_TRACE_VCD", "VM_TRACE_SAIF", "VM_VPI",
)

#: The warnings verilated.mk silences in generated code
QUIET = (
  "-faligned-new", "-Wno-bool-operation", "-Wno-int-in-bool-context", "-Wno-shadow", "-Wno-sign-compare",
  "-Wno-tautological-compare", "-Wno-uninitialized", "-Wno-unused-parameter", "-Wno-unused-variable",
)

_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(\+=|\?=|:=|=)\s*(.*)$")

MISSING_COMPILER = (
  "Verilator builds a C++ simulator, and no C++ compiler is in the PATH (g++ or clang++): the OSS CAD Suite does "
  "not ship one on Windows. Install one (MSYS2: \"pacman -S mingw-w64-ucrt-x86_64-gcc\", then add its "
  "ucrt64\\bin directory to the PATH), simulate with the \"icarus\" template instead, or run Verilator in WSL "
  "(\"wsl_tools\" in odatix.yml)"
)


def program():
  """The Verilator that verilates: its binary on Windows, its front end elsewhere."""
  return programs.which("verilator")


def environment(path):
  """
  What the binary of Verilator needs to find its include files when it is run
  without its Perl front end: VERILATOR_ROOT, found next to it in the usual
  layouts (OSS CAD Suite: share/verilator, MSYS2: the prefix itself).
  """
  if os.environ.get("VERILATOR_ROOT") or not path:
    return {}
  prefix = os.path.dirname(os.path.dirname(os.path.abspath(path)))
  for root in (os.path.join(prefix, "share", "verilator"), prefix):
    if os.path.isdir(os.path.join(root, "include")):
      return {"VERILATOR_ROOT": root}
  return {}


def compiler():
  """The C++ compiler to build with: $CXX, else the first of COMPILERS in the PATH, or None."""
  configured = os.environ.get("CXX", "").strip()
  if configured:
    return shutil.which(configured) or configured
  for name in COMPILERS:
    found = shutil.which(name)
    if found:
      return found
  return None


def read_makefile(path):
  """
  The variables a makefile written by Verilator sets, each a list of words.
  Only what these makefiles hold is understood: "NAME = value" and
  "NAME += value", continued on the next line by a backslash.
  """
  variables = {}
  with open(path, encoding="utf-8", errors="replace") as f:
    text = f.read().replace("\\\r\n", " ").replace("\\\n", " ")
  for line in text.splitlines():
    match = _ASSIGNMENT.match(line.strip())
    if not match:
      continue
    name, operator, value = match.groups()
    words = value.split("#")[0].split()
    if operator == "+=":
      variables.setdefault(name, []).extend(words)
    elif operator != "?=" or name not in variables:
      variables[name] = words
  return variables


def build_command(cxx, prefix, root, executable, obj_dir=OBJ_DIR):
  """
  The command compiling and linking the C++ Verilator wrote in `obj_dir` for
  the model `prefix` (V<top>), with the runtime of `root` (VERILATOR_ROOT).
  """
  variables = read_makefile(os.path.join(obj_dir, prefix + "_classes.mk"))
  variables.update(read_makefile(os.path.join(obj_dir, prefix + ".mk")))

  def value(name, default="0"):
    words = variables.get(name) or [default]
    return words[0]

  include = os.path.join(root, "include")
  is_clang = "clang" in os.path.basename(cxx).lower()
  timing = value("VM_TIMING") not in ("0", "")

  command = [cxx, "-std=gnu++20", "-Os"]
  if timing and not is_clang:
    command.append("-fcoroutines")
  command += ["-I" + obj_dir, "-I" + include, "-I" + os.path.join(include, "vltstd"), "-DVERILATOR=1"]
  command += ["-D{0}={1}".format(name, value(name)) for name in DEFINES]
  command.append("-DVM_PREFIX_INCLUDE=<{0}.h>".format(prefix))
  command += variables.get("VM_USER_CFLAGS", [])
  command += list(QUIET)

  generated = []
  for name in ("VM_CLASSES_FAST", "VM_CLASSES_SLOW", "VM_SUPPORT_FAST", "VM_SUPPORT_SLOW", "VM_USER_CLASSES"):
    generated += variables.get(name, [])
  command += [os.path.join(obj_dir, name + ".cpp") for name in generated]
  command += [os.path.join(include, name + ".cpp") for name in variables.get("VM_GLOBAL_FAST", []) + variables.get("VM_GLOBAL_SLOW", [])]

  command += ["-o", os.path.join(obj_dir, executable)]
  # Linked statically: the PATH of a Windows holding the OSS CAD Suite also
  # holds its own C++ runtime (lib\libstdc++-6.dll), which a simulator built
  # by another compiler would otherwise load, and fail to start with.
  command += ["-static", "-pthread"]
  command += variables.get("VM_USER_LDLIBS", [])
  return command


def build(sim, options, executable="odatix_sim"):
  """
  Verilate the design with the binary of Verilator, then compile and link the
  simulator `obj_dir/<executable>`, both as the "compile" stage of `sim`.

  Args:
    options (list): what "verilator --binary" would be given besides
      "--binary", "-Mdir" and "-o": the top module, the files, the parameters.
  """
  cxx = compiler()
  if cxx is None:
    sim.fail(MISSING_COMPILER)
  path = program()
  if path is None:
    sim.fail("verilator is not in the PATH (neither verilator nor verilator_bin)")
  env = environment(path)
  root = env.get("VERILATOR_ROOT") or os.environ.get("VERILATOR_ROOT", "")
  if not root:
    sim.fail("VERILATOR_ROOT is not set, and the include files of Verilator are not next to " + path)

  # "--binary" is "--cc --exe --main --timing --build": all of it but the build
  command = [path, "--cc", "--exe", "--main", "--timing", "-Mdir", OBJ_DIR] + list(options)
  sim.run("compile", command, log="verilator", env=env)

  top = sim.tb_top
  prefix = "V" + top
  sim.run("compile", build_command(cxx, prefix, root, executable), log="cxx")
