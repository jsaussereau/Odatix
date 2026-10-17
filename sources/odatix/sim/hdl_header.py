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
The header of the top of a design: its parameters and its ports.

What the generated testbench needs to instantiate the design (see
odatix.sim.testbench_gen). Nothing is evaluated: declarations are kept as
written, so that "logic [WIDTH-1:0]" stays valid next to a copy of the
parameter WIDTH, whatever WIDTH is. The parameters already hold the values of
the configuration, which Odatix wrote into the RTL.

Handled:
  - Verilog and SystemVerilog modules with an ANSI header: parameters in
    "#(...)", ports with their direction in "(...)", packages imported before
    the module or in its header;
  - VHDL entities: generics and ports, and the context clauses before them.

Anything else (an interface port, a Verilog header listing only port names, a
port of an unconstrained or unknown type...) raises HeaderError, which says to
give the design a testbench of its own.
"""

import re

LANGUAGE_SV = "sv"
LANGUAGE_VHDL = "vhdl"

DIRECTIONS = ("input", "output", "inout")
VHDL_DIRECTIONS = ("in", "out", "inout", "buffer")


class HeaderError(ValueError):
  pass


class Parameter(object):
  """A parameter (generic) of the top: its name and its declaration."""

  def __init__(self, name, declaration):
    self.name = name
    #: SystemVerilog: "int WIDTH = 16", without "parameter".
    #: VHDL: "WIDTH : integer := 16".
    self.declaration = declaration

  def __repr__(self):
    return "Parameter(" + self.name + ")"


class Port(object):
  """A port of the top: its name, its direction and its type."""

  def __init__(self, name, direction, type_text, unpacked=""):
    self.name = name
    self.direction = direction
    #: SystemVerilog: "logic signed [WIDTH-1:0]". VHDL: "std_logic_vector(7 downto 0)".
    self.type = type_text
    #: SystemVerilog unpacked dimensions, written after the name.
    self.unpacked = unpacked

  @property
  def is_input(self):
    return self.direction in ("input", "in")

  @property
  def is_output(self):
    return self.direction in ("output", "out", "buffer", "inout")

  def __repr__(self):
    return "Port(" + self.direction + " " + self.type + " " + self.name + self.unpacked + ")"


class Header(object):
  def __init__(self, language, name, parameters, ports, context, timescale=""):
    self.language = language
    #: The "`timescale" the module is compiled with, if any: a testbench
    #: instantiating it uses the same, or some simulators complain.
    self.timescale = timescale
    self.name = name
    self.parameters = parameters
    self.ports = ports
    #: What the declarations need: SystemVerilog "import" statements, VHDL
    #: "library" and "use" clauses.
    self.context = context

  def port(self, name):
    for port in self.ports:
      if port.name.lower() == str(name).lower():
        return port
    return None


######################################
# Helpers
######################################

_SV_COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_VHDL_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)


def _balanced(text, start):
  """
  The text between the parenthesis at `start` and the one closing it, and the
  index after it.
  """
  if start >= len(text) or text[start] != "(":
    raise HeaderError("expected \"(\"")
  depth = 0
  for index in range(start, len(text)):
    char = text[index]
    if char == "(":
      depth += 1
    elif char == ")":
      depth -= 1
      if depth == 0:
        return text[start + 1:index], index + 1
  raise HeaderError("unbalanced parentheses")


def _split(text, separator):
  """`text` split at the separators that are not inside brackets."""
  items = []
  depth = 0
  current = []
  for char in text:
    if char in "([{":
      depth += 1
    elif char in ")]}":
      depth -= 1
    if char == separator and depth == 0:
      items.append("".join(current))
      current = []
    else:
      current.append(char)
  items.append("".join(current))
  return [" ".join(item.split()) for item in items if item.strip()]


def _skip_spaces(text, index):
  while index < len(text) and text[index].isspace():
    index += 1
  return index


######################################
# SystemVerilog
######################################

_SV_NET_KEYWORDS = ("wire", "reg", "var", "logic", "tri", "uwire", "wand", "wor")
_SV_INTEGER_TYPES = ("bit", "byte", "shortint", "int", "longint", "integer", "time", "real", "shortreal", "realtime", "string")


def parse_sv(text, top):
  """The header of the module `top` in a Verilog or SystemVerilog source."""
  text = _SV_COMMENTS.sub(" ", text)
  match = re.search(r"\bmodule\s+(?:automatic\s+|static\s+)?" + re.escape(top) + r"\b", text)
  if match is None:
    raise HeaderError("no module \"" + top + "\"")

  timescales = re.findall(r"`timescale[^\n]*", text[:match.start()])

  # Packages imported before the module, in the compilation unit, and in its header
  context = re.findall(r"\bimport\s+[\w:*,\s]+;", text[:match.start()])
  index = match.end()
  while True:
    index = _skip_spaces(text, index)
    imported = re.match(r"import\s+[\w:*,\s]+;", text[index:])
    if imported is None:
      break
    context.append(imported.group(0))
    index += imported.end()

  parameters = []
  index = _skip_spaces(text, index)
  if text.startswith("#", index):
    index = _skip_spaces(text, index + 1)
    body, index = _balanced(text, index)
    parameters = _sv_parameters(body)

  index = _skip_spaces(text, index)
  ports = []
  if text.startswith("(", index):
    body, index = _balanced(text, index)
    ports = _sv_ports(body, top)
  return Header(
    LANGUAGE_SV, top, parameters, ports, [" ".join(item.split()) for item in context],
    timescale=timescales[-1].strip() if timescales else "",
  )


def _sv_parameters(body):
  parameters = []
  prefix = ""
  for item in _split(body, ","):
    words = item.split()
    if words[0] in ("parameter", "localparam"):
      item = item[len(words[0]):].strip()
      if re.match(r"type\b", item):
        raise HeaderError("a type parameter is not handled")
      name_match = re.match(r"(.*?)\b(\w+)\s*(\[[^=]*\])?\s*=", item)
      prefix = name_match.group(1).strip() if name_match else ""
    elif words[0] == "type":
      raise HeaderError("a type parameter is not handled")
    elif prefix and "=" in item:
      item = prefix + " " + item
    if "=" not in item:
      raise HeaderError("the parameter \"" + item + "\" has no value")
    name = re.match(r"(.*?)\b(\w+)\s*(\[[^=]*\])?\s*=", item).group(2)
    parameters.append(Parameter(name, item))
  return parameters


def _sv_ports(body, top):
  ports = []
  direction = None
  type_text = "logic"
  for item in _split(body, ","):
    words = item.split()
    if words[0] in DIRECTIONS:
      direction = words[0]
      item = item[len(words[0]):].strip()
      declaration = re.match(r"(.*?)\b(\w+)\s*((?:\[[^\]]*\]\s*)*)$", item)
      if declaration is None:
        raise HeaderError("cannot read the port \"" + item + "\"")
      type_text = _sv_type(declaration.group(1).strip())
      name, unpacked = declaration.group(2), declaration.group(3).strip()
    elif direction is None:
      if re.match(r"^\w+$", item):
        raise HeaderError(
          "the ports of \"" + top + "\" are only listed in its header (non-ANSI style): "
          "their directions and types are not handled"
        )
      raise HeaderError("the port \"" + item + "\" has no direction: interface ports are not handled")
    else:
      # "input a, b": the next names share the direction and type of the first.
      declaration = re.match(r"^(\w+)\s*((?:\[[^\]]*\]\s*)*)$", item)
      if declaration is None:
        raise HeaderError("cannot read the port \"" + item + "\"")
      name, unpacked = declaration.group(1), declaration.group(2).strip()
    if "." in type_text:
      raise HeaderError("the port \"" + name + "\" is an interface: interface ports are not handled")
    ports.append(Port(name, direction, type_text, unpacked))
  return ports


def _sv_type(declared):
  """What a signal connected to a port of that declared type is declared as."""
  words = declared.split()
  if words and words[0] in _SV_NET_KEYWORDS:
    words = words[1:]
    if words and words[0] == "logic":
      words = words[1:]
    return " ".join(["logic"] + words)
  if not words or words[0] in ("signed", "unsigned") or words[0].startswith("["):
    return " ".join(["logic"] + words)
  return " ".join(words)


######################################
# VHDL
######################################

def parse_vhdl(text, top):
  """The header of the entity `top` in a VHDL source."""
  text = _VHDL_COMMENTS.sub(" ", text)
  match = re.search(r"\bentity\s+" + re.escape(top) + r"\s+is\b", text, re.I)
  if match is None:
    raise HeaderError("no entity \"" + top + "\"")

  # The context clauses of the design unit: those since the previous unit
  previous_end = max(
    [m.end() for m in re.finditer(r"\bend\b[^;]*;", text[:match.start()], re.I)] or [0]
  )
  context = [
    " ".join(clause.split()) for clause in
    re.findall(r"\b(?:library|use|context)\s+[^;]+;", text[previous_end:match.start()], re.I)
  ]

  end = re.search(r"\bend\b", text[match.end():], re.I)
  header_end = match.end() + (end.start() if end else len(text))
  parameters = []
  ports = []
  index = match.end()
  while index < header_end:
    clause = re.compile(r"\s*(generic|port)\s*", re.I).match(text, index)
    if clause is None:
      break
    body, index = _balanced(text, clause.end())
    index = text.index(";", index) + 1
    if clause.group(1).lower() == "generic":
      parameters = _vhdl_generics(body)
    else:
      ports = _vhdl_ports(body)
  return Header(LANGUAGE_VHDL, top, parameters, ports, context)


def _vhdl_generics(body):
  parameters = []
  for item in _split(body, ";"):
    names, _colon, rest = item.partition(":")
    if ":=" not in rest:
      raise HeaderError("the generic \"" + names.strip() + "\" has no default value")
    if re.match(r"^\s*(type|function|procedure|package)\b", item, re.I):
      raise HeaderError("a generic type, subprogram or package is not handled")
    for name in names.replace("constant", " ").split(","):
      parameters.append(Parameter(name.strip(), name.strip() + " :" + rest))
  return parameters


def _vhdl_ports(body):
  ports = []
  for item in _split(body, ";"):
    names, _colon, rest = item.partition(":")
    words = rest.split()
    if not words or words[0].lower() not in VHDL_DIRECTIONS:
      raise HeaderError("the port \"" + names.strip() + "\" has no mode (in, out, inout)")
    direction = words[0].lower()
    type_text = rest.strip()[len(words[0]):].split(":=")[0].strip()
    if re.match(r"^\w+_vector$|^(unsigned|signed|bit_vector|string)$", type_text, re.I):
      raise HeaderError("the port \"" + names.strip() + "\" has an unconstrained type")
    for name in names.replace("signal", " ").split(","):
      ports.append(Port(name.strip(), direction, type_text))
  return ports


def parse(text, top, language):
  """The header of `top` in a source of that language ("vhdl", "verilog" or "sv")."""
  if language == LANGUAGE_VHDL:
    return parse_vhdl(text, top)
  return parse_sv(text, top)
