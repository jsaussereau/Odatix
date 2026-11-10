#!/usr/bin/env python3
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
Bench of "odatix init --detect" on known open-source HDL projects, each pinned
to a commit (detect_projects.yml next to this file): it tells whether a change
of the detection makes it better or worse on real projects, not only on the
synthetic ones of test_project_detect.py.

    python tests/bench/run_detect_bench.py                # every project
    python tests/bench/run_detect_bench.py serv ibex      # some of them
    python tests/bench/run_detect_bench.py --light        # without the heavy ones
    python tests/bench/run_detect_bench.py --record out.yml   # what is found now, to review

Projects are cloned once (shallow, at their commit) into the cache directory
(--cache, $ODATIX_BENCH_CACHE, or ~/.cache/odatix/detect_bench). Generators are
never run: that would execute the code of the projects. A project whose RTL is
generated is checked on the generation found instead.

Each expectation is a check; "known" lists the checks that fail today for a
known reason: they are reported, not counted as regressions, and a known check
that passes is reported as fixed. The exit code is 1 when a check that is not
known fails.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "sources"))

import yaml  # noqa: E402

PROJECTS_FILE = os.path.join(HERE, "detect_projects.yml")
DEFAULT_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "odatix", "detect_bench")


def load_projects(path=PROJECTS_FILE):
    with open(path) as f:
        return yaml.safe_load(f)["projects"]


def _git(args, cwd, timeout=900):
    return subprocess.run(["git"] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=timeout)


def fetch(project, cache):
    """The project checked out at its commit in the cache, cloned when missing."""
    path = os.path.join(cache, project["name"])
    marker = os.path.join(path, ".odatix_bench_commit")
    if os.path.isfile(marker) and open(marker).read().strip() == project["commit"]:
        return path
    os.makedirs(path, exist_ok=True)
    if not os.path.isdir(os.path.join(path, ".git")):
        _git(["init", "-q"], path)
        _git(["remote", "add", "origin", project["url"]], path)
    result = _git(["fetch", "-q", "--depth", "1", "origin", project["commit"]], path)
    if result.returncode != 0:
        raise RuntimeError("cannot fetch {0} at {1}: {2}".format(project["url"], project["commit"], result.stdout.strip()))
    _git(["checkout", "-q", "--force", "FETCH_HEAD"], path)
    if project.get("submodules"):
        result = _git(["submodule", "update", "-q", "--init", "--recursive", "--depth", "1"], path, timeout=3600)
        if result.returncode != 0:
            raise RuntimeError("cannot fetch the submodules of {0}: {1}".format(project["name"], result.stdout.strip()))
    with open(marker, "w") as f:
        f.write(project["commit"])
    return path


def observe(path, project):
    """What the detection finds, as plain data."""
    from odatix.lib import project_detect
    start = time.time()
    detection = project_detect.detect_project(path, top=project.get("top_given", ""))
    root = detection.root
    generator = detection.generator
    return {
        "origin": detection.origin,
        "files": len(detection.files),
        "top": detection.top.value if detection.top else "",
        "top_alternatives": list(detection.top.alternatives) if detection.top else [],
        "clock": detection.clock.value if detection.clock else "",
        "reset": detection.reset.value if detection.reset else "",
        "elaborates": detection.validation.ok,
        "tool": detection.validation.tool,
        "errors": detection.validation.errors[:3],
        "fixes": len(detection.validation.fixes),
        "needs_generation": detection.needs_generation,
        "generator": generator.name if generator else "",
        "command": generator.command if generator else "",
        "variants": sorted(detection.variants),
        "seconds": round(time.time() - start, 1),
        "root": root,
    }


def checks(expect, seen):
    """(name, passed, detail) for each expectation of a project."""
    results = []
    for key, wanted in sorted(expect.items()):
        if key == "files_min":
            results.append((key, seen["files"] >= wanted, "{0} files (at least {1})".format(seen["files"], wanted)))
        elif key == "files_max":
            results.append((key, seen["files"] <= wanted, "{0} files (at most {1})".format(seen["files"], wanted)))
        elif key == "origin":
            results.append((key, seen["origin"].startswith(wanted), seen["origin"]))
        elif key == "top_in_alternatives":
            results.append((key, wanted == seen["top"] or wanted in seen["top_alternatives"],
                            "{0} (alternatives: {1})".format(seen["top"], ", ".join(seen["top_alternatives"][:4]))))
        elif key == "command_contains":
            results.append((key, wanted in seen["command"], seen["command"]))
        else:
            results.append((key, seen.get(key) == wanted, repr(seen.get(key))))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="*", help="projects to run (all by default)")
    parser.add_argument("--cache", default=os.environ.get("ODATIX_BENCH_CACHE", DEFAULT_CACHE))
    parser.add_argument("--light", action="store_true", help="leave out the projects marked heavy")
    parser.add_argument("--record", metavar="FILE", help="write what is found, to review before updating the expectations")
    parser.add_argument("--json", metavar="FILE", help="write the full report as JSON")
    args = parser.parse_args(argv)

    projects = [p for p in load_projects() if (not args.names or p["name"] in args.names)
                and not (args.light and p.get("heavy"))]
    os.makedirs(args.cache, exist_ok=True)
    report, regressions, fixed, recorded = [], 0, 0, {}
    for project in projects:
        name = project["name"]
        try:
            path = fetch(project, args.cache)
            seen = observe(path, project)
        except Exception as exception:  # one broken project must not hide the others
            print("{0:<22} ERROR {1}".format(name, exception))
            report.append({"name": name, "error": str(exception)})
            regressions += 1
            continue
        known = project.get("known") or {}
        lines = []
        for check, passed, detail in checks(project.get("expect") or {}, seen):
            if passed and check in known:
                status = "FIXED"
                fixed += 1
            elif passed:
                status = "ok"
            elif check in known:
                status = "known"
            else:
                status = "FAIL"
                regressions += 1
            lines.append((status, check, detail, known.get(check, "")))
        worst = "FAIL" if any(l[0] == "FAIL" for l in lines) else "known" if any(l[0] == "known" for l in lines) else "ok"
        print("{0:<22} {1:<5} {2:<34} {3:>4} files  top {4:<24} {5:>6.1f} s".format(
            name, worst, seen["origin"][:34], seen["files"], seen["top"][:24] or "-", seen["seconds"]))
        for status, check, detail, reason in lines:
            if status != "ok":
                print("    {0:<5} {1}: {2}{3}".format(status, check, detail, "  [" + reason + "]" if reason else ""))
        report.append({"name": name, "seen": seen, "checks": [list(l) for l in lines]})
        recorded[name] = {k: v for k, v in seen.items() if k not in ("root", "errors", "seconds")}
    print("\n{0} project(s), {1} regression(s), {2} known failure(s) fixed".format(len(projects), regressions, fixed))
    if args.record:
        with open(args.record, "w") as f:
            yaml.safe_dump(recorded, f, sort_keys=True, allow_unicode=True)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
