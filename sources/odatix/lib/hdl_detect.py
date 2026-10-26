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
Guesses the top level module, the clock and the reset of a design from its
HDL sources (Verilog, SystemVerilog, VHDL), for the "auto detect" buttons of
the architecture editor.

This is not a parser: a light reading of the sources finds the modules, their
ports and how they are used, then each guess is scored from two kinds of
evidence:
 - what the code does with a signal (`posedge clk`, `rising_edge(clk)`, the
   second edge of `always @(posedge clk or negedge rst_n)`, `if rst = '1'`
   right before `elsif rising_edge`...), the most reliable when present;
 - its name, split into words (`i_sys_clk`, `ClkIn`, `RAZ_N`...) and matched
   against a vocabulary of several languages and abbreviations, the affixes
   telling a direction or a polarity (`i_`, `_i`, `_n`, `_b`...) being
   neutral and any other word (`clk_en`, `rst_done`) a sign of a derived
   signal.

Each guess comes back as a list of candidates, best first, keeping only those
worth proposing: one clear winner gives a list of one.
"""

import os
import re

HDL_EXTENSIONS = (".v", ".vh", ".sv", ".svh", ".vhd", ".vhdl")
VHDL_EXTENSIONS = (".vhd", ".vhdl")

MAX_FILES = 2000
MAX_FILE_SIZE = 5 * 1024 * 1024

######################################
# Data
######################################

class Port(object):
    def __init__(self, name, direction=None, wide=False):
        self.name = name
        self.direction = direction  # "input", "output", "inout" or None (interface...)
        self.wide = wide            # more than one bit

    def __repr__(self):
        return "Port({0!r}, {1!r}, wide={2})".format(self.name, self.direction, self.wide)


class Unit(object):
    """A Verilog module or a VHDL entity (with the bodies of its architectures)."""

    def __init__(self, name, file, language, ports, body):
        self.name = name
        self.file = file
        self.language = language
        self.ports = ports
        self.body = body

    def port(self, name):
        for port in self.ports:
            if port.name.lower() == name.lower():
                return port
        return None

    def __repr__(self):
        return "Unit({0!r}, {1!r})".format(self.name, self.file)


class Candidate(object):
    def __init__(self, value, score, detail="", file=""):
        self.value = value
        self.score = score
        self.detail = detail
        self.file = file

    def __repr__(self):
        return "Candidate({0!r}, {1:.1f}, {2!r})".format(self.value, self.score, self.detail)

######################################
# Reading the sources
######################################

def _strip_verilog(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.S)  # attributes
    text = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    return text


def _strip_vhdl(text):
    text = re.sub(r"--[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)  # VHDL-2008
    text = re.sub(r'"[^"\n]*"', '""', text)
    return text


def _matching_paren(text, start):
    """Index of the parenthesis closing the one at `start`, -1 if none."""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top(text, sep):
    """`text` split on `sep` outside of any bracket."""
    parts, depth, current = [], 0, []
    for c in text:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(c)
    parts.append("".join(current))
    return [p for p in parts if p.strip()]


_IDENT = r"[A-Za-z_][\w$]*"
_VERILOG_DIRECTIONS = ("input", "output", "inout", "ref")
_VERILOG_SKIPPED = {
    "wire", "reg", "logic", "bit", "var", "signed", "unsigned", "tri", "wand", "wor",
    "integer", "int", "byte", "shortint", "longint", "const", "interconnect",
}


def _verilog_declaration(item):
    """(direction or None, wide, name) of one port declaration, None if not one."""
    item = re.sub(r"=.*$", "", item, flags=re.S).strip()  # default value
    if not item:
        return None
    unpacked = re.search(r"((?:\s*\[[^\]]*\])+)\s*$", item)
    names_part = item[:unpacked.start()] if unpacked else item
    packed = re.findall(r"\[([^\]]*)\]", names_part)
    words = re.findall(r"[\w$.]+", re.sub(r"\[[^\]]*\]", " ", names_part))
    if not words:
        return None
    name = words[-1]
    if not re.match(_IDENT + "$", name):
        return None
    direction = None
    other_types = False
    for word in words[:-1]:
        if word in _VERILOG_DIRECTIONS:
            direction = "input" if word == "ref" else word
        elif word not in _VERILOG_SKIPPED:
            other_types = True  # a struct, an interface, an integer type...
    wide = bool(packed) and not all(re.match(r"\s*0\s*:\s*0\s*$", p) for p in packed)
    if other_types and not packed and direction is None:
        direction = "interface"
    return direction, wide or "integer" in words or "int" in words, name


def _verilog_units(text, path):
    units = []
    for match in re.finditer(r"\b(?:module|macromodule)\s+(?:(?:static|automatic)\s+)?(" + _IDENT + r")", text):
        name = match.group(1)
        end = re.compile(r"\bendmodule\b").search(text, match.end())
        stop = end.start() if end else len(text)
        chunk = text[match.end():stop]

        # Header: optional #(parameters), then the port list, up to ";"
        pos = 0
        header_ports = ""
        m = re.match(r"\s*(?:import\s[^;]*;\s*)*", chunk)
        pos = m.end()
        m = re.match(r"\s*#\s*\(", chunk[pos:])
        if m:
            close = _matching_paren(chunk, pos + m.end() - 1)
            pos = close + 1 if close > 0 else pos
        m = re.match(r"\s*\(", chunk[pos:])
        if m:
            close = _matching_paren(chunk, pos + m.end() - 1)
            if close > 0:
                header_ports = chunk[pos + m.end():close]
                pos = close + 1
        semicolon = chunk.find(";", pos)
        body = chunk[semicolon + 1:] if semicolon >= 0 else chunk[pos:]

        ports = []
        direction, wide = None, False
        for item in _split_top(header_ports, ","):
            declaration = _verilog_declaration(item)
            if declaration is None:
                continue
            item_direction, item_wide, port_name = declaration
            if item_direction is not None:
                direction, wide = item_direction, item_wide
            elif re.search(r"\[", item):
                wide = item_wide
            ports.append(Port(port_name, direction, wide if item_direction is None else item_wide))

        # Non-ANSI headers declare the directions in the body
        if not any(p.direction for p in ports):
            for statement in re.finditer(r"\b(input|output|inout)\b([^;]*);", body):
                for item in _split_top(statement.group(1) + " " + statement.group(2), ","):
                    declaration = _verilog_declaration(item if re.match(r"\s*(input|output|inout)\b", item) else statement.group(1) + " " + item)
                    if declaration is None:
                        continue
                    item_direction, item_wide, port_name = declaration
                    # a list "input [7:0] a, b" shares its width
                    item_wide = item_wide or bool(re.search(r"\[", statement.group(2).split(",")[0]))
                    for port in ports:
                        if port.name == port_name:
                            port.direction, port.wide = item_direction, item_wide
                            break
                    else:
                        ports.append(Port(port_name, item_direction, item_wide))
        units.append(Unit(name, path, "verilog", ports, body))
    return units


_VHDL_ONE_BIT = {"std_logic", "std_ulogic", "bit", "boolean"}


def _vhdl_units(text, path):
    units = []
    lower = text.lower()
    architectures = list(re.finditer(r"\barchitecture\s+\w+\s+of\s+(\w+)\s+is\b", lower))
    for match in re.finditer(r"\bentity\s+(\w+)\s+is\b", lower):
        name = text[match.start(1):match.end(1)]
        end = re.compile(r"\bend\b(?:\s+entity)?(?:\s+" + re.escape(match.group(1)) + r")?\s*;").search(lower, match.end())
        stop = end.start() if end else len(text)
        header = text[match.end():stop]
        ports = []
        port_match = re.search(r"\bport\s*\(", header, flags=re.I)
        if port_match:
            close = _matching_paren(header, port_match.end() - 1)
            for item in _split_top(header[port_match.end():close if close > 0 else len(header)], ";"):
                m = re.match(r"\s*(?:signal\s+)?([\w\s,]+?)\s*:\s*(in|out|inout|buffer|linkage)?\s*(.*)$", item, flags=re.I | re.S)
                if not m:
                    continue
                direction = (m.group(2) or "").lower()
                direction = {"in": "input", "out": "output", "buffer": "output", "inout": "inout"}.get(direction, "interface")
                type_name = re.match(r"\s*([\w.]+)", m.group(3))
                type_name = type_name.group(1).lower().split(".")[-1] if type_name else ""
                wide = type_name not in _VHDL_ONE_BIT
                for port_name in m.group(1).split(","):
                    if port_name.strip():
                        ports.append(Port(port_name.strip(), direction, wide))
        body = ""
        for i, arch in enumerate(architectures):
            if arch.group(1) == match.group(1):
                next_unit = re.compile(r"\b(?:architecture|entity|package|configuration)\b").search(lower, arch.end())
                body += text[arch.end():next_unit.start() if next_unit else len(text)] + "\n"
        units.append(Unit(name, path, "vhdl", ports, body))
    return units


def read_file(path, display_path=None):
    """The units declared in one HDL file."""
    display_path = display_path or path
    try:
        if os.path.getsize(path) > MAX_FILE_SIZE:
            return []
        with open(path, "r", errors="replace") as f:
            text = f.read()
    except (OSError, IOError):
        return []
    if path.lower().endswith(VHDL_EXTENSIONS):
        return _vhdl_units(_strip_vhdl(text), display_path)
    return _verilog_units(_strip_verilog(text), display_path)


def hdl_files(directory):
    """The HDL files under `directory` (relative paths), hidden ones left out."""
    found = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.lower().endswith(HDL_EXTENSIONS) and not name.startswith("."):
                found.append(os.path.relpath(os.path.join(root, name), directory))
                if len(found) >= MAX_FILES:
                    return found
    return found


def read_directory(directory):
    units = []
    for rel in hdl_files(directory):
        units.extend(read_file(os.path.join(directory, rel), rel))
    return units

######################################
# Top level module
######################################

_TESTBENCH_WORDS = {"tb", "testbench", "test", "tests", "bench", "sim", "simulation", "stimulus", "tst", "verif"}


def split_words(name):
    """`i_SysClk2x_n` -> ["i", "sys", "clk", "2", "x", "n"]."""
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    words = []
    for part in re.split(r"[^A-Za-z0-9]+", name):
        words.extend(w.lower() for w in re.findall(r"[A-Za-z]+|[0-9]+", part))
    return words


def is_testbench(unit):
    words = split_words(unit.name)
    lower = unit.name.lower()
    return bool(_TESTBENCH_WORDS.intersection(words)) or lower.startswith("tb") or lower.endswith("tb")


def _instantiated(unit, units):
    """Whether another unit instantiates `unit`."""
    name = re.escape(unit.name)
    verilog = re.compile(r"(?<![\w$.])" + name + r"\s*(?:#\s*\(|" + _IDENT + r"\s*(?:\[[^\]]*\]\s*)?\()")
    vhdl = re.compile(
        r"(?:\bentity\s+\w+\s*\.\s*" + name + r"\b|:\s*(?:component\s+)?" + name + r"\s+(?:generic|port)\s+map\b)",
        re.I,
    )
    for other in units:
        if other is unit:
            continue
        if (vhdl if other.language == "vhdl" else verilog).search(other.body):
            return True
        if other.language == "verilog" and unit.language == "vhdl" and verilog.search(other.body):
            return True
    return False


def _children(unit, units):
    return sum(1 for other in units if other is not unit and _instantiated(other, [unit]))


def top_module_candidates(units, preferred_file="", hints=()):
    """
    The units that may be the top level, best first. `preferred_file` is the
    top level file already chosen, `hints` the names it is likely to bear (the
    architecture name, the directory...).
    """
    if not units:
        return []
    hints = [h.lower() for h in hints if h]
    benches = [u for u in units if is_testbench(u)]
    # a testbench instantiating the top does not make it a submodule
    design = [u for u in units if u not in benches]
    scored = []
    for unit in units:
        score = 0.0
        notes = []
        words = split_words(unit.name)
        is_bench = unit in benches
        if is_bench or not unit.ports:
            score -= 8
            notes.append("testbench" if is_bench else "no port")
        if not _instantiated(unit, design):
            score += 10
        else:
            score -= 5
            notes.append("instantiated elsewhere")
        children = _children(unit, design if not is_bench else units)
        score += min(children, 8) * 0.5
        if "top" in words:
            score += 2
        base = os.path.splitext(os.path.basename(unit.file))[0].lower()
        if base == unit.name.lower():
            score += 1.5
        if preferred_file and os.path.normpath(unit.file) == os.path.normpath(preferred_file):
            score += 6
        if unit.name.lower() in hints:
            score += 3
        score += min(len(unit.ports), 20) * 0.05
        detail = os.path.basename(unit.file)
        if children:
            detail += ", instantiates {0} module{1}".format(children, "s" if children > 1 else "")
        if notes:
            detail += ", " + ", ".join(notes)
        scored.append(Candidate(unit.name, score, detail, unit.file))
    return _keep_relevant(scored, minimum=5)


def _keep_relevant(candidates, minimum, ratio=0.6, fallback=True):
    candidates = sorted(candidates, key=lambda c: (-c.score, c.value.lower()))
    seen = set()
    candidates = [c for c in candidates if not (c.value in seen or seen.add(c.value))]
    if not candidates:
        return []
    best = candidates[0].score
    kept = [c for c in candidates if c.score >= minimum and c.score >= best * ratio]
    if not kept and fallback:
        # nothing convincing: still propose the best ones rather than nothing
        kept = [c for c in candidates[:5] if c.score >= best - 2]
    return kept[:8]

######################################
# Clock and reset
######################################

# Words naming a clock, in several languages, and the abbreviations in use
_CLOCK_WORDS = {
    "clk": 10, "clock": 10, "clck": 9, "clok": 8, "clks": 8, "clocks": 8,
    "horloge": 10, "horl": 8, "hor": 5,         # French
    "takt": 9, "taktsignal": 9,                 # German
    "reloj": 9,                                 # Spanish
    "orologio": 9,                              # Italian
    "relogio": 9,                               # Portuguese
    "klok": 8, "zegar": 8, "kello": 7,          # Dutch, Polish, Finnish
    "ck": 7, "cp": 3, "osc": 4, "xtal": 4, "tck": 7,
}
# Words naming a reset (raz: "remise à zéro", rz...)
_RESET_WORDS = {
    "rst": 10, "reset": 10, "rset": 8, "rstn": 10, "nrst": 10, "rstb": 10, "resetn": 10,
    "nreset": 10, "resetb": 10, "arst": 10, "srst": 10, "areset": 10, "sreset": 10,
    "aresetn": 10, "arstn": 10, "srstn": 10, "presetn": 9, "hresetn": 9,
    "raz": 10, "razn": 10, "nraz": 10, "rz": 6, "remiseazero": 9,  # French
    "reinit": 7, "reinitialisation": 8, "init": 5, "initialisation": 5,
    "ruecksetzen": 8, "rucksetzen": 8,          # German
    "reinicio": 8, "reiniciar": 8,              # Spanish
    "azzeramento": 8, "ripristino": 6,          # Italian
    "por": 6, "clr": 5, "clear": 5, "res": 4, "rs": 3, "rest": 2,
}
# Words that only tell the direction, the polarity, the domain or the kind
# of the signal: they are neutral
_NEUTRAL_WORDS = {
    "i", "in", "inp", "input", "s", "sig", "signal", "w", "p", "port", "pin", "pad", "x",
    "n", "b", "l", "neg", "bar", "not", "low", "lo", "high", "hi", "pos", "active",
    "sys", "system", "main", "core", "global", "glb", "g", "ext", "external", "top",
    "a", "async", "asynchronous", "sync", "synchronous", "hw", "soft", "sw", "hard",
    "master", "m", "ref", "root", "src", "source", "primary", "base", "e", "ent", "entree",
    "general", "gen", "chip", "board", "fpga", "design", "dut", "the", "rtl",
    "h", "f", "d", "mhz", "khz", "ghz", "hz", "domain",
}
# Words of a signal derived from a clock or a reset rather than the signal itself
_DERIVED_WORDS = {
    "en", "ena", "enable", "ce", "gate", "gated", "div", "divider", "divided", "cnt", "count",
    "counter", "sel", "select", "mux", "lock", "locked", "valid", "vld", "ok", "rdy", "ready",
    "done", "req", "request", "ack", "stop", "stopped", "period", "freq", "frequency", "ratio",
    "fb", "feedback", "dbg", "debug", "status", "cfg", "config", "mode", "out", "o", "output",
    "q", "value", "val", "data", "addr", "state", "err", "error", "flag", "detect", "detected",
    "pulse", "edge", "phase", "shift", "busy", "pending", "cause", "vector", "vec", "level",
    "mask", "irq", "int", "tick", "strobe", "stb",
}
# What can be glued to a core word: "iclk", "sysclk", "clkin", "rstn", "hresetn"
_FUSED_AFFIXES = {
    "i", "in", "n", "b", "l", "a", "s", "h", "p", "m", "f", "x", "g", "c", "d", "o",
    "sys", "ext", "ref", "core", "main", "pll", "osc", "an", "sn", "bn", "ref", "top",
    "por", "glb", "hw", "sw",
}
_ACTIVE_LOW = {"n", "b", "l", "neg", "bar", "not", "low", "lo"}


def _name_score(name, vocabulary, fused_cores):
    """How much `name` reads as a word of `vocabulary`, 0 if not at all."""
    words = split_words(name)
    if not words:
        return 0.0
    words = [w for w in words if not w.isdigit()]
    best, core_index = 0.0, None
    for i, word in enumerate(words):
        score = vocabulary.get(word, 0)
        if not score:
            # a core glued to affixes: "iclk", "sysclk", "clkin", "rstn", "hresetn", "nrst"
            for core in fused_cores:
                at = word.find(core)
                if at < 0:
                    continue
                before, after = word[:at], word[at + len(core):]
                parts = [x for x in (before, after) if x]
                if all(x in _FUSED_AFFIXES for x in parts):
                    score = max(score, vocabulary[core] - (1 if parts else 0))
                elif any(x in _DERIVED_WORDS for x in parts):
                    score = max(score, vocabulary[core] - 8)
        if score > best:
            best, core_index = score, i
    if best <= 0:
        return 0.0
    for i, word in enumerate(words):
        if i == core_index:
            continue
        if word in _DERIVED_WORDS:
            best -= 7
        elif word in _NEUTRAL_WORDS or word in vocabulary:
            best -= 0.2
        else:
            best -= 1.5  # an unknown word: "clk_spi", "rst_fifo"... possible, less likely
    return max(best, 0.0)


def _is_active_low(name):
    words = split_words(name)
    if any(w in _ACTIVE_LOW for w in words):
        return True
    lower = name.lower()
    return bool(re.search(r"(rst|reset|raz|res|clr|init)(n|b)\d*$", lower) or re.match(r"^n(rst|reset|raz)", lower))


def _edge_evidence(unit):
    """
    {signal: {"clock": n, "async_reset": n, "sync_reset": n}} from the way the
    body of `unit` uses its signals.
    """
    evidence = {}

    def add(signal, kind, amount=1):
        signal = signal.split(".")[-1].split("[")[0]
        entry = evidence.setdefault(signal.lower(), {"clock": 0, "async_reset": 0, "sync_reset": 0})
        entry[kind] += amount

    body = unit.body
    if unit.language == "verilog":
        for sensitivity in re.finditer(r"@\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)", body):
            edges = re.findall(r"\b(posedge|negedge|edge)\s+([\w$.]+)", sensitivity.group(1))
            if not edges:
                continue
            if len(edges) == 1:
                add(edges[0][1], "clock")
                # synchronous reset: the first test right after the edge
                after = body[sensitivity.end():sensitivity.end() + 200]
                m = re.match(r"\s*(?:begin\s*(?::\s*\w+)?\s*)?if\s*\(\s*(?:!|~)?\s*\(?\s*([\w$]+)", after)
                if m:
                    add(m.group(1), "sync_reset")
                continue
            names = [e[1] for e in edges]
            # the clock among several edges: the best name, else the first
            clock = max(names, key=lambda n: (_name_score(n, _CLOCK_WORDS, _CLOCK_FUSED) - _name_score(n, _RESET_WORDS, _RESET_FUSED), -names.index(n)))
            add(clock, "clock")
            for other in names:
                if other != clock:
                    add(other, "async_reset")
    else:
        for m in re.finditer(r"\b(?:rising_edge|falling_edge)\s*\(\s*(\w+)\s*\)", body, flags=re.I):
            add(m.group(1), "clock")
        for m in re.finditer(r"\b(\w+)\s*'\s*event\b", body, flags=re.I):
            add(m.group(1), "clock")
        for m in re.finditer(
            r"\bif\s*\(?\s*(\w+)\s*=\s*'[01]'\s*\)?\s*then\b((?:(?!\bprocess\b).){0,1500}?)\belsif\s*\(?\s*(?:rising_edge|falling_edge)\s*\(\s*(\w+)",
            body, flags=re.I | re.S,
        ):
            add(m.group(1), "async_reset")
        for m in re.finditer(
            r"(?:rising_edge|falling_edge)\s*\(\s*\w+\s*\)\s*\)?\s*then\s*if\s*\(?\s*(\w+)\s*=\s*'[01]'",
            body, flags=re.I,
        ):
            add(m.group(1), "sync_reset")
    return evidence


_CLOCK_FUSED = ("clock", "clk", "horloge", "takt", "reloj", "ck")
_RESET_FUSED = ("reset", "rst", "raz", "reinit")


def _merge_evidence(units):
    total = {}
    for unit in units:
        for signal, counts in _edge_evidence(unit).items():
            entry = total.setdefault(signal, {"clock": 0, "async_reset": 0, "sync_reset": 0})
            for k, v in counts.items():
                entry[k] += v
    return total


def _signal_candidates(unit, units, kind):
    """`kind`: "clock" or "reset"."""
    own = _edge_evidence(unit)
    others = _merge_evidence([u for u in units if u is not unit])
    candidates = []
    for port in unit.ports:
        if port.direction not in ("input", "inout"):
            continue
        key = port.name.lower()
        mine = own.get(key, {"clock": 0, "async_reset": 0, "sync_reset": 0})
        theirs = others.get(key, {"clock": 0, "async_reset": 0, "sync_reset": 0})
        clock_name = _name_score(port.name, _CLOCK_WORDS, _CLOCK_FUSED)
        reset_name = _name_score(port.name, _RESET_WORDS, _RESET_FUSED)
        notes = []
        if kind == "clock":
            score = clock_name
            if mine["clock"]:
                score += 8 + min(mine["clock"], 10) * 0.3
                notes.append("used as a clock edge")
            elif theirs["clock"]:
                score += 4
                notes.append("clock edge in a submodule")
            score -= reset_name * 0.8
            score -= 6 * bool(mine["async_reset"])
        else:
            score = reset_name
            if mine["async_reset"]:
                score += 8
                notes.append("asynchronous reset")
            elif theirs["async_reset"]:
                score += 4
                notes.append("asynchronous reset in a submodule")
            if mine["sync_reset"] or theirs["sync_reset"]:
                # also any enable tested first: only counts along with a name
                score += (4 if mine["sync_reset"] else 2) if reset_name else 0.5
                if reset_name:
                    notes.append("synchronous reset")
            score -= clock_name * 0.8
            score -= 8 * bool(mine["clock"])
            if score > 0 and _is_active_low(port.name):
                notes.append("active low")
        if port.wide:
            score -= 8
            notes.append("several bits")
        if port.direction == "inout":
            score -= 2
        if score > 0:
            candidates.append(Candidate(port.name, score, ", ".join(notes)))
    return _keep_relevant(candidates, minimum=6, ratio=0.7, fallback=False)


def clock_candidates(unit, units=()):
    return _signal_candidates(unit, list(units) or [unit], "clock")


def reset_candidates(unit, units=()):
    return _signal_candidates(unit, list(units) or [unit], "reset")


def find_unit(units, name, preferred_file=""):
    matches = [u for u in units if u.name.lower() == (name or "").lower()]
    if preferred_file:
        preferred = [u for u in matches if os.path.normpath(u.file) == os.path.normpath(preferred_file)]
        matches = preferred or matches
    return matches[0] if matches else None

######################################
# Parameters
######################################

class Parameter(object):
    """
    A parameter declared in a file: its name, its value as written, and where
    that value is in the text (`start`, `end`), so a template can put a
    variable in its place.
    """
    def __init__(self, name, value, start, end, kind):
        self.name = name
        self.value = value
        self.start = start
        self.end = end
        self.kind = kind  # "parameter", "localparam", "generic", "constant", "define", "variable", "argument"

    @property
    def overridable(self):
        """Whether the design expects it to be set from outside."""
        return self.kind in ("parameter", "generic", "define", "argument")

    def __repr__(self):
        return "Parameter({0!r}, {1!r}, {2!r})".format(self.name, self.value, self.kind)


def _blank(text, pattern, flags=0):
    """`text` with what `pattern` matches turned into spaces, line breaks kept."""
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=flags)


def _value_end(text, start, stops):
    """Where a value starting at `start` ends: the first of `stops` outside brackets."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif c == '"':
            close = text.find('"', i + 1)
            i = close if close > 0 else i
        elif depth == 0 and c in stops:
            return i
        i += 1
    return len(text)


def _parameter(text, name, start, stops, kind):
    end = _value_end(text, start, stops)
    value = text[start:end]
    stripped = value.rstrip()
    end -= len(value) - len(stripped)
    lead = len(stripped) - len(stripped.lstrip())
    return Parameter(name, stripped.strip(), start + lead, end, kind)


_SV_TYPES = r"(?:\s+(?:int|integer|logic|bit|reg|signed|unsigned|real|realtime|string|longint|shortint|byte|time|unsigned)\b|\s*\[[^\]]*\])*"


def _verilog_parameters(text):
    found = []
    for m in re.finditer(r"\b(parameter|localparam)\b(?!\s+type\b)" + _SV_TYPES + r"\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)?=", text):
        kind = m.group(1)
        param = _parameter(text, m.group(2), m.end(), ",;)", kind)
        found.append(param)
        # "parameter A = 1, B = 2": the next ones share the keyword
        pos = param.end
        while True:
            more = re.compile(r"\s*,\s*([A-Za-z_]\w*)\s*=").match(text, pos)
            if not more:
                break
            param = _parameter(text, more.group(1), more.end(), ",;)", kind)
            found.append(param)
            pos = param.end
    for m in re.finditer(r"^[ \t]*`define[ \t]+([A-Za-z_]\w*)[ \t]+", text, flags=re.M):
        found.append(_parameter(text, m.group(1), m.end(), "\n", "define"))
    return found


def _vhdl_parameters(text):
    found = []
    for m in re.finditer(r"\bgeneric\s*\(", text, flags=re.I):
        close = _matching_paren(text, m.end() - 1)
        close = close if close > 0 else len(text)
        for item in re.finditer(r"(?:^|;)\s*(?:constant\s+)?([A-Za-z]\w*(?:\s*,\s*[A-Za-z]\w*)*)\s*:\s*(?:in\s+)?[^:;=]*?:=", text[m.end():close], flags=re.I):
            start = m.end() + item.end()
            for name in item.group(1).split(","):
                found.append(_parameter(text, name.strip(), start, ";)", "generic"))
    for m in re.finditer(r"\bconstant\s+([A-Za-z]\w*)\s*:\s*[^:;=]*?:=", text, flags=re.I):
        found.append(_parameter(text, m.group(1), m.end(), ";", "constant"))
    return found


def _matches(text, pattern, stops, kind, flags=re.M):
    return [_parameter(text, m.group(1), m.end(), stops, kind) for m in re.finditer(pattern, text, flags)]


def _c_parameters(text):
    """C, C++ (HLS), Bluespec, SystemC: #define and typed constants."""
    return (
        _matches(text, r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+(?=\S)", "\n", "define")
        + _matches(text, r"\b(?:static\s+)?(?:constexpr|const)\s+(?:unsigned\s+|signed\s+)?[\w:<>,]+\s+([A-Za-z_]\w*)\s*=\s*", ";", "constant")
        + _matches(text, r"^[ \t]*(?:Integer|Bit#\(\d+\)|UInt#\(\d+\)|Int#\(\d+\)|Bool)\s+([A-Za-z_]\w*)\s*=\s*", ";", "constant")
    )


def _scala_parameters(text):
    """Chisel, SpinalHDL: the arguments of a class with a default, and vals."""
    return (
        _matches(text, r"(?:[(,]|^)\s*(?:(?:override\s+)?(?:val|var)\s+)?([A-Za-z_]\w*)\s*:\s*[\w.\[\]]+\s*=\s*(?!>)", ",)\n", "parameter")
        + _matches(text, r"^\s*(?:(?:private|protected|final|lazy|override)\s+)*val\s+([A-Za-z_]\w*)\s*(?::\s*[\w.\[\]]+\s*)?=\s*(?!>)", ";\n", "constant")
    )


def _python_parameters(text):
    """Amaranth, MyHDL, cocotb, Migen: keyword arguments with a default, and constants."""
    return (
        _matches(text, r"(?:[(,]|^)\s*([A-Za-z_]\w*)\s*(?::\s*[\w.\[\]]+\s*)?=(?!=)\s*", ",)\n", "parameter")
    )


def _haskell_parameters(text):
    """Clash: type-level sizes and top-level constants."""
    return (
        _matches(text, r"^type\s+([A-Z]\w*)\s*=\s*", "\n", "parameter")
        + _matches(text, r"^([a-z_]\w*)\s*=\s*", "\n", "constant")
    )


def _config_parameters(text):
    """Tcl, Makefile, YAML, JSON, .ini, shell: what configures a flow."""
    return (
        _matches(text, r"^[ \t]*set[ \t]+([A-Za-z_][\w:]*)[ \t]+(?=\S)", ";\n", "variable")
        + _matches(text, r"^[ \t]*(?:export[ \t]+)?([A-Za-z_]\w*)[ \t]*[?:+]?=[ \t]*(?=\S)", "\n", "variable")
        + _matches(text, r"^[ \t]*([A-Za-z_][\w-]*)[ \t]*:[ \t]+(?=\S)", "\n", "variable")
        + _matches(text, r'"([A-Za-z_][\w-]*)"\s*:\s*', ",}\n", "variable")
    )


def _argument_parameters(text):
    """
    Named arguments of an instantiation or a call: ".WIDTH(8)" (Verilog),
    "WIDTH => 8" (VHDL), "width = 16" (Scala, Python...). Kept only with a
    literal value, which tells them from port connections.
    """
    return (
        _matches(text, r"\.([A-Za-z_]\w*)\s*\(\s*", ")", "argument", 0)
        + _matches(text, r"\b([A-Za-z_]\w*)\s*=>\s*", ",)", "argument", 0)
        + _matches(text, r"[(,]\s*([A-Za-z_]\w*)\s*=(?![=>])\s*", ",)", "argument", 0)
    )


_LANGUAGES = [
    ((".v", ".vh", ".sv", ".svh", ".vlg", ".verilog"), _verilog_parameters, "//"),
    (VHDL_EXTENSIONS, _vhdl_parameters, "--"),
    ((".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".bsv", ".bs"), _c_parameters, "//"),
    ((".scala", ".sc"), _scala_parameters, "//"),
    ((".py",), _python_parameters, "#"),
    ((".hs", ".lhs"), _haskell_parameters, "--"),
    ((".tcl", ".xdc", ".sdc", ".mk", ".yml", ".yaml", ".json", ".ini", ".cfg", ".conf", ".sh", ".env"), _config_parameters, "#"),
]
_GENERIC = (_verilog_parameters, _c_parameters, _config_parameters)

_LITERAL = re.compile(
    r"""^(?:[-+]?(?:\d[\d_]*(?:\.\d+)?(?:[eE][-+]?\d+)?|0[xX][\da-fA-F_]+|0[bB][01_]+)[uUlLfF]*"""
    r"""|\d*\s*'[sS]?[bBoOdDhH]\s*[\da-fA-FxXzZ_?]+"""          # 8'hFF
    r"""|[xXbBoO]?"[\da-fA-F_]*"|'[01]'"""                       # x"FF", '1'
    r"""|\d+(?:\.\d+)?\s*(?:ns|ps|us|ms|MHz|kHz|GHz|Hz)"""
    r"""|"[^"\n]*"|'[^'\n]*'|true|false|True|False|TRUE|FALSE|yes|no"""
    r"""|\d+\.U(?:\(\d+\.W\))?|\d+\.W)$"""
)


#: Words some patterns take for a name and are not one: "others => '0'"...
_NOT_PARAMETERS = {
    "others", "open", "if", "for", "while", "case", "when", "return", "assert", "print", "println",
    "require", "else", "begin", "end", "default", "self", "this", "super", "true", "false",
}


def is_literal(value):
    return bool(_LITERAL.match(value.strip()))


def _strip_comments(text, comment):
    text = _blank(text, r"/\*.*?\*/", re.S) if comment == "//" else text
    if comment == "--":
        text = _blank(text, r"\{-.*?-\}", re.S)
    if comment == "#":
        text = _blank(text, r'"""[\s\S]*?"""')
        # "#define" is not a comment
        return _blank(text, r"(?<![\w\\])#(?![ \t]*(?:define|include|if|endif|else|undef|pragma)\b)[^\n]*")
    return _blank(text, re.escape(comment) + r"[^\n]*")


def detect_parameters(text, filename="", section=None):
    """
    The parameters declared in `text` (the content of `filename`), in order,
    each name once. The language is told by the extension; an unknown one is
    read as several, keeping only literal values. `section` = (start, end)
    keeps only those whose value lies inside it: the part a domain replaces.
    """
    lower = filename.lower()
    readers = None
    for extensions, reader, comment in _LANGUAGES:
        if lower.endswith(extensions):
            readers, blanked = (reader,), _strip_comments(text, comment)
            break
    if readers is None:
        readers, blanked = _GENERIC, _strip_comments(_strip_comments(text, "//"), "#")
    found = []
    for reader in readers + (_argument_parameters,):
        found.extend(reader(blanked))
    known = readers != _GENERIC and readers[0] not in (_python_parameters, _haskell_parameters, _config_parameters, _scala_parameters)
    seen = set()
    kept = []
    for param in sorted(found, key=lambda p: (p.start, p.end)):
        if section is not None and not (section[0] <= param.start and param.end <= section[1]):
            continue
        # "A, B : natural := 3" gives both the same value: one place to template
        if param.name in seen or param.start in seen or not param.value or param.name.lower() in _NOT_PARAMETERS:
            continue
        param.value = text[param.start:param.end]
        # where anything can be an assignment, only literals are parameters
        if (not known or param.kind == "argument") and not is_literal(param.value):
            continue
        seen.add(param.name)
        seen.add(param.start)
        kept.append(param)
    if not kept and section is not None:
        kept = _positional_arguments(text, blanked, section)
    if section is None:
        # calls passing literals to what the file declares: "new ALUTop(8)"
        for param in _call_arguments(text, blanked):
            if param.name not in seen and param.start not in seen:
                seen.add(param.name)
                seen.add(param.start)
                kept.append(param)
        kept.sort(key=lambda p: p.start)
    return kept


def _call_arguments(text, blanked):
    found = []
    for m in re.finditer(r"(?<![\w.])(?:new\s+)?([A-Za-z_]\w*)\s*(?:#\s*)?\(", blanked):
        callee = m.group(1)
        before = blanked[max(0, m.start() - 30):m.start()]
        if re.search(r"\b(?:class|object|def|module|entity|struct|void|int)\s*$", before):
            continue  # the declaration itself
        if callee in _NOT_PARAMETERS or not re.search(
            r"\b(?:class|object|def|module|entity|struct)\s+" + re.escape(callee) + r"\b", blanked
        ):
            continue
        close = _matching_paren(blanked, m.end() - 1)
        if close < 0:
            continue
        found.extend(_positional_arguments(text, blanked, (m.end(), close)))
    return found


def _signature_names(blanked, callee):
    """The parameter names `callee` is declared with in the file, in order."""
    callee = re.escape(callee)
    for pattern in (
        r"\b(?:class|object|def|case\s+class)\s+" + callee + r"\s*(?:\[[^\]]*\])?\s*\(",  # Scala, Python
        r"\bmodule\s+" + callee + r"\s*#\s*\(",                                                # Verilog
        r"\bentity\s+" + callee + r"\s+is\s+generic\s*\(",                                   # VHDL
        r"\b(?:struct|class)\s+" + callee + r"\s*\(",
        r"(?<![\w.])" + callee + r"\s*\((?=[^()]*:)",                                               # typed "name: T"
        r"\b[A-Za-z_][\w:<>]*[\s*&]+" + callee + r"\s*\((?=[^()]*[A-Za-z_]\w*\s+[A-Za-z_*&])",          # C, C++
    ):
        m = re.search(pattern, blanked, flags=re.I)
        if not m:
            continue
        close = _matching_paren(blanked, m.end() - 1)
        if close < 0:
            continue
        names = []
        for item in _split_top(blanked[m.end():close], ";" if "entity" in pattern else ","):
            item = re.sub(r"^\s*(?:parameter|localparam|val|var|implicit|self)\b", "", item.strip())
            words = re.findall(r"[A-Za-z_]\w*", item.split("=")[0].split(":")[0])
            if words and words[-1] not in ("int", "integer", "Int", "logic"):
                names.append(words[-1] if ":" in item or "=" not in item else words[0])
            elif words:
                names.append(words[0])
        if names:
            return names
    return []


def _positional_arguments(text, blanked, section):
    """
    The literal values between the delimiters when nothing names them: the
    arguments of a call or an instantiation ("new ALUTop(8)"). Each is named
    after the parameter of the callee at its position when the file declares
    it, "param1", "param2"... otherwise.
    """
    start, end = section
    before = blanked[max(0, start - 300):start]
    callee = (
        # VHDL: "u: entity work.alu generic map (" / "u: alu generic map ("
        re.search(r"(?:entity\s+\w+\s*\.\s*|:\s*(?:component\s+)?)([A-Za-z]\w*)\s+generic\s+map\s*\(?\s*$", before, flags=re.I)
        or re.search(r"([A-Za-z_]\w*)\s*(?:#\s*)?\(?\s*$", before)
    )
    names = _signature_names(blanked, callee.group(1)) if callee else []
    found = []
    pos = start
    index = 0
    while pos < end:
        stop = min(_value_end(blanked, pos, ","), end)
        value = text[pos:stop]
        lead = len(value) - len(value.lstrip())
        stripped = value.strip()
        if stripped and is_literal(stripped):
            name = names[index] if index < len(names) else "param{0}".format(index + 1)
            found.append(Parameter(name, stripped, pos + lead, pos + lead + len(stripped), "argument"))
        index += 1
        pos = stop + 1
    return found


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def parameter_relevance(param, parameters=()):
    """
    How likely `param` is to be explored, 0 to 10: what the design expects to be
    set from outside, with a plain value, comes first; what is computed from
    other parameters, or kept local, last.
    """
    score = 5.0
    if param.overridable or param.kind == "variable":
        score += 2
    if param.kind == "localparam":
        score -= 4
    value = param.value.strip()
    if is_literal(value):
        score += 2
        if re.match(r"^[-+]?\d", value) or "'" in value:
            score += 1
    else:
        score -= 2
    names = set(p.name for p in parameters if p is not param)
    if any(re.search(r"\b" + re.escape(n) + r"\b", value) for n in names):
        score -= 4  # derived from another parameter
    if param.name.isupper() or param.name[:1].isupper():
        score += 0.5
    return max(0.0, min(10.0, score))


def parameter_template(text, section, parameters):
    """
    The content template of a domain: the replaced section of `text` as it is,
    with the value of each of `parameters` (inside it) turned into ${name}.
    """
    start, end = section
    pieces = []
    pos = start
    for param in sorted(parameters, key=lambda p: p.start):
        if param.start < pos or param.end > end:
            continue
        pieces.append(text[pos:param.start])
        pieces.append("${" + param.name + "}")
        pos = param.end
    pieces.append(text[pos:end])
    return "".join(pieces)


######################################
# Delimiters
######################################

def _isolates(text, start_delimiter, stop_delimiter, start, end):
    """
    Whether a run, which replaces from the first `start_delimiter` of the file
    to the first `stop_delimiter` after it, replaces exactly text[start:end].
    """
    at = text.find(start_delimiter)
    if at < 0 or at + len(start_delimiter) != start:
        return False
    return text.find(stop_delimiter, start) == end


def auto_delimiters(text, start, end, name="", max_back=400):
    """
    The shortest delimiters around text[start:end] (a value) that a run would
    replace exactly: the start one ends right before the value and begins on a
    word boundary ("WIDTH = ", "parameter WIDTH = "...), going back as far as
    needed to be the first of its kind in the file; the stop one is what
    follows the value, up to the end of its line. None when there is none.
    """
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end
    stops = [text[end:end + k] for k in range(1, max(1, line_end - end) + 1)]
    if line_end < len(text):
        stops.append(text[end:line_end + 1])  # up to and including the line break
    stops = [s for s in stops if s.strip() or s == "\n" or s.endswith("\n")] or stops
    # Readable first: a start delimiter naming the parameter ("WIDTH = ")
    # says what it stands for, a bare "= " does not.
    for needs_name in ((True, False) if name else (False,)):
        for begin in range(start - 1, max(-1, start - max_back - 1), -1):
            candidate = text[begin:start]
            if not candidate.strip() or text[begin].isspace():
                continue
            # start on a word boundary, never in the middle of a name
            if begin > 0 and _word(text[begin - 1]) and _word(text[begin]):
                continue
            if needs_name:
                # the name only counts on the line of the value
                if "\n" in candidate:
                    break
                if not re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", candidate):
                    continue
            for stop in stops:
                if _isolates(text, candidate, stop, start, end):
                    return candidate, stop
    return None


def _word(c):
    return c.isalnum() or c == "_"
