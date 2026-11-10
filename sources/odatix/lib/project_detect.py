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
Detects an existing HDL project, for "odatix init --detect": its sources in
compilation order, include directories, macros, top level, clock, reset and
parameters, the generator it may use, the tools of the machine.

Sources, by order of reliability:
 1. what the project declares: file lists (.f, .vc), Bender.yml, FuseSoC
    cores, LibreLane configurations, Vivado projects and scripts, Quartus
    settings, cocotb makefiles, Design Compiler / Genus scripts;
 2. otherwise, the RTL itself: the hierarchy under the most likely top level,
    the packages it imports, the files it includes, in dependency order;
 3. then an elaboration by a real tool (slang, Verilator, Yosys or GHDL),
    whose errors are fixed where the project holds the answer: a module or a
    package defined by a file not listed yet, an include file in a directory
    not given yet.

Every finding tells where it comes from ("origin"), so that a report can tell
what was declared from what was guessed. Nothing is written here.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import odatix.lib.hdl_detect as hdl_detect
import odatix.lib.rtl_generation as rtl_generation
import odatix.sim.design_info as design_info

HDL_EXTENSIONS = (".v", ".sv", ".vhd", ".vhdl")

#: First line of the file list "odatix init --detect" writes: never read back as a declaration.
GENERATED_FILELIST_MARK = "# Written by \"odatix init --detect\""
HEADER_EXTENSIONS = (".vh", ".svh", ".vinc", ".inc")
VHDL_EXTENSIONS = (".vhd", ".vhdl")

MAX_FILES = 20000
MAX_DEPTH = 12

#: Directories never searched: version control, build outputs, Odatix itself.
SKIPPED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "work", "build", "_build", "obj_dir", "sim_build", "runs", ".Xil", "xsim.dir",
    "odatix_userconfig", "odatix_work", "odatix_results", "results", "reports",
}

#: Directory names holding verification code rather than the design.
TESTBENCH_DIRS = {
    "tb", "tbs", "test", "tests", "testbench", "testbenches", "bench", "sim", "simulation",
    "verif", "verification", "dv", "tb_files", "cocotb", "formal", "fv", "sva", "bhv", "uvm",
}

#: Executables telling an Odatix tool is installed: (tool, executables).
TOOL_EXECUTABLES = (
    ("vivado", ("vivado",)),
    ("design_compiler", ("dc_shell",)),
    ("dc_nxt", ("dcnxt_shell",)),
    ("fusion_compiler", ("fc_shell",)),
    ("genus", ("genus",)),
    ("innovus", ("innovus",)),
    ("quartus", ("quartus_sh",)),
    ("yosys_fpga", ("yosys", "nextpnr-ecp5")),
    ("yosys", ("yosys",)),
    ("librelane", ("librelane",)),
    ("verilator", ("verilator",)),
    ("icarus", ("iverilog",)),
    ("ghdl", ("ghdl",)),
    ("questa", ("vsim",)),
)

#: Preference for the default tool among those installed: synthesis first.
DEFAULT_TOOL_ORDER = ("vivado", "design_compiler", "genus", "quartus", "yosys_fpga", "yosys", "librelane")

#: Prefixes of vendor primitives and cells: black boxes, never searched.
_PRIMITIVE = re.compile(
    r"^(?:IBUF|OBUF|IOBUF|BUFG|BUFH|BUFR|MMCM|PLL|DSP48|RAMB\d|FD[CPRSE]|LUT\d|CARRY\d|SRL|IDDR|ODDR|XPM_|xpm_"
    r"|altsyncram|altpll|lpm_|altera_|cyclone|stratix|arria|SB_|EHXPLL|DP16KD|TRELLIS_|ALU54|MULT18"
    r"|sky130_|gf180mcu_|ihp_|sg13g2_|DFF|SDFF)"
)

_VERILOG_KEYWORDS = set("""
always always_comb always_ff always_latch and assert assign assume automatic begin bind buf bufif0 bufif1
case casex casez cell class clocking cmos config const constraint context cover covergroup coverpoint cross deassign
default defparam design disable dist do edge else end endcase endclass endclocking endconfig endfunction endgenerate
endgroup endinterface endmodule endpackage endprimitive endprogram endproperty endspecify endsequence endtable endtask
enum event expect export extends extern final first_match for force foreach forever fork forkjoin function generate
genvar if iff ifnone ignore_bins illegal_bins import incdir include initial inout input inside instance int integer
interface intersect join join_any join_none large liblist library local localparam logic longint macromodule matches
medium modport module nand negedge new nmos nor noshowcancelled not notif0 notif1 null or output package packed parameter
pmos posedge primitive priority program property protected pull0 pull1 pulldown pullup pulsestyle_onevent
pulsestyle_ondetect pure rand randc randcase randsequence rcmos real realtime ref reg release repeat return rnmos rpmos
rtran rtranif0 rtranif1 scalared sequence shortint shortreal showcancelled signed small solve specify specparam static
string strong0 strong1 struct super supply0 supply1 table tagged task this throughout time timeprecision timeunit tran
tranif0 tranif1 tri tri0 tri1 triand trior trireg type typedef union unique unique0 unsigned use uwire var vectored
virtual void wait wait_order wand weak0 weak1 while wildcard wire with within wor xnor xor bit byte
""".split())

_IDENT = r"[A-Za-z_][\w$]*"

######################################
# Data
######################################

class Finding(object):
    """A value found, where it comes from and how sure it is."""

    def __init__(self, value, origin, confidence="guessed", alternatives=()):
        self.value = value
        self.origin = origin                # "Bender.yml", "inferred", "given"...
        self.confidence = confidence        # "declared", "inferred", "guessed" or "given"
        self.alternatives = list(alternatives)

    def to_dict(self):
        return {"value": self.value, "origin": self.origin, "confidence": self.confidence,
                "alternatives": list(self.alternatives)}

    def __repr__(self):
        return "Finding({0!r}, {1!r})".format(self.value, self.origin)


class DeclaredSources(object):
    """What one project file declares about the sources."""

    def __init__(self, origin, path, files=(), include_dirs=(), defines=(), top="", clock="", notes=()):
        self.origin = origin          # kind: "file list", "Bender", "FuseSoC"...
        self.path = path              # the declaring file
        self.files = list(files)      # absolute paths, in order
        self.include_dirs = list(include_dirs)
        self.defines = list(defines)
        self.top = top
        self.clock = clock
        self.notes = list(notes)

    @property
    def label(self):
        return "{0} ({1})".format(self.origin, os.path.basename(self.path))

    def score(self):
        existing = [f for f in self.files if os.path.isfile(f)]
        if not existing:
            return 0.0
        ratio = float(len(existing)) / len(self.files)
        bench = sum(1 for f in existing if _in_testbench_dir(f))
        score = len(existing) * ratio - 2 * bench
        score *= _ORIGIN_WEIGHT.get(self.origin, 1.0)
        if _in_testbench_dir(self.path):
            score *= 0.5
        parts = [p.lower() for p in _parts(self.path)]
        if set(parts) & {"vendor", "third_party", "thirdparty", "external", "deps", "submodules", "boards", "board"}:
            score *= 0.25
        return score

    def __repr__(self):
        return "DeclaredSources({0!r}, {1} files)".format(self.label, len(self.files))


#: How much a kind of declaration is trusted over another, the counts being equal.
_ORIGIN_WEIGHT = {
    "Bender": 1.3, "FuseSoC": 1.3, "file list": 1.2, "Vivado project": 1.15, "Quartus project": 1.15,
    "LibreLane": 1.1, "Vivado script": 1.0, "synthesis script": 1.0, "makefile": 0.9,
}


class FileInfo(object):
    """What one HDL file defines and uses."""

    def __init__(self, path):
        self.path = path
        self.language = "vhdl" if path.lower().endswith(VHDL_EXTENSIONS) else "verilog"
        self.units = []          # hdl_detect.Unit
        self.packages = set()    # packages defined
        self.imports = set()     # packages used
        self.instances = set()   # modules / entities instantiated
        self.includes = []       # include files named
        self.macros_defined = set()
        self.macros_tested = set()   # `ifdef X / `ifndef X / `elsif X
        self.macros_used = set()     # `X
        self.interfaces = set()      # SystemVerilog interfaces defined

    @property
    def modules(self):
        return set(u.name for u in self.units)

    @property
    def is_testbench(self):
        return bool(self.units) and all(hdl_detect.is_testbench(u) or not u.ports for u in self.units) \
            or _in_testbench_dir(self.path) and not any(u.ports for u in self.units)


class Validation(object):
    def __init__(self, tool="", ok=None, errors=(), fixes=(), command=""):
        self.tool = tool          # elaborating tool, "" when none could run
        self.ok = ok              # True, False, or None when not run
        self.errors = list(errors)
        self.fixes = list(fixes)  # what was added to make it elaborate
        self.command = command

    def to_dict(self):
        return {"tool": self.tool, "ok": self.ok, "errors": self.errors, "fixes": self.fixes, "command": self.command}


class ProjectDetection(object):
    """Everything found about a project. Paths are absolute."""

    def __init__(self, root):
        self.root = root
        self.origin = ""                 # what gave the file list
        self.declarations = []           # DeclaredSources found, best first
        self.files = []                  # in compilation order
        self.include_dirs = []
        self.defines = []
        self.top = None                  # Finding
        self.top_file = ""
        self.tops = []                   # hdl_detect.Candidate
        self.units = []                  # hdl_detect.Unit of the design: what the top level may be
        self.clock = None                # Finding
        self.reset = None                # Finding
        self.parameters = []             # hdl_detect.Parameter of the top
        self.optional_macros = []        # tested, never defined: choices to make
        self.undefined_macros = []       # used, never defined: required
        self.black_boxes = []            # instantiated, defined nowhere
        self.duplicates = {}             # module -> files defining it
        self.variants = {}               # package -> files defining it: one kept, the others are choices
        self.generator = None            # rtl_generation.Generation, when the RTL is generated
        self.generated_dir = ""          # where the generated RTL is, once generated (in a temporary copy)
        self.tools = []                  # installed Odatix tools
        self.pdks = []
        self.validation = Validation()
        self.notes = []

    @property
    def languages(self):
        found = set()
        for path in self.files:
            lower = path.lower()
            found.add("vhdl" if lower.endswith(VHDL_EXTENSIONS) else "sv" if lower.endswith(".sv") else "verilog")
        return sorted(found)

    @property
    def needs_generation(self):
        """Whether the RTL found is not enough and the generator must run: no HDL, or HDL that does not elaborate."""
        return bool(self.generator) and not self.generated_dir and (not self.files or self.validation.ok is False)

    @property
    def default_tool(self):
        for tool in DEFAULT_TOOL_ORDER:
            if tool in self.tools:
                return tool
        return ""

    def to_dict(self):
        def rel(path):
            return _relative(path, self.root)
        return {
            "root": self.root,
            "origin": self.origin,
            "declarations": [{"origin": d.origin, "path": rel(d.path), "files": len(d.files)} for d in self.declarations],
            "files": [rel(f) for f in self.files],
            "include_dirs": [rel(d) for d in self.include_dirs],
            "defines": list(self.defines),
            "top": self.top.to_dict() if self.top else None,
            "top_file": rel(self.top_file) if self.top_file else "",
            "top_candidates": [{"value": c.value, "score": round(c.score, 2), "detail": c.detail} for c in self.tops],
            "clock": self.clock.to_dict() if self.clock else None,
            "reset": self.reset.to_dict() if self.reset else None,
            "parameters": [{"name": p.name, "value": p.value.strip(), "kind": p.kind} for p in self.parameters],
            "optional_macros": list(self.optional_macros),
            "undefined_macros": list(self.undefined_macros),
            "black_boxes": list(self.black_boxes),
            "duplicates": {name: [rel(f) for f in files] for name, files in self.duplicates.items()},
            "variants": {name: [rel(f) for f in files] for name, files in self.variants.items()},
            "generator": self.generator.to_dict() if self.generator else None,
            "generated_dir": self.generated_dir,
            "needs_generation": self.needs_generation,
            "tools": list(self.tools),
            "default_tool": self.default_tool,
            "pdks": list(self.pdks),
            "validation": self.validation.to_dict(),
            "notes": list(self.notes),
        }

######################################
# Helpers
######################################

def _relative(path, root):
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:  # another drive (Windows)
        return path


def _unique(items):
    return list(dict.fromkeys(items))


def _parts(path):
    return [p.lower() for p in os.path.normpath(path).split(os.sep)]


def _in_testbench_dir(path):
    return any(p in TESTBENCH_DIRS for p in _parts(os.path.dirname(path)))


def _is_hdl(path):
    return path.lower().endswith(HDL_EXTENSIONS)


def walk(root, extensions=None, max_depth=MAX_DEPTH):
    """The files under `root` (absolute paths, sorted), skipping build and VCS directories."""
    found = []
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.count(os.sep) - base_depth
        dirnames[:] = sorted(
            d for d in dirnames
            if not d.startswith(".") and d not in SKIPPED_DIRS and depth < max_depth
        )
        for name in sorted(filenames):
            if extensions is None or name.lower().endswith(extensions):
                found.append(os.path.join(dirpath, name))
                if len(found) >= MAX_FILES:
                    return found
    return found


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, IOError):
        return ""


def _expand_glob(pattern):
    if any(c in pattern for c in "*?["):
        return sorted(glob.glob(pattern, recursive=True))
    return [pattern]


def _abs(path, base):
    path = os.path.expanduser(path)
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(base, path))

######################################
# Reading the HDL files
######################################

def _strip_comments(text, vhdl):
    if vhdl:
        return re.sub(r"--[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


#: Macros guarding code that only verification compiles: what they guard is not the design.
_VERIFICATION_MACROS = re.compile(r"^(?:FORMAL|SIMULATION|SIM|VERILATOR|COCOTB_SIM|RVFI|ASSERTIONS?|ASSERT_ON|TB|TESTBENCH|SV_ASSERTION)$")


def _strip_verification(text):
    """
    `text` without the code only verification compiles: what `ifdef FORMAL
    guards, or the `else of an `ifndef FORMAL (nested blocks included).
    """
    out, stack = [], []   # per level: [guarded by a verification macro, negated, in its else]
    for line in text.split("\n"):
        m = re.match(r"\s*`(ifdef|ifndef|elsif|else|endif)\b\s*(\w*)", line)
        if m:
            kind, name = m.group(1), m.group(2)
            if kind in ("ifdef", "ifndef"):
                stack.append([bool(_VERIFICATION_MACROS.match(name)), kind == "ifndef", False])
            elif kind == "elsif" and stack:
                stack[-1] = [bool(_VERIFICATION_MACROS.match(name)), False, False]
            elif kind == "else" and stack:
                stack[-1][2] = True
            elif kind == "endif" and stack:
                stack.pop()
            out.append("")
            continue
        hidden = any(verification and (negated == in_else) for verification, negated, in_else in stack)
        out.append("" if hidden else line)
    return "\n".join(out)


def _verilog_instances(body):
    found = set()
    pattern = re.compile(
        r"(?:^|[;\n]|\bbegin\b|\bend\b|\belse\b|\)|:)\s*(" + _IDENT + r")\s*"
        r"(?:#\s*\(|\s(" + _IDENT + r")\s*(?:\[[^\]]*\]\s*)*\()",
        re.M,
    )
    for m in pattern.finditer(body):
        name = m.group(1)
        if name in _VERILOG_KEYWORDS or (m.group(2) and m.group(2) in _VERILOG_KEYWORDS):
            continue
        found.add(name)
    return found


def _vhdl_instances(body):
    found = set()
    for m in re.finditer(r"\bentity\s+\w+\s*\.\s*(\w+)", body, re.I):
        found.add(m.group(1))
    for m in re.finditer(r":\s*(?:component\s+)?(\w+)\s+(?:generic|port)\s+map\b", body, re.I):
        found.add(m.group(1))
    return found


def read_hdl_file(path):
    """The FileInfo of one HDL file (Verilog, SystemVerilog or VHDL)."""
    info = FileInfo(path)
    text = _read(path)
    if not text:
        return info
    vhdl = info.language == "vhdl"
    info.units = hdl_detect.read_file(path, path)
    code = _strip_comments(text, vhdl)
    if vhdl:
        info.packages = set(m.group(1).lower() for m in re.finditer(r"^\s*package\s+(\w+)\s+is\b", code, re.I | re.M))
        info.imports = set(m.group(1).lower() for m in re.finditer(r"\buse\s+work\.(\w+)", code, re.I))
        for unit in info.units:
            info.instances |= _vhdl_instances(unit.body)
        info.instances = set(i.lower() for i in info.instances)
    else:
        info.packages = set(re.findall(r"^\s*package\s+(?:automatic\s+|static\s+)?(" + _IDENT + r")\s*;", code, re.M))
        info.imports = set(re.findall(r"\b(" + _IDENT + r")\s*::", code)) - {"std", "$unit"}
        for unit in info.units:
            info.instances |= _verilog_instances(_strip_verification(unit.body))
        info.interfaces = set(re.findall(r"^\s*interface\s+(?:automatic\s+|static\s+)?(" + _IDENT + r")\b", code, re.M))
        info.includes = re.findall(r"`include\s+[\"<]([^\">]+)[\">]", code)
        info.macros_defined = set(re.findall(r"`define\s+(" + _IDENT + ")", code))
        info.macros_tested = set(re.findall(r"`(?:ifdef|ifndef|elsif)\s+(" + _IDENT + ")", code))
        directives = {"define", "undef", "ifdef", "ifndef", "elsif", "else", "endif", "include", "timescale",
                      "default_nettype", "resetall", "celldefine", "endcelldefine", "line", "pragma",
                      "begin_keywords", "end_keywords", "unconnected_drive", "nounconnected_drive", "__FILE__", "__LINE__"}
        info.macros_used = set(m for m in re.findall(r"`(" + _IDENT + ")", code) if m not in directives)
    info.instances -= info.modules | info.interfaces
    return info


#: Paths of the version of a module made for one technology: the generic one is preferred.
_VENDOR_SPECIFIC = re.compile(r"(?:^|[/_.-])(?:fpga|xilinx|altera|intel|lattice|ecp5|ice40|asic|tsmc|gf\d+|sky130|ihp|deprecated)(?:[/_.-]|$)")


class ProjectIndex(object):
    """What every HDL file of a tree defines: to find who defines what."""

    def __init__(self, root, extra_files=()):
        self.root = root
        self.files = {}
        for path in _unique(list(walk(root, HDL_EXTENSIONS)) + [f for f in extra_files if os.path.isfile(f)]):
            self.files[path] = read_hdl_file(path)
        self.headers = walk(root, HEADER_EXTENSIONS + (".v", ".sv"))
        self.module_files = {}
        self.package_files = {}
        self.model_files = {}   # modules only a bench or a behavioural model defines: the last resort
        declared = set(extra_files)
        for path, info in self.files.items():
            if _in_testbench_dir(path) and path not in declared:
                # a bench never completes the design; a behavioural model (a clock gate...) may, when nothing else does
                if not info.is_testbench:
                    for name in info.modules | info.interfaces:
                        self.model_files.setdefault(name, []).append(path)
                continue
            for name in info.modules | info.interfaces:
                key = name.lower() if info.language == "vhdl" else name
                self.module_files.setdefault(key, []).append(path)
            for name in info.packages:
                self.package_files.setdefault(name, []).append(path)

    def info(self, path):
        if path not in self.files:
            self.files[path] = read_hdl_file(path)
        return self.files[path]

    def _best(self, paths, near=()):
        """The most likely of several files defining the same thing: not a testbench, nearest the others."""
        if not paths:
            return None
        anchors = [os.path.dirname(p) for p in near] or [self.root]

        def distance(path):
            best = min(len(os.path.relpath(path, a).split(os.sep)) for a in anchors)
            relative = _relative(path, self.root).lower()
            specific = bool(_VENDOR_SPECIFIC.search(relative)) or os.path.basename(path).startswith("_") \
                or bool(re.search(r"(?:^|/)(?:boards?|platforms?|scripts)/", relative))
            return (_in_testbench_dir(path), specific, best, path)
        return sorted(paths, key=distance)[0]

    def module_file(self, name, near=()):
        return self._best(self.module_files.get(name) or self.module_files.get(name.lower()) or [], near)

    def model_file(self, name, near=()):
        """A behavioural model of `name`, kept apart from the design (see model_files)."""
        return self._best(self.model_files.get(name) or [], near)

    def package_file(self, name, near=()):
        return self._best(self.package_files.get(name) or self.package_files.get(name.lower()) or [], near)

    def include_dir(self, include, near=()):
        """The directory that makes `include include` resolve, the nearest when several do."""
        suffix = os.sep + os.path.normpath(include)
        matches = [h for h in self.headers if h.endswith(suffix)]
        best = self._best(matches, near)
        if best is None:
            return None
        return best[:len(best) - len(suffix)] or os.sep

######################################
# What the project declares
######################################

def _guess_variables(text_entries, base, root):
    """
    Values for the ${VARIABLE}s a file list uses without the environment
    defining them: the directory, among those containing the list up to the
    project root (and its repository), that makes most entries exist.
    """
    names = set()
    for entry in text_entries:
        names.update(n for groups in re.findall(r"\$\{(\w+)\}|\$\((\w+)\)|\$(\w+)", entry) for n in groups if n)
    names = [n for n in names if n not in os.environ]
    if not names:
        return {}
    candidates = []
    directory = base
    top = os.path.dirname(_git_root(root) or root)
    while directory and directory.startswith(top) and directory not in candidates:
        candidates.append(directory)
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    guesses = {}
    for name in names:
        best, best_count = None, 0
        uses = [e for e in text_entries if "${" + name + "}" in e or "$(" + name + ")" in e or re.search(r"\$" + name + r"\b", e)]
        for directory in candidates:
            count = sum(
                1 for e in uses
                if os.path.exists(design_info.expand_variables(e, dict(guesses, **{name: directory})))
            )
            if count > best_count:
                best, best_count = directory, count
        if best:
            guesses[name] = best
    return guesses


def read_filelist(path, root):
    tokens = []
    for line in _read(path).splitlines():
        tokens.extend(re.split(r"//|#", line, maxsplit=1)[0].split())
    variables = _guess_variables(tokens, os.path.dirname(path), root)
    defines = []
    try:
        files, incdirs = design_info.read_filelist(path, "/", variables=variables, defines=defines,
                                                   search_dirs=(root,))
    except (OSError, IOError, UnicodeDecodeError):
        return None
    notes = ["${{{0}}} taken as {1}".format(k, _relative(v, root) or ".") for k, v in variables.items()]
    return DeclaredSources(
        "file list", path, [_abs(f, "/") for f in files], [_abs(d, "/") for d in incdirs], defines, notes=notes)


def _yaml(path):
    import yaml
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


#: Bender targets a generic synthesis has, and those it has not. Any other
#: name (a configuration of the design...) is taken as active: the variants it
#: selects are then told apart by the packages they define twice.
BENDER_ACTIVE = {"synthesis", "rtl"}
BENDER_INACTIVE = {
    "simulation", "sim", "test", "tb", "fpga", "xilinx", "intel", "altera", "lattice", "asic", "gate",
    "verilator", "vsim", "vcs", "xsim", "questa", "riviera", "spyglass", "formal", "cadence", "synopsys",
}


def bender_target_active(expression):
    """Whether a Bender target expression ("all(fpga, xilinx)", "not(synthesis)"...) holds for a generic synthesis."""
    tokens = re.findall(r"[\w-]+|[(),*]", expression)
    if not tokens:
        return True
    position = [0]

    def parse():
        token = tokens[position[0]]
        position[0] += 1
        if token == "*":
            return True
        if position[0] < len(tokens) and tokens[position[0]] == "(" and token in ("all", "any", "not"):
            position[0] += 1
            values = []
            while position[0] < len(tokens) and tokens[position[0]] != ")":
                if tokens[position[0]] == ",":
                    position[0] += 1
                    continue
                values.append(parse())
            position[0] += 1
            if token == "all":
                return all(values)
            if token == "any":
                return any(values)
            return not values[0] if values else True
        name = token.lower()
        if name in BENDER_ACTIVE:
            return True
        if name in BENDER_INACTIVE:
            return False
        return True

    try:
        return parse()
    except IndexError:
        return True


def read_bender(path, root):
    base = os.path.dirname(path)
    if shutil.which("bender"):
        for target in ("synthesis", "rtl", None):
            command = ["bender", "script", "flist-plus"] + (["-t", target] if target else [])
            output = _run(command, base, timeout=120)
            if output is not None and output[0] == 0 and output[1].strip():
                handle, flist = tempfile.mkstemp(suffix=".f")
                with os.fdopen(handle, "w") as f:
                    f.write(output[1])
                try:
                    found = read_filelist(flist, root)
                finally:
                    os.remove(flist)
                if found and found.files:
                    return DeclaredSources("Bender", path, found.files, found.include_dirs, found.defines,
                                           notes=["from \"{0}\"".format(" ".join(command))])
    data = _yaml(path)
    if not isinstance(data, dict):
        return None
    files, incdirs, defines = [], [], []
    notes = []
    for directory in data.get("export_include_dirs") or []:
        incdirs.append(_abs(str(directory), base))

    def visit(entries, target_ok=True):
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries or []:
            if isinstance(entry, str):
                if target_ok:
                    files.extend(_expand_glob(_abs(entry, base)))
            elif isinstance(entry, dict):
                ok = target_ok and bender_target_active(str(entry.get("target", "")))
                for directory in entry.get("include_dirs") or []:
                    incdirs.append(_abs(str(directory), base))
                for name, value in (entry.get("defines") or {}).items():
                    defines.append(str(name) if value is None else "{0}={1}".format(name, value))
                visit(entry.get("files"), ok)
    visit(data.get("sources"))
    if data.get("dependencies"):
        notes.append("dependencies not read without the \"bender\" tool: " + ", ".join(sorted(data["dependencies"])))
    return DeclaredSources("Bender", path, files, incdirs, defines, notes=notes)


def read_fusesoc(path, root):
    data = _yaml(path)
    if not isinstance(data, dict) or "filesets" not in data:
        return None
    base = os.path.dirname(path)
    targets = data.get("targets") or {}
    target_name = next((t for t in ("synth", "synthesis", "default") if t in targets), None)
    target = targets.get(target_name) or {}
    wanted = []
    for item in target.get("filesets") or list((data.get("filesets") or {}).keys()):
        item = str(item)
        conditional = re.match(r"^(!?)(\w+)\?\s*\((.*)\)$", item.strip())
        if conditional:
            negated, flag, inner = conditional.groups()
            if not negated and re.search(r"sim|tb|verilator|icarus|test", flag):
                continue
            item = inner.strip()
        wanted.extend(item.split())
    files, incdirs, notes, depends = [], [], [], []
    for name in wanted:
        fileset = (data.get("filesets") or {}).get(name) or {}
        if re.search(r"(?:^|_)(?:tb|sim|test|bench|verif|formal|fpv|lint)(?:_|$)", name):
            continue
        depends.extend(str(d) for d in fileset.get("depend") or [])
        for entry in fileset.get("files") or []:
            options = {}
            if isinstance(entry, dict):
                (entry, options), = entry.items()
                options = options or {}
            entry = _abs(str(entry), base)
            if options.get("is_include_file") or entry.lower().endswith(HEADER_EXTENSIONS):
                incdirs.append(_abs(str(options["include_path"]), base) if options.get("include_path") else os.path.dirname(entry))
            elif _is_hdl(entry):
                files.append(entry)
    toplevel = target.get("toplevel") or ""
    if isinstance(toplevel, list):
        toplevel = toplevel[0] if toplevel else ""
    conditional = re.match(r"^!?\w+\?\s*\((.*)\)$", str(toplevel).strip())
    if conditional:
        toplevel = conditional.group(1).strip()
    if depends:
        notes.append("core dependencies looked for in the project tree: " + ", ".join(depends))
    return DeclaredSources("FuseSoC", path, files, incdirs, top=str(toplevel), notes=notes)


def read_librelane(path, root):
    base = os.path.dirname(path)
    if path.endswith(".json"):
        try:
            data = json.loads(_read(path))
        except ValueError:
            return None
    else:
        data = _yaml(path)
    if not isinstance(data, dict) or "VERILOG_FILES" not in data:
        return None

    def paths(value):
        if isinstance(value, str):
            value = value.split()
        found = []
        for item in value or []:
            item = re.sub(r"^(?:dir|ref)::", "", str(item)).replace("$DESIGN_DIR", base)
            found.extend(_expand_glob(_abs(item, base)))
        return found
    defines = data.get("VERILOG_DEFINES") or []
    if isinstance(defines, str):
        defines = defines.split()
    return DeclaredSources(
        "LibreLane", path, paths(data.get("VERILOG_FILES")), paths(data.get("VERILOG_INCLUDE_DIRS")),
        [str(d) for d in defines], top=str(data.get("DESIGN_NAME") or ""), clock=str(data.get("CLOCK_PORT") or ""))


def read_vivado_project(path, root):
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return None
    base = os.path.dirname(path)
    files, incdirs, defines, top = [], [], [], ""
    for fileset in tree.iter("FileSet"):
        if fileset.get("Type") != "DesignSrcs":
            continue
        for item in fileset.iter("File"):
            file_path = (item.get("Path") or "").replace("$PPRDIR", base).replace("$PSRCDIR", os.path.join(base, os.path.splitext(os.path.basename(path))[0] + ".srcs"))
            file_path = _abs(file_path, base)
            if _is_hdl(file_path):
                files.append(file_path)
            elif file_path.lower().endswith(HEADER_EXTENSIONS):
                incdirs.append(os.path.dirname(file_path))
        for option in fileset.iter("Option"):
            name, value = option.get("Name"), option.get("Val") or ""
            if name == "TopModule":
                top = value
            elif name == "VerilogDefine":
                defines.extend(value.split())
            elif name == "VerilogDir":
                incdirs.extend(_abs(v.replace("$PPRDIR", base), base) for v in value.split())
    return DeclaredSources("Vivado project", path, files, incdirs, defines, top=top)


def _tcl_commands(text):
    """The commands of a Tcl script, as lists of words, continuation lines joined."""
    text = re.sub(r"\\\n", " ", text)
    commands = []
    for line in re.split(r"[\n;]", text):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        commands.append(re.findall(r"\{[^{}]*\}|\[[^\[\]]*\]|\"[^\"]*\"|\S+", line))
    return commands


def _tcl_values(word, base):
    """The paths a Tcl word names: a {list}, a [glob ...], a plain path."""
    word = word.strip()
    if word.startswith("[glob"):
        inner = word[5:-1].split()
        inner = [w for w in inner if not w.startswith("-")]
        found = []
        for w in inner:
            found.extend(_expand_glob(_abs(w.strip("{}\""), base)))
        return found
    if word.startswith("[") or "$" in word:
        return []
    word = word.strip("{}\"")
    found = []
    for item in word.split():
        found.extend(_expand_glob(_abs(item, base)))
    return found


def read_tcl_script(path, root):
    """Vivado, Design Compiler, Genus or Quartus Tcl scripts naming the sources."""
    base = os.path.dirname(path)
    text = _read(path)
    files, incdirs, defines, top = [], [], [], ""
    origin = "synthesis script"
    for words in _tcl_commands(text):
        command = words[0]
        args = words[1:]
        if command in ("read_verilog", "read_vhdl", "add_files", "read_hdl", "analyze", "read_sverilog", "read_file",
                       "read_hdl_sources"):
            if command in ("read_verilog", "read_vhdl", "add_files") and origin == "synthesis script":
                origin = "Vivado script"
            skip = False
            for index, word in enumerate(args):
                if skip:
                    skip = False
                    continue
                if word in ("-format", "-library", "-lib", "-work", "-fileset", "-of_objects", "-language", "-f"):
                    skip = True
                    continue
                if word in ("-define", "-defines"):
                    if index + 1 < len(args):
                        defines.extend(args[index + 1].strip("{}\"").split())
                    skip = True
                    continue
                if word.startswith("-"):
                    continue
                for value in _tcl_values(word, base):
                    if _is_hdl(value):
                        files.append(value)
                    elif os.path.isdir(value):
                        files.extend(f for f in walk(value, HDL_EXTENSIONS, 1))
        elif command == "set_property" and len(args) >= 2 and args[0] == "top":
            top = args[1].strip("{}\"")
        elif command in ("synth_design", "elaborate", "set_top_module"):
            if "-top" in args and args.index("-top") + 1 < len(args):
                top = args[args.index("-top") + 1].strip("{}\"")
            elif command != "synth_design" and args and not args[0].startswith("-"):
                top = args[0].strip("{}\"")
            for flag in ("-include_dirs",):
                if flag in args and args.index(flag) + 1 < len(args):
                    incdirs.extend(_tcl_values(args[args.index(flag) + 1], base))
            if "-verilog_define" in args:
                for index, word in enumerate(args):
                    if word == "-verilog_define" and index + 1 < len(args):
                        defines.append(args[index + 1].strip("{}\""))
        elif command == "set_global_assignment" and "-name" in args:
            origin = "Quartus project"
            name = args[args.index("-name") + 1]
            value = args[-1].strip("{}\"")
            if name in ("VERILOG_FILE", "SYSTEMVERILOG_FILE", "VHDL_FILE"):
                files.extend(_expand_glob(_abs(value, base)))
            elif name == "TOP_LEVEL_ENTITY":
                top = value
            elif name == "SEARCH_PATH":
                incdirs.append(_abs(value, base))
            elif name == "VERILOG_MACRO":
                defines.append(value)
    if not files:
        return None
    return DeclaredSources(origin, path, files, incdirs, defines, top=top)


def _make_variables(path):
    """The variables a makefile sets (=, :=, ?=, +=), expanded."""
    base = os.path.dirname(path)
    variables = {"PWD": base, "CURDIR": base, "CURDIR_": base}
    text = re.sub(r"\\\n", " ", _read(path))
    for m in re.finditer(r"^\s*(?:export\s+)?([A-Za-z_]\w*)\s*([:?+]?=)\s*(.*)$", text, re.M):
        name, operator, value = m.groups()
        value = value.split("#")[0].strip()
        value = re.sub(r"\$\((?:shell\s+pwd|abspath\s+\.)\)", base, value)
        value = re.sub(r"\$\(wildcard\s+([^)]*)\)", lambda w: " ".join(
            sum((_expand_glob(_abs(design_info.expand_variables(p, variables), base)) for p in w.group(1).split()), [])), value)
        value = design_info.expand_variables(value, variables)
        if operator == "+=" and name in variables:
            variables[name] = variables[name] + " " + value
        elif operator == "?=" and name in variables:
            continue
        else:
            variables[name] = value
    return variables


def read_makefile(path, root):
    variables = _make_variables(path)
    base = os.path.dirname(path)
    files = []
    for name in ("VERILOG_SOURCES", "VHDL_SOURCES", "SV_SOURCES", "SOURCES", "RTL_SOURCES", "SRCS", "RTL_FILES", "VERILOG_FILES"):
        for item in (variables.get(name) or "").split():
            if "$" not in item:
                files.extend(f for f in _expand_glob(_abs(item, base)) if _is_hdl(f))
    if not files:
        return None
    incdirs, defines = [], []
    for name in ("COMPILE_ARGS", "EXTRA_ARGS", "VERILATOR_FLAGS", "INCDIRS", "INCLUDE_DIRS"):
        for token in (variables.get(name) or "").split():
            if token.startswith("+incdir+"):
                incdirs.extend(_abs(d, base) for d in token[8:].split("+") if d)
            elif token.startswith("-I") and len(token) > 2:
                incdirs.append(_abs(token[2:], base))
            elif token.startswith("+define+"):
                defines.extend(d for d in token[8:].split("+") if d)
            elif token.startswith("-D") and len(token) > 2:
                defines.append(token[2:])
            elif name.startswith("INC") and "$" not in token:
                incdirs.append(_abs(token, base))
    top = variables.get("TOPLEVEL") or variables.get("TOP") or variables.get("TOP_MODULE") or ""
    return DeclaredSources("makefile", path, files, incdirs, defines, top=top.split()[0] if top.split() else "")


def find_declarations(root):
    """Every project file of the tree that names sources, best first."""
    readers = []
    for path in walk(root, max_depth=5):
        name = os.path.basename(path)
        lower = name.lower()
        if lower.endswith((".f", ".vc", ".flist")):
            if not _read(path).startswith(GENERATED_FILELIST_MARK):
                readers.append((read_filelist, path))
        elif name == "Bender.yml":
            readers.append((read_bender, path))
        elif lower.endswith(".core"):
            readers.append((read_fusesoc, path))
        elif lower.endswith((".json", ".yaml", ".yml")) and "VERILOG_FILES" in _read(path)[:100000]:
            readers.append((read_librelane, path))
        elif lower.endswith(".xpr"):
            readers.append((read_vivado_project, path))
        elif lower.endswith((".tcl", ".qsf")):
            readers.append((read_tcl_script, path))
        elif name in ("Makefile", "makefile", "GNUmakefile") or lower.endswith(".mk"):
            readers.append((read_makefile, path))
    found = []
    for reader, path in readers:
        try:
            declared = reader(path, root)
        except Exception as exception:  # a project file Odatix misreads must not stop the detection
            declared = None
            _ = exception
        if declared is not None and declared.files:
            declared.files = _unique(declared.files)
            declared.include_dirs = _unique(declared.include_dirs)
            found.append(declared)
    project = os.path.basename(os.path.normpath(root)).lower()

    def score(declared):
        # the declaration named after the project, at its root, is the project itself
        named = os.path.splitext(os.path.basename(declared.path))[0].lower() == project or declared.top.lower() == project
        shallow = os.path.dirname(declared.path) == os.path.normpath(root)
        return declared.score() * (4.0 if named else 1.0) * (1.3 if shallow else 1.0)
    found.sort(key=lambda d: -score(d))
    return [d for d in found if d.score() > 0]

######################################
# What the RTL says
######################################

def _hierarchy(index, top, top_file, files=None):
    """
    The files the hierarchy under `top` needs, in compilation order (the
    packages and the modules a file uses before it), the modules defined
    nowhere, and the modules defined by several files.
    """
    allowed = set(files) if files is not None else None
    needed = []
    black_boxes = set()
    duplicates = {}
    seen_modules = set()
    queue = [(top, top_file)]

    def locate(name, near, kind):
        candidates = (index.package_files if kind == "package" else index.module_files).get(name) \
            or (index.package_files if kind == "package" else index.module_files).get(name.lower()) or []
        if allowed is not None:
            inside = [c for c in candidates if c in allowed]
            candidates = inside or candidates
        if len(set(candidates)) > 1 and kind == "module":
            duplicates[name] = sorted(set(candidates))
        return index._best(candidates, near)

    while queue:
        name, path = queue.pop(0)
        if name in seen_modules:
            continue
        seen_modules.add(name)
        path = path or locate(name, needed[-1:] or [top_file], "module")
        if not path:
            if not _PRIMITIVE.match(name) and not name.endswith("_t"):
                black_boxes.add(name)
            continue
        if path not in needed:
            needed.append(path)
        info = index.info(path)
        for package in info.imports:
            package_path = locate(package, [path], "package")
            if package_path and package_path not in needed:
                needed.append(package_path)
                for nested in index.info(package_path).imports:
                    nested_path = locate(nested, [package_path], "package")
                    if nested_path and nested_path not in needed:
                        needed.append(nested_path)
        for child in sorted(info.instances):
            if child not in seen_modules:
                queue.append((child, None))
    included = set(_all_includes(index, needed))
    needed = [p for p in needed if p not in included]
    return _compilation_order(index, needed), sorted(black_boxes), duplicates


def _compilation_order(index, files):
    """`files` sorted so that what defines a package or an entity comes before what uses it."""
    defines = {}
    for path in files:
        info = index.info(path)
        for name in info.packages:
            defines.setdefault(("p", name.lower()), path)
        if info.language == "vhdl":
            for name in info.modules:
                defines.setdefault(("m", name.lower()), path)
    depends = {}
    for path in files:
        info = index.info(path)
        deps = set()
        for name in info.imports:
            dep = defines.get(("p", name.lower()))
            if dep and dep != path:
                deps.add(dep)
        if info.language == "vhdl":
            for name in info.instances:
                dep = defines.get(("m", name.lower()))
                if dep and dep != path:
                    deps.add(dep)
        depends[path] = deps
    # packages first, then a stable depth-first order
    ordered, visiting = [], set()

    def visit(path):
        if path in ordered or path in visiting:
            return
        visiting.add(path)
        for dep in sorted(depends.get(path, ()), key=files.index):
            visit(dep)
        visiting.discard(path)
        ordered.append(path)

    packages = [p for p in files if index.info(p).packages]
    for path in packages + list(reversed([p for p in files if p not in packages])):
        visit(path)
    return ordered


def _complete_instances(index, files):
    """
    Add to `files` what defines the modules and packages any of them uses:
    some tools (Verilator) elaborate every module they read, not only the
    hierarchy under the top. Returns the files added.
    """
    added = []
    changed = True
    while changed:
        changed = False
        defined_modules = set()
        defined_packages = set()
        defined_interfaces = set()
        for path in files:
            info = index.info(path)
            defined_interfaces |= info.interfaces
            defined_modules |= set(m.lower() if info.language == "vhdl" else m for m in info.modules)
            defined_packages |= info.packages
        for path in list(files):
            info = index.info(path)
            for name in sorted(info.instances):
                if name in defined_modules or name in defined_interfaces or _PRIMITIVE.match(name) or name.endswith("_t"):
                    continue
                found = index.module_file(name, files)
                if found and found not in files:
                    files.append(found)
                    added.append(found)
                    defined_modules |= index.info(found).modules
                    changed = True
            for name in sorted(info.imports - defined_packages):
                found = index.package_file(name, files)
                if found and found not in files:
                    files.insert(0, found)
                    added.append(found)
                    defined_packages |= index.info(found).packages
                    changed = True
    return added


def _keep_one_variant(index, files):
    """
    `files` with a single file per package: designs ship several definitions
    of a configuration package, one per variant, and compile one of them.
    """
    owners = {}
    for path in files:
        for name in index.info(path).packages:
            owners.setdefault(name, []).append(path)
    variants = {name: paths for name, paths in owners.items() if len(paths) > 1}
    dropped = set(p for paths in variants.values() for p in paths[1:])
    return [p for p in files if p not in dropped], variants


def _macro_report(index, files, defines):
    defined = set(d.split("=")[0] for d in defines)
    for path in files:
        defined |= index.info(path).macros_defined
    for path in _all_includes(index, files):
        defined |= index.info(path).macros_defined
    tested, used = set(), set()
    for path in files:
        info = index.info(path)
        tested |= info.macros_tested
        used |= info.macros_used
    return sorted(tested - defined), sorted(used - defined - tested)


def _all_includes(index, files):
    found = []
    for path in files:
        for include in index.info(path).includes:
            directory = index.include_dir(include, [path])
            if directory:
                found.append(os.path.join(directory, include))
    return [f for f in _unique(found) if os.path.isfile(f)]


def _include_dirs(index, files):
    dirs = []
    for path in files:
        for include in index.info(path).includes:
            if os.path.isfile(os.path.join(os.path.dirname(path), include)):
                continue
            directory = index.include_dir(include, [path])
            if directory:
                dirs.append(directory)
    return _unique(dirs)


def _top_candidates(index, files, hints):
    units = []
    for path in files:
        info = index.info(path)
        if not info.is_testbench:
            units.extend(info.units)
    return hdl_detect.top_module_candidates(units, hints=hints), units

######################################
# Generators, tools, PDKs
######################################

def detect_generator(root):
    """How the project's RTL is generated (Chisel, SpinalHDL, Amaranth, HLS...), or None."""
    try:
        return rtl_generation.detect(root)
    except Exception:  # a project Odatix misreads must not stop the detection
        return None


def installed_tools():
    return [tool for tool, executables in TOOL_EXECUTABLES if all(shutil.which(e) for e in executables)]


def detect_pdks():
    found = []
    for variable in ("PDK_ROOT", "PDKPATH", "PDK"):
        value = os.environ.get(variable)
        if value:
            found.append("{0}={1}".format(variable, value))
    for path in (os.path.expanduser("~/.volare"), os.path.expanduser("~/.ciel"), "/opt/pdk", "/usr/local/share/pdk"):
        if os.path.isdir(path):
            found.append(path)
    return _unique(found)


def _git_root(path):
    directory = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(directory, ".git")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent

######################################
# Validation by elaboration
######################################

def _run(command, cwd, timeout=600):
    try:
        process = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 universal_newlines=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return process.returncode, process.stdout


def _elaborator(languages):
    if "vhdl" in languages:
        if languages == ["vhdl"] and shutil.which("ghdl"):
            return "ghdl"
        return ""  # mixed languages: no free tool elaborates them all
    for tool in ("slang", "verilator", "yosys"):
        if shutil.which(tool):
            return tool
    return ""


def vhdl_library(files):
    """
    The library a VHDL design is compiled into when its files name it
    ("library neorv32; use neorv32.pkg.all;") instead of using "work".
    """
    named = {}
    for path in files:
        if not path.lower().endswith(VHDL_EXTENSIONS):
            continue
        for name in re.findall(r"^\s*library\s+(\w+)\s*;", _strip_comments(_read(path), True), re.I | re.M):
            name = name.lower()
            if name not in ("ieee", "std", "work") and not _VENDOR_LIBRARY.match(name):
                named[name] = named.get(name, 0) + 1
    return max(named, key=named.get) if named else "work"


_VENDOR_LIBRARY = re.compile(r"^(?:unisim|unimacro|xpm|altera\w*|lpm|ice40|ecp5|machxo\w*|vital\w*|synopsys)$")


def _elaboration_command(tool, files, include_dirs, defines, top, workdir):
    if tool == "slang":
        command = ["slang", "--top", top, "-q", "-Wno-duplicate-definition", "--timescale", "1ns/1ps", "--single-unit", "--compat=vcs", "--allow-toplevel-iface-ports"]
        command += ["-I" + d for d in include_dirs] + ["-D" + d for d in defines] + files
    elif tool == "verilator":
        command = ["verilator", "--lint-only", "-Wno-fatal", "-Wno-lint", "-Wno-style", "--timing", "--top-module", top]
        command += ["-I" + d for d in include_dirs] + ["+define+" + d for d in defines] + files
    elif tool == "yosys":
        reads = " ".join(
            "read_verilog {0}-defer {1}{2}{3}".format(
                "-sv " if f.endswith(".sv") else "",
                " ".join("-I" + d for d in include_dirs) + " ",
                " ".join("-D" + d for d in defines) + " ", f)
            for f in files)
        command = ["yosys", "-q", "-p", reads + "; hierarchy -check -top " + top]
    else:  # ghdl
        command = ["sh", "-c", "ghdl -i --std=08 -frelaxed --work={3} --workdir={0} {1} && ghdl -m --std=08 -frelaxed --work={3} --workdir={0} {2}".format(
            workdir, " ".join("'" + f + "'" for f in files), top, vhdl_library(files))]
    return command


_MISSING_MODULE = (
    r"unknown module '(\w+)'",
    r"Cannot find file containing module: '(\w+)'",
    r"unknown interface '(\w+)'",
    r"Module `\\?(\w+)' referenced in module .* is not part of the design",
    r"cannot find entity or configuration (\w+)",
)
_MISSING_PACKAGE = (
    r"unknown (?:class or )?package '(\w+)'",
    r"Package/class '(\w+)' not found",
    r"Importing from missing package '(\w+)'",
    r"unit \"(\w+)\" not found in library",
)
_MISSING_INCLUDE = (
    r"could not find or open include file '([^']+)'",
    r"Cannot find include file: '?\"?([^'\"\s]+)",
    r"Can't open include file `([^']+)'",
)


def _matches(patterns, output):
    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, output))
    return _unique(found)


def _error_lines(output):
    lines = [l.strip() for l in output.splitlines()
             if re.search(r"(?:^|\s|:)(?:error|fatal)(?:\s*\[[^\]]*\])?:|%Error|%Fatal|^ERROR:", l, re.I)]
    return lines[:15]


def validate(detection, index, max_rounds=6, timeout=600, max_variants=12):
    """
    Elaborate the sources (see _validate_once); when they do not elaborate and
    a package has variants, try the others in turn, keeping the first that
    does: the default of a design is often not its first file.
    """
    result = _validate_once(detection, index, max_rounds, timeout)
    if result.ok is not False:
        return result
    for name, paths in list(detection.variants.items()):
        kept = paths[0]
        for variant in paths[1:max_variants + 1]:
            snapshot = (list(detection.files), list(detection.include_dirs), list(detection.black_boxes))
            detection.files = [variant if f == kept else f for f in detection.files]
            attempt = _validate_once(detection, index, max_rounds, timeout)
            if attempt.ok:
                detection.variants[name] = [variant] + [p for p in paths if p != variant]
                attempt.fixes.append("variant {0} of package {1} chosen: {2} does not elaborate".format(
                    _relative(variant, detection.root), name, _relative(kept, detection.root)))
                detection.notes = [n for n in detection.notes if not n.endswith("the others are variants") or name not in n]
                detection.notes.append("{0} files define the package {1}: {2} kept, the others are variants".format(
                    len(paths), name, _relative(variant, detection.root)))
                return attempt
            detection.files, detection.include_dirs, detection.black_boxes = snapshot
    detection.validation = result
    return result


def _validate_once(detection, index, max_rounds=6, timeout=600):
    """
    Elaborate the sources found with a free tool and fix what the project can
    answer: a module, a package or an include file it holds elsewhere. The
    detection is updated in place.
    """
    top = detection.top.value if detection.top else ""
    tool = _elaborator(detection.languages)
    if not tool or not top:
        detection.validation = Validation(
            "", None, errors=[] if top else ["no top level"],
        )
        if not tool:
            detection.notes.append(
                "no tool to check the sources with: install slang, Verilator or Yosys"
                + (" (and GHDL for VHDL; mixed languages are not checked)" if "vhdl" in detection.languages else ""))
        return detection.validation
    fixes = []
    workdir = tempfile.mkdtemp(prefix="odatix_detect_")
    try:
        output = ""
        for _round in range(max_rounds):
            command = _elaboration_command(tool, detection.files, detection.include_dirs, detection.defines, top, workdir)
            result = _run(command, detection.root, timeout=timeout)
            if result is None:
                detection.validation = Validation(tool, None, ["could not run " + tool], fixes)
                return detection.validation
            code, output = result
            errors = _error_lines(output)
            if code == 0 and not errors:
                detection.validation = Validation(tool, True, [], fixes, " ".join(command[:4]) + " ...")
                return detection.validation
            changed = False
            for name in _matches(_MISSING_PACKAGE, output):
                path = index.package_file(name, detection.files)
                if path and path not in detection.files:
                    detection.files.insert(0, path)
                    fixes.append("added {0} (package {1})".format(_relative(path, detection.root), name))
                    changed = True
            for name in _matches(_MISSING_MODULE, output):
                path = index.module_file(name, detection.files)
                if path and path not in detection.files:
                    needed, _, _ = _hierarchy(index, name, path)
                    for item in needed:
                        if item not in detection.files:
                            if index.info(item).packages:
                                detection.files.insert(0, item)
                            else:
                                detection.files.append(item)
                    fixes.append("added {0} (module {1})".format(_relative(path, detection.root), name))
                    changed = True
                elif not path and index.model_file(name, detection.files) not in (None,) + tuple(detection.files):
                    model = index.model_file(name, detection.files)
                    detection.files.append(model)
                    fixes.append("added {0} (module {1}): a behavioural model, to replace for synthesis".format(
                        _relative(model, detection.root), name))
                    changed = True
                elif not path and name not in detection.black_boxes:
                    detection.black_boxes.append(name)
            for include in _matches(_MISSING_INCLUDE, output):
                directory = index.include_dir(include, detection.files)
                if directory and directory not in detection.include_dirs:
                    detection.include_dirs.append(directory)
                    fixes.append("added include directory {0} ({1})".format(_relative(directory, detection.root), include))
                    changed = True
            if not changed:
                break
        detection.validation = Validation(tool, False, _error_lines(output) or output.strip().splitlines()[-5:], fixes)
        return detection.validation
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

######################################
# Everything together
######################################

def detect_project(root, top="", use_declarations=True, check=True, timeout=600, generator=True):
    """
    Detect the project under `root`.

    Args:
        top (str): the top level, when known.
        use_declarations (bool): read the project files naming the sources
            (otherwise infer everything from the RTL).
        check (bool): elaborate the result with a free tool, fixing what can be.

    Returns:
        ProjectDetection
    """
    root = os.path.abspath(root)
    detection = ProjectDetection(root)
    detection.declarations = find_declarations(root) if use_declarations else []
    declared = detection.declarations[0] if detection.declarations else None
    index = ProjectIndex(root, declared.files if declared else ())
    hints = [os.path.basename(root)]

    if declared is not None:
        detection.origin = declared.label
        included = set(_all_includes(index, declared.files))
        files = [f for f in declared.files if os.path.isfile(f) and not index.info(f).is_testbench and f not in included]
        dropped = [f for f in declared.files if os.path.isfile(f) and f not in files]
        missing = [f for f in declared.files if not os.path.isfile(f)]
        if dropped:
            detection.notes.append("{0} testbench file(s) of {1} left out".format(len(dropped), declared.label))
        if missing:
            detection.notes.append("{0} file(s) named by {1} do not exist, e.g. {2}".format(
                len(missing), declared.label, _relative(missing[0], root)))
        detection.notes.extend(declared.notes)
        files, detection.variants = _keep_one_variant(index, files)
        for name, paths in detection.variants.items():
            detection.notes.append("{0} files define the package {1}: {2} kept, the others are variants".format(
                len(paths), name, _relative(paths[0], root)))
        completed = _complete_instances(index, files)
        if completed:
            detection.notes.append("{0} file(s) added that {1} does not name, defining what its files use: {2}{3}".format(
                len(completed), declared.label, ", ".join(_relative(f, root) for f in completed[:4]),
                " ..." if len(completed) > 4 else ""))
        detection.files = files
        detection.include_dirs = [d for d in declared.include_dirs if os.path.isdir(d)]
        detection.defines = list(declared.defines)
        if declared.top and not top:
            alternatives = [d.top for d in detection.declarations[1:] if d.top and d.top != declared.top]
            detection.top = Finding(declared.top, declared.label, "declared", _unique(alternatives))
        if declared.clock:
            detection.clock = Finding(declared.clock, declared.label, "declared")
        detection.tops, units = _top_candidates(index, files, hints + [declared.top])
        detection.units = units
    else:
        detection.origin = "inferred from the RTL"
        candidates = [p for p, info in index.files.items() if not info.is_testbench and not _in_testbench_dir(p)]
        detection.tops, units = _top_candidates(index, candidates, hints)
        detection.units = units

    if top:
        detection.top = Finding(top, "given", "given")
    elif detection.top is None and detection.tops:
        best = detection.tops[0]
        detection.top = Finding(best.value, "inferred", "inferred" if len(detection.tops) == 1 else "guessed",
                                [c.value for c in detection.tops[1:]])

    # the module named after the project is worth proposing, even when wrappers instantiate it
    project_name = os.path.basename(os.path.normpath(root))
    if detection.top is not None and detection.top.value != project_name and project_name not in detection.top.alternatives \
            and index.module_file(project_name, detection.files):
        detection.top.alternatives.insert(0, project_name)
        if detection.top.confidence == "inferred":
            detection.top.confidence = "guessed"
    if detection.top is not None:
        top_file = index.module_file(detection.top.value, detection.files)
        detection.top_file = top_file or ""
        if declared is None and top_file:
            detection.files, detection.black_boxes, detection.duplicates = _hierarchy(index, detection.top.value, top_file)
            detection.include_dirs = _include_dirs(index, detection.files)
        elif top_file:
            _, detection.black_boxes, detection.duplicates = _hierarchy(index, detection.top.value, top_file, detection.files)
            detection.include_dirs = _unique(detection.include_dirs + _include_dirs(index, detection.files))
            if top_file not in detection.files:
                detection.files.append(top_file)
                detection.notes.append("top level file {0} added: {1} does not name it".format(
                    _relative(top_file, root), declared.label))
        unit = hdl_detect.find_unit(units or [u for i in index.files.values() for u in i.units], detection.top.value, top_file or "")
        if unit is not None:
            if detection.clock is None:
                clocks = hdl_detect.clock_candidates(unit, units)
                if clocks:
                    detection.clock = Finding(clocks[0].value, "inferred", "inferred" if len(clocks) == 1 else "guessed",
                                              [c.value for c in clocks[1:]])
            resets = hdl_detect.reset_candidates(unit, units)
            if resets:
                detection.reset = Finding(resets[0].value, "inferred", "inferred" if len(resets) == 1 else "guessed",
                                          [c.value for c in resets[1:]])
        if top_file:
            detection.parameters = [p for p in hdl_detect.detect_parameters(_read(top_file), top_file)
                                    if p.kind in ("parameter", "generic") and p.overridable]

    detection.optional_macros, detection.undefined_macros = _macro_report(index, detection.files, detection.defines)
    detection.generator = detect_generator(root) if generator else None
    if detection.top is not None and detection.top.confidence == "guessed" and len(detection.tops) >= 5:
        detection.notes.append("{0} modules could be the top level, as in a library: name the one you want "
                               "(--top, or the top level field of the GUI)".format(len(detection.tops)))
    detection.tools = installed_tools()
    detection.pdks = detect_pdks()
    if check and detection.files:
        validate(detection, index, timeout=timeout)
        if detection.top is not None:
            detection.optional_macros, detection.undefined_macros = _macro_report(index, detection.files, detection.defines)
    if detection.needs_generation:
        detection.notes.append("the RTL is generated by {0} ({1}): it is found by running \"{2}\"".format(
            detection.generator.name, detection.generator.file, detection.generator.command))
    return detection


def module_choices(detection):
    """
    Every module the top level may be: the suggested ones first (the
    candidates of the detection, the module found or given), then the other
    modules of the design, in alphabetical order. Returns (suggested, others).
    """
    suggested = []
    if detection.top is not None:
        suggested.append(detection.top.value)
        suggested.extend(detection.top.alternatives)
    suggested.extend(c.value for c in detection.tops)
    suggested = list(dict.fromkeys(suggested))
    others = sorted(set(u.name for u in detection.units if not hdl_detect.is_testbench(u)) - set(suggested),
                    key=str.lower)
    return suggested, others


def signal_choices(detection, top):
    """
    What the clock and the reset of `top` may be: (inputs, clocks, resets),
    `inputs` being its one-bit inputs in the order of its ports, `clocks` and
    `resets` the suggested ones, best first.
    """
    unit = hdl_detect.find_unit(detection.units, top, detection.top_file if detection.top and detection.top.value == top else "")
    if unit is None:
        return [], [], []
    inputs = [p.name for p in unit.ports if p.direction in ("input", "inout") and not p.wide]
    clocks = [c.value for c in hdl_detect.clock_candidates(unit, detection.units)]
    resets = [c.value for c in hdl_detect.reset_candidates(unit, detection.units)]
    return inputs, clocks, resets


def parameters_of(detection, top):
    """The parameters `top` can be given (those of the detection for its own top level)."""
    if detection.top is not None and top == detection.top.value:
        return detection.parameters
    cache = detection.__dict__.setdefault("_parameters_by_top", {})
    if top not in cache:
        unit = hdl_detect.find_unit(detection.units, top)
        params = []
        if unit is not None:
            params = [p for p in hdl_detect.detect_parameters(_read(unit.file), unit.file)
                      if p.kind in ("parameter", "generic") and p.overridable]
        cache[top] = params
    return cache[top]


def retarget(detection, top, check=True):
    """
    The detection of the same project with another top level: another
    hierarchy, so its sources are found again (in the generated RTL, when the
    RTL was generated). Returns the new detection (the same object when the
    RTL is generated).
    """
    if not detection.generated_dir:
        return detect_project(detection.root, top=top, check=check)
    again = detect_project(detection.generated_dir, top=top, use_declarations=False, check=check, generator=False)
    for attribute in ("files", "include_dirs", "top", "top_file", "tops", "units", "clock", "reset", "parameters",
                      "optional_macros", "undefined_macros", "black_boxes", "duplicates", "validation"):
        setattr(detection, attribute, getattr(again, attribute))
    return detection


def detect_generated(detection, command=None, timeout=rtl_generation.DEFAULT_TIMEOUT, log=None):
    """
    Run the generator of `detection` (in a temporary copy of the project, as a
    job would) and describe the RTL it writes instead: sources, top level,
    clock, reset, parameters, check. The detection is updated in place; on
    failure, it is left as it was and generator.error says why.

    Returns:
        bool: whether the RTL was generated.
    """
    generation = detection.generator
    if generation is None:
        return False
    output = rtl_generation.generate(generation, detection.root, command=command, timeout=timeout, keep_log=log)
    if not output:
        return False
    top = detection.top.value if detection.top is not None and detection.top.confidence == "given" else ""
    generated = detect_project(output, top=top, use_declarations=False, check=True, generator=False)
    for attribute in ("files", "include_dirs", "defines", "top", "top_file", "tops", "units", "clock", "reset", "parameters",
                      "optional_macros", "undefined_macros", "black_boxes", "duplicates", "variants", "validation"):
        setattr(detection, attribute, getattr(generated, attribute))
    detection.generated_dir = output
    detection.origin = "generated by {0}".format(generation.name)
    detection.notes = [n for n in detection.notes if "it is found by running" not in n] + generated.notes
    detection.notes.append("{0} HDL file(s) generated in {1:.0f} s into {2}".format(
        len(generation.generated), generation.duration, generation.output or "the project root"))
    return True
