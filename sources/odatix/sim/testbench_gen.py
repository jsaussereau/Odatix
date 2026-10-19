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
The minimal testbench Odatix generates for a design that has none.

It does not check what the design computes. It instantiates the design,
generates its clock, applies its reset, then drives its inputs with random
values (or zeros) for a number of cycles, and dumps a VCD. That covers
compiling, elaborating, the speed of the simulator, and gives a realistic
activity to estimate the power from.

It only checks that:
  - no output is unknown (X) once the reset is released;
  - no assertion of the design fires (the simulator reports it as an error).

It is written in the language of the top of the design: a VHDL testbench for a
VHDL entity, a SystemVerilog one for a Verilog or SystemVerilog module. The
header of the top is copied as written (see odatix.sim.hdl_header), so its
widths are valid without being evaluated.
"""

import os
import re

import odatix.sim.design_info as design_info
import odatix.sim.hdl_header as hdl_header

TOP = "odatix_tb"
DEFAULT_CYCLES = 1000
RESET_CYCLES = 5
CLOCK_HALF_PERIOD_NS = 5
STIMULI = ("random", "zero")
WAVES_FILENAME = "odatix_sim.vcd"
# How many unknown outputs are reported, before staying quiet.
REPORTED_UNKNOWNS = 10

######################################
# Finding the top
######################################

def find_top(info, work_dir="."):
  """
  The header of the top of the design under test, read from its sources.

  Raises:
    HeaderError: the top cannot be found or read.
  """
  top = str(info.get("dut", {}).get("top", ""))
  if not top:
    raise hdl_header.HeaderError("the design has no top_level_module")
  sources = info.get("sources", {})
  candidates = [(path, "vhdl") for path in sources.get("vhdl", [])]
  candidates += [(path, "sv") for path in sources.get("verilog", []) + sources.get("sv", [])]
  for path, language in candidates:
    try:
      with open(os.path.join(work_dir, path), "r", errors="replace", encoding="utf-8") as f:
        text = f.read()
    except (IOError, OSError):
      continue
    pattern = r"\bentity\s+" + re.escape(top) + r"\s+is\b" if language == "vhdl" else r"\bmodule\s+" + re.escape(top) + r"\b"
    if re.search(pattern, text, re.I if language == "vhdl" else 0):
      return hdl_header.parse(text, top, language)
  raise hdl_header.HeaderError("no source of the design defines its top, \"" + top + "\"")


######################################
# SystemVerilog
######################################

_SV_NUMBERS = ("logic", "bit", "byte", "shortint", "int", "longint", "integer", "time", "reg", "wire")
_SV_REALS = ("real", "shortreal", "realtime")


def _sv_kind(port):
  """"vector", "real", "user" (a type of the design) or "string"."""
  first = port.type.split()[0] if port.type else "logic"
  if first in _SV_NUMBERS:
    return "vector"
  if first in _SV_REALS:
    return "real"
  if first == "string":
    return "string"
  return "user"


def _sv_value(port, random):
  kind = _sv_kind(port)
  if kind == "real":
    return "$urandom / 4294967296.0" if random else "0.0"
  value = "{4{$urandom}}" if random else "'0"
  if kind == "user":
    return port.type + "'(" + ("{4{$urandom}}" if random else "0") + ")"
  return value


def generate_sv(header, clock="", reset="", reset_active_low=False, cycles=DEFAULT_CYCLES, stimulus="random", waves=True):
  clock_port = header.port(clock) if clock else None
  reset_port = header.port(reset) if reset else None
  for port in header.ports:
    if port.unpacked:
      raise hdl_header.HeaderError("the port \"" + port.name + "\" is an unpacked array: it is not handled")
  inputs = [p for p in header.ports if p.is_input and p not in (clock_port, reset_port) and _sv_kind(p) != "string"]
  outputs = [p for p in header.ports if p.is_output and _sv_kind(p) in ("vector", "user")]
  active, inactive = ("1'b0", "1'b1") if reset_active_low else ("1'b1", "1'b0")
  wait = "@(negedge " + clock_port.name + ");" if clock_port else "#" + str(2 * CLOCK_HALF_PERIOD_NS) + ";"

  # The time unit of the design, if it gives one: a testbench with one and a
  # design without (or the other way around) is warned about, or refused.
  lines = [header.timescale, ""] if header.timescale else []
  lines += [
    "// Generated by Odatix: a minimal testbench for \"" + header.name + "\", which has none.",
    "// It drives the inputs with " + ("random values" if stimulus == "random" else "zeros")
    + " and checks that no output is unknown once out of reset.",
    "",
    "module " + TOP + ";",
  ]
  lines += ["  " + clause for clause in header.context]
  if header.parameters:
    lines.append("")
    lines += ["  localparam " + parameter.declaration + ";" for parameter in header.parameters]
  lines.append("")
  lines += ["  " + port.type + " " + port.name + ";" for port in header.ports]
  lines += [
    "",
    "  localparam int ODATIX_CYCLES = " + str(int(cycles)) + ";",
    "  int odatix_unknowns = 0;",
    "",
    "  " + header.name + " dut (",
    ",\n".join("    ." + port.name + " (" + port.name + ")" for port in header.ports),
    "  );",
    "",
  ]
  if clock_port is not None:
    lines += [
      "  initial " + clock_port.name + " = 1'b0;",
      "  always #" + str(CLOCK_HALF_PERIOD_NS) + " " + clock_port.name + " = ~" + clock_port.name + ";",
      "",
    ]
  lines += ["  initial begin"]
  if waves:
    lines += [
      "    $dumpfile(\"" + WAVES_FILENAME + "\");",
      "    $dumpvars(0, dut);",
    ]
  lines += ["    " + port.name + " = " + _sv_value(port, False) + ";" for port in inputs]
  if reset_port is not None:
    lines.append("    " + reset_port.name + " = " + active + ";")
  lines += ["    repeat (" + str(RESET_CYCLES) + ") " + wait]
  if reset_port is not None:
    lines.append("    " + reset_port.name + " = " + inactive + ";")
  lines += [
    "    for (int cycle = 1; cycle <= ODATIX_CYCLES; cycle++) begin",
    "      " + wait,
  ]
  for port in outputs:
    lines += [
      "      if ($isunknown(" + port.name + ")) begin",
      "        odatix_unknowns++;",
      "        if (odatix_unknowns <= " + str(REPORTED_UNKNOWNS) + ")",
      "          $error(\"output " + port.name + " is unknown at cycle %0d\", cycle);",
      "      end",
    ]
  if stimulus == "random":
    lines += ["      " + port.name + " = " + _sv_value(port, True) + ";" for port in inputs]
  lines += [
    "    end",
    "    $display(\"odatix_cycles: %0d\", ODATIX_CYCLES);",
    "    $finish;",
    "  end",
    "",
    "endmodule",
    "",
  ]
  return "\n".join(lines)


######################################
# VHDL
######################################

def _vhdl_kind(port):
  type_text = port.type.lower()
  base = re.split(r"[\s(]", type_text, maxsplit=1)[0]
  if base in ("std_logic", "std_ulogic"):
    return "bit_std"
  if base == "bit":
    return "bit"
  if base == "boolean":
    return "boolean"
  if base in ("std_logic_vector", "std_ulogic_vector"):
    return "vector"
  if base in ("unsigned", "signed"):
    return base
  if base == "bit_vector":
    return "bit_vector"
  return "other"


def _vhdl_value(port, random):
  kind = _vhdl_kind(port)
  if kind == "bit_std":
    return "odatix_random_bit" if random else "'0'"
  if kind == "bit":
    return "to_bit(odatix_random_bit)" if random else "'0'"
  if kind == "boolean":
    return "odatix_random_bit = '1'" if random else "false"
  vector = "odatix_random_vector(" + port.name + "'length)"
  if kind == "vector":
    return vector if random else "(others => '0')"
  if kind in ("unsigned", "signed"):
    return kind + "(" + vector + ")" if random else "(others => '0')"
  if kind == "bit_vector":
    return "to_bitvector(" + vector + ")" if random else "(others => '0')"
  return None


_TB_CONTEXT = (
  "library ieee;",
  "use ieee.std_logic_1164.all;",
  "use ieee.numeric_std.all;",
  "use ieee.math_real.all;",
)


def generate_vhdl(header, clock="", reset="", reset_active_low=False, cycles=DEFAULT_CYCLES, stimulus="random", waves=True):
  clock_port = header.port(clock) if clock else None
  reset_port = header.port(reset) if reset else None
  inputs = [p for p in header.ports if p.is_input and p not in (clock_port, reset_port) and _vhdl_value(p, False) is not None]
  outputs = [p for p in header.ports if p.is_output and _vhdl_kind(p) in ("bit_std", "vector", "unsigned", "signed")]
  active, inactive = ("'0'", "'1'") if reset_active_low else ("'1'", "'0'")
  if clock_port is not None:
    wait = "wait until falling_edge(" + clock_port.name + ");"
  else:
    wait = "wait for " + str(2 * CLOCK_HALF_PERIOD_NS) + " ns;"

  context = list(_TB_CONTEXT)
  known = {clause.lower().rstrip(";").replace(" ", "") for clause in context}
  for clause in header.context:
    if clause.lower().rstrip(";").replace(" ", "") not in known:
      context.append(clause)

  lines = [
    "-- Generated by Odatix: a minimal testbench for \"" + header.name + "\", which has none.",
    "-- It drives the inputs with " + ("random values" if stimulus == "random" else "zeros")
    + " and checks that no output is unknown once out of reset.",
    "",
  ]
  lines += context
  lines += [
    "",
    "entity " + TOP + " is",
    "end entity " + TOP + ";",
    "",
    "architecture sim of " + TOP + " is",
  ]
  lines += ["  constant " + parameter.declaration + ";" for parameter in header.parameters]
  for port in header.ports:
    initial = ""
    if port is clock_port and _vhdl_kind(port) in ("bit_std", "bit"):
      initial = " := '0'"
    lines.append("  signal " + port.name + " : " + port.type + initial + ";")
  lines += [
    "  constant ODATIX_CYCLES : natural := " + str(int(cycles)) + ";",
    "  signal odatix_running : boolean := true;",
    "begin",
    "",
    "  dut: entity work." + header.name,
    "    port map (",
    ",\n".join("      " + port.name + " => " + port.name for port in header.ports),
    "    );",
    "",
  ]
  if clock_port is not None:
    lines += [
      "  " + clock_port.name + " <= not " + clock_port.name + " after " + str(CLOCK_HALF_PERIOD_NS)
      + " ns when odatix_running else " + clock_port.name + ";",
      "",
    ]
  lines += [
    "  stimulus: process",
    "    variable odatix_seed1 : positive := 1;",
    "    variable odatix_seed2 : positive := 2;",
    "    variable odatix_unknowns : natural := 0;",
    "",
    "    impure function odatix_random_bit return std_logic is",
    "      variable r : real;",
    "    begin",
    "      uniform(odatix_seed1, odatix_seed2, r);",
    "      if r > 0.5 then",
    "        return '1';",
    "      end if;",
    "      return '0';",
    "    end function;",
    "",
    "    impure function odatix_random_vector(n : natural) return std_logic_vector is",
    "      variable v : std_logic_vector(n - 1 downto 0);",
    "    begin",
    "      for i in v'range loop",
    "        v(i) := odatix_random_bit;",
    "      end loop;",
    "      return v;",
    "    end function;",
    "  begin",
  ]
  lines += ["    " + port.name + " <= " + _vhdl_value(port, False) + ";" for port in inputs]
  if reset_port is not None:
    lines.append("    " + reset_port.name + " <= " + active + ";")
  lines += [
    "    for i in 1 to " + str(RESET_CYCLES) + " loop",
    "      " + wait,
    "    end loop;",
  ]
  if reset_port is not None:
    lines.append("    " + reset_port.name + " <= " + inactive + ";")
  lines += [
    "    for cycle in 1 to ODATIX_CYCLES loop",
    "      " + wait,
  ]
  for port in outputs:
    lines += [
      "      if is_x(" + port.name + ") then",
      "        odatix_unknowns := odatix_unknowns + 1;",
      "        if odatix_unknowns <= " + str(REPORTED_UNKNOWNS) + " then",
      "          report \"output " + port.name + " is unknown at cycle \" & integer'image(cycle) severity error;",
      "        end if;",
      "      end if;",
    ]
  if stimulus == "random":
    lines += ["      " + port.name + " <= " + _vhdl_value(port, True) + ";" for port in inputs]
  lines += [
    "    end loop;",
    "    report \"odatix_cycles: \" & integer'image(ODATIX_CYCLES);",
    "    odatix_running <= false;",
    "    wait;",
    "  end process;",
    "",
    "end architecture sim;",
    "",
  ]
  return "\n".join(lines)


######################################
# Writing it
######################################

def write(info, work_dir="."):
  """
  Generate the testbench of a job and write it into its work directory.

  Args:
    info (dict): the content of "odatix_sim.yml".

  Returns:
    (path, top, language): the file written, relative to the work directory,
    the top of the testbench and its language.

  Raises:
    HeaderError: the header of the design cannot be read.
  """
  dut = info.get("dut", {})
  testbench = info.get("testbench", {})
  header = find_top(info, work_dir)
  reset_active_low = dut.get("reset_active_low")
  if reset_active_low is None:
    reset_active_low = design_info.reset_is_active_low(dut.get("reset", ""))
  options = dict(
    clock=dut.get("clock", ""),
    reset=dut.get("reset", ""),
    reset_active_low=bool(reset_active_low),
    cycles=int(testbench.get("cycles") or DEFAULT_CYCLES),
    stimulus=str(testbench.get("stimulus") or "random"),
    waves=bool(testbench.get("waves", True)),
  )
  if header.language == hdl_header.LANGUAGE_VHDL:
    path, language, text = TOP + ".vhd", "vhdl", generate_vhdl(header, **options)
  else:
    path, language, text = TOP + ".sv", "sv", generate_sv(header, **options)
  with open(os.path.join(work_dir, path), "w", encoding="utf-8") as f:
    f.write(text)
  return path, TOP, language
