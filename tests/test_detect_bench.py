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
The bench of "odatix init --detect" on real projects (tests/bench). It clones
them, hence runs only when asked: ODATIX_DETECT_BENCH=1 (all projects) or
ODATIX_DETECT_BENCH=light (without the heavy ones), or "make detect-bench".
The file describing the projects is checked every time.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench"))
import run_detect_bench as bench  # noqa: E402

PROJECTS = bench.load_projects()
EXPECTATIONS = {"origin", "top", "top_in_alternatives", "clock", "reset", "files_min", "files_max", "elaborates",
                "needs_generation", "generator", "command_contains"}
MODE = os.environ.get("ODATIX_DETECT_BENCH", "")


class TestProjectsFile:
    def test_projects_are_pinned_and_unique(self):
        names = [p["name"] for p in PROJECTS]
        assert len(names) == len(set(names))
        for project in PROJECTS:
            assert re.match(r"^[0-9a-f]{40}$", project["commit"]), project["name"]
            assert project["url"].startswith("https://")

    def test_expectations_are_known_keys(self):
        for project in PROJECTS:
            expect = project.get("expect") or {}
            assert set(expect) <= EXPECTATIONS, project["name"]
            # a known failure must name an expectation, and say why
            for check, reason in (project.get("known") or {}).items():
                assert check in expect and reason, project["name"]

    def test_checks(self):
        seen = {"origin": "FuseSoC (serv.core)", "files": 17, "top": "serv_rf_top", "top_alternatives": ["serv_top"],
                "clock": "clk", "elaborates": True, "command": ""}
        results = dict((name, passed) for name, passed, _ in bench.checks(
            {"origin": "FuseSoC", "files_min": 10, "files_max": 12, "top_in_alternatives": "serv_top", "clock": "clk_i"},
            seen))
        assert results == {"origin": True, "files_min": True, "files_max": False, "top_in_alternatives": True, "clock": False}


@pytest.mark.bench
@pytest.mark.skipif(not MODE, reason="clones real projects: set ODATIX_DETECT_BENCH=1 (or light) to run it")
@pytest.mark.parametrize("project", [p for p in PROJECTS if not (MODE == "light" and p.get("heavy"))],
                         ids=lambda p: p["name"])
def test_detect_real_project(project):
    cache = os.environ.get("ODATIX_BENCH_CACHE", bench.DEFAULT_CACHE)
    seen = bench.observe(bench.fetch(project, cache), project)
    known = project.get("known") or {}
    failed = ["{0}: {1}".format(name, detail) for name, passed, detail in bench.checks(project.get("expect") or {}, seen)
              if not passed and name not in known]
    assert not failed, "; ".join(failed)
