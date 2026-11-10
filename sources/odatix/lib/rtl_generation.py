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
Projects whose RTL is generated (Chisel, SpinalHDL, Amaranth, Migen/LiteX,
Vitis HLS), for "odatix init --detect": which generator, which entry points,
the command running one, and what to copy for it to run.

`generate` runs the command the way a job does: in a copy of what the
architecture copies (its design_path, filtered by the white and black lists),
never in the project itself. The HDL files the command creates or changes give
the output directory, wherever the generator writes; the detection then reads
the generated RTL like any other.
"""

import os
import re
import shutil
import subprocess
import tempfile
import time

HDL_EXTENSIONS = (".v", ".sv", ".vhd", ".vhdl")

#: Never copied for a generation: version control, build caches, outputs.
BLACKLIST = [".git", "target", "out", "project/target", "project/project", "test_run_dir", "build", "obj_dir",
             ".bloop", ".metals", ".bsp", ".idea", "__pycache__", ".venv", "venv", "node_modules"]

DEFAULT_TIMEOUT = 1800


class Generation(object):
    """How the RTL of a project is generated."""

    def __init__(self, name, file, command="", entries=(), whitelist=(), blacklist=(), output=""):
        self.name = name                 # "Chisel", "SpinalHDL"...
        self.file = file                 # what told it (build.sbt...), relative to the project
        self.command = command           # the command generating the RTL, run from the project root
        self.entries = list(entries)     # other commands worth proposing (other main objects...)
        self.whitelist = list(whitelist) # what to copy (everything when empty)
        self.blacklist = list(blacklist) # what not to copy
        self.output = output             # where the RTL lands, relative to the project ("" until generated)
        self.generated = []              # HDL files the last run created, relative to its copy
        self.error = ""                  # why the last run failed
        self.duration = 0.0
        self.copy = ""                   # the copy the last run happened in (to be removed)

    def to_dict(self):
        return {
            "name": self.name, "file": self.file, "command": self.command, "entries": list(self.entries),
            "whitelist": list(self.whitelist), "blacklist": list(self.blacklist), "output": self.output,
            "generated": list(self.generated), "error": self.error, "duration": round(self.duration, 1),
        }

    # what odatix.lib.project_detect.ProjectDetection.generator used to hold
    def __getitem__(self, key):
        return self.to_dict()[key]

    def __repr__(self):
        return "Generation({0!r}, {1!r})".format(self.name, self.command)

######################################
# Detection
######################################

def _read(path, limit=400000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except (OSError, IOError):
        return ""


def _files(root, extensions, max_depth=6):
    found = []
    base = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.count(os.sep) - base
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in BLACKLIST and depth < max_depth)
        for name in sorted(filenames):
            if name.endswith(extensions):
                found.append(os.path.join(dirpath, name))
    return found


_EMITS = re.compile(
    r"\b(?:emitVerilog|emitSystemVerilog|emitFIRRTL|ChiselStage|SpinalVerilog|SpinalVhdl|SpinalSystemVerilog"
    r"|SpinalConfig|generateVerilog|generateSystemVerilog|execute\s*\()"
)


def scala_entries(root):
    """
    The main objects of a Scala project ("object X extends App", or one with a
    "def main"), fully qualified, those emitting HDL first, the one named like
    the project (or "Top", "Gen"...) first among them.
    """
    project = os.path.basename(os.path.normpath(root)).lower()
    documented = readme_mains(root)
    found = []
    seen = set()
    for path in _files(root, (".scala",)):
        if os.sep + "test" + os.sep in path:
            continue
        text = _read(path)
        package = re.search(r"^\s*package\s+([\w.]+)", text, re.M)
        package = package.group(1) + "." if package else ""
        for m in re.finditer(r"\bobject\s+(\w+)\s+extends\s+App\b|\bobject\s+(\w+)\b[^{]*\{(?=(?:(?!\bobject\b)[\s\S])*?\bdef\s+main\s*\()", text):
            name = m.group(1) or m.group(2)
            if package + name in seen:
                continue
            seen.add(package + name)
            end = text.find("\nobject ", m.end())
            body = text[m.start():end if end > 0 else len(text)]
            score = 0
            if _EMITS.search(body):
                score += 10
            lower = name.lower()
            if lower == project or lower.startswith(project):
                score += 4
            if re.search(r"top|gen|main|verilog|emit", lower):
                score += 2
            if re.search(r"test|sim|bench|formal|spec", lower):
                score -= 6
            if package + name in documented:
                # what the README tells to run, in its order
                score += 20 - min(documented.index(package + name), 10)
            score -= max(0, package.count(".") - 2)
            found.append((score, package + name, os.path.relpath(path, root), _output_arguments(body)))
    found.sort(key=lambda f: (-f[0], f[1]))
    return [f for f in found if f[0] > 0] or found


#: Where the generated RTL goes when the command has to say it.
GENERATED_DIR = "generated_rtl"


def readme_mains(root):
    """The main objects the README of the project tells to run ("sbt "runMain x.y.Gen""), in order."""
    found = []
    for name in sorted(os.listdir(root)):
        if re.match(r"(?i)readme", name) and os.path.isfile(os.path.join(root, name)):
            for main in re.findall(r"runMain\s+([\w.]+)", _read(os.path.join(root, name), 2000000)):
                if main not in found:
                    found.append(main)
    return found


def _output_arguments(body):
    """
    The arguments telling a main object where to write, when it hands its own
    command line to the compiler: firtool ("firtoolOpts = ... args") wants
    -o=<dir> with --split-verilog, ChiselStage ("emitVerilog(new X, args)")
    a --target-dir.
    """
    if re.search(r"firtoolOpts\s*=[\s\S]{0,400}?\bargs\b", body):
        return " -o=" + GENERATED_DIR if "split-verilog" in body else " -o=" + GENERATED_DIR + "/design.sv"
    if re.search(r"\b(?:emitVerilog|emitSystemVerilog|execute)\s*\([^)]*\bargs\b", body):
        return " --target-dir " + GENERATED_DIR
    return ""


def _quote(text):
    return "'" + text.replace("'", "'\\''") + "'"


def detect(root):
    """The generation of the project's RTL, or None when it is written by hand."""
    root = os.path.abspath(root)

    def rel(path):
        return os.path.relpath(path, root).replace(os.sep, "/")

    sbt = os.path.join(root, "build.sbt")
    if os.path.isfile(sbt):
        text = _read(sbt).lower()
        sources = text + " ".join(_read(p, 20000).lower() for p in _files(os.path.join(root, "project"), (".scala", ".sbt"), 1))
        name = "SpinalHDL" if "spinalhdl" in sources else "Chisel" if "chisel" in sources else "Scala (sbt)"
        mains = scala_entries(root)
        commands = ["sbt {0}".format(_quote("runMain " + m[1] + m[3])) for m in mains]
        whitelist = ["build.sbt", "project", "src"] + sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d)) and d not in ("project", "src", "target") and not d.startswith(".")
            and os.path.isfile(os.path.join(root, d, "build.sbt")))  # sbt sub-projects
        # the white list leaves out everything else: only sbt's own outputs inside it matter
        blacklist = ["target", "project/target", "project/project"] + [d + "/target" for d in whitelist[3:]]
        return Generation(name, rel(sbt), commands[0] if commands else "sbt run", commands[1:8], whitelist, blacklist)

    mill = os.path.join(root, "build.sc")
    if os.path.isfile(mill):
        text = _read(mill)
        module = re.search(r"^\s*object\s+(\w+)\s+extends\b[^\n]*(?:Scala|Chisel|SbtModule)", text, re.M)
        module = module.group(1) if module else "design"
        mains = scala_entries(root)
        commands = ["mill {0}.runMain {1}{2}".format(module, m[1], m[3]) for m in mains] or ["mill {0}.run".format(module)]
        return Generation("Chisel (mill)" if "chisel" in text.lower() else "Scala (mill)", rel(mill),
                          commands[0], commands[1:8], [], BLACKLIST)

    candidates = []
    for path in _files(root, (".py",), 4):
        text = _read(path)
        if re.search(r"^\s*(?:from|import)\s+amaranth\b", text, re.M):
            kind = "Amaranth"
        elif re.search(r"^\s*(?:from|import)\s+(?:migen|litex)\b", text, re.M):
            kind = "Migen/LiteX"
        else:
            continue
        score = (5 if "__main__" in text else 0) + (3 if re.search(r"\b(?:verilog\.convert|main\(|\.build\(|convert\()", text) else 0)
        score -= 4 if re.search(r"(?:^|/)tests?/|test_", rel(path)) else 0
        candidates.append((score, kind, path))
    if candidates:
        candidates.sort(key=lambda c: (-c[0], c[2]))
        commands = ["python3 " + rel(c[2]) for c in candidates]
        return Generation(candidates[0][1], rel(candidates[0][2]), commands[0], commands[1:8], [], BLACKLIST)

    for path in _files(root, (".tcl", ".cfg"), 4):
        text = _read(path)
        if path.endswith(".tcl") and re.search(r"^\s*open_(?:project|component)\b", text, re.M) and "csynth_design" in text:
            return Generation("Vitis HLS", rel(path), "vitis_hls -f " + rel(path), [], [], BLACKLIST)
        if path.endswith(".cfg") and "[hls]" in text.lower():
            return Generation("Vitis HLS", rel(path), "v++ -c --mode hls --config " + rel(path), [], [], BLACKLIST)
    return None

######################################
# Running it
######################################

def _ignored(relative, blacklist):
    relative = relative.replace(os.sep, "/")
    return any(relative == b or relative.startswith(b.rstrip("/") + "/") for b in blacklist)


def copy_design(root, destination, whitelist=(), blacklist=()):
    """What a job copies of `root` for its generation: the whitelist (everything when empty), minus the blacklist."""
    entries = list(whitelist) or sorted(os.listdir(root))
    for entry in entries:
        source = os.path.join(root, entry)
        if not os.path.exists(source) or _ignored(entry, blacklist):
            continue
        target = os.path.join(destination, entry)
        if os.path.isdir(source):
            def ignore(directory, names, entry_root=source):
                relative = os.path.relpath(directory, root)
                return [n for n in names if _ignored(os.path.join(relative, n), blacklist) or os.path.islink(os.path.join(directory, n))
                        and not os.path.exists(os.path.join(directory, n))]
            shutil.copytree(source, target, symlinks=True, ignore=ignore)
        else:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)


def _snapshot(directory):
    found = {}
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in ("target", ".git", ".bloop", ".bsp", "out")]
        for name in filenames:
            if name.lower().endswith(HDL_EXTENSIONS):
                path = os.path.join(dirpath, name)
                try:
                    found[path] = os.path.getmtime(path)
                except OSError:
                    pass
    return found


def generate(generation, root, command=None, timeout=DEFAULT_TIMEOUT, keep_log=None):
    """
    Run the generation in a temporary copy of the project, as a job would.
    On success, `generation.output` is where the RTL landed (relative to the
    copy, hence to the project), `generation.generated` the files written, and
    `generation.copy` the copy (remove it with `cleanup`). On failure,
    `generation.error` says why.

    Returns:
        str: the absolute output directory in the copy, or "" on failure.
    """
    if command:
        generation.command = command
    cleanup(generation)
    output = _generate(generation, root, timeout, keep_log)
    if not output:
        cleanup(generation)  # nothing to read in a failed copy
    return output


def _generate(generation, root, timeout, keep_log):
    generation.output, generation.generated, generation.error = "", [], ""
    copy = tempfile.mkdtemp(prefix="odatix_generate_")
    generation.copy = copy
    try:
        copy_design(root, copy, generation.whitelist, generation.blacklist)
    except (OSError, shutil.Error) as exception:
        generation.error = "could not copy the design: {0}".format(exception)
        return ""
    before = _snapshot(copy)
    start = time.time()
    try:
        process = subprocess.run(generation.command, shell=True, cwd=copy, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout,
                                 stdin=subprocess.DEVNULL)
        output, code = process.stdout, process.returncode
    except subprocess.TimeoutExpired:
        generation.error = "the command ran longer than {0} s".format(timeout)
        return ""
    except OSError as exception:
        generation.error = str(exception)
        return ""
    finally:
        generation.duration = time.time() - start
    if keep_log:
        with open(keep_log, "w") as f:
            f.write(output)
    after = _snapshot(copy)
    written = sorted(p for p, mtime in after.items() if before.get(p) != mtime)
    if code != 0:
        tail = [l for l in output.strip().splitlines() if l.strip()][-6:]
        generation.error = "the command failed (exit code {0}): {1}".format(code, " | ".join(tail))
        return ""
    if not written:
        generation.error = "the command wrote no Verilog, SystemVerilog or VHDL file"
        return ""
    generation.generated = [os.path.relpath(p, copy).replace(os.sep, "/") for p in written]
    common = os.path.commonpath([os.path.dirname(p) for p in written])
    generation.output = os.path.relpath(common, copy).replace(os.sep, "/")
    if generation.output == ".":
        generation.output = ""
    return common


def cleanup(generation):
    if generation is not None and generation.copy:
        shutil.rmtree(generation.copy, ignore_errors=True)
        generation.copy = ""
