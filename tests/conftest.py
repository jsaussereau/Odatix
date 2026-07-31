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
Shared pytest fixtures for the Odatix test suite.

The suite runs against the sources tree directly (no install needed):
`sources/` is prepended to sys.path below.
"""

import os
import shutil
import sys
import textwrap

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(REPO_ROOT, "sources")
EXAMPLES_DIR = os.path.join(SOURCES_DIR, "odatix_examples")
INIT_DIR = os.path.join(SOURCES_DIR, "odatix_init")

if SOURCES_DIR not in sys.path:
    sys.path.insert(0, SOURCES_DIR)


@pytest.fixture
def in_tmp_dir(tmp_path, monkeypatch):
    """Run the test from inside an empty temporary directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def example_workspace(tmp_path, monkeypatch):
    """
    A full Odatix workspace in a temporary directory, built from the packaged
    examples (odatix_userconfig + examples RTL sources + odatix.yml).
    """
    shutil.copytree(os.path.join(EXAMPLES_DIR, "odatix_userconfig"), str(tmp_path / "odatix_userconfig"))
    shutil.copytree(os.path.join(EXAMPLES_DIR, "examples"), str(tmp_path / "examples"))
    shutil.copy(os.path.join(INIT_DIR, "odatix.yml"), str(tmp_path / "odatix.yml"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def arch_dir(tmp_path):
    """
    A minimal single-architecture directory tree:
      <tmp>/architectures/my_arch/main/_settings.yml   (param domain settings)
      <tmp>/architectures/my_arch/main/default.txt     (a configuration file)
    Returns the architectures root path.
    """
    domain_dir = tmp_path / "architectures" / "my_arch" / "main"
    domain_dir.mkdir(parents=True)
    (domain_dir / "_settings.yml").write_text(
        textwrap.dedent(
            """\
            use_parameters: true
            start_delimiter: "#("
            stop_delimiter: ")("
            param_target_file: "rtl/top.v"
            """
        )
    )
    (domain_dir / "default.txt").write_text("parameter WIDTH = 8\n")
    return tmp_path / "architectures"


def make_generation_settings(**overrides):
    """A valid generate_configurations settings dict, overridable per test."""
    data = {
        "generate_configurations": True,
        "generate_configurations_settings": {
            "template": "parameter WIDTH = $WIDTH",
            "name": "w$WIDTH",
            "variables": {
                "WIDTH": {"type": "list", "settings": {"list": [8, 16, 32]}},
            },
        },
    }
    data.update(overrides)
    return data
