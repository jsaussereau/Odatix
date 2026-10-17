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
The parameter spaces of the examples must keep resolving to what they resolved
to before the design space was unified.

The reference was recorded from the behaviour that shipped, so a difference
here means a settings file that used to work now describes something else --
which is exactly what the unification promised never to do.

Record a new reference, deliberately, with::

    python3 tests/golden/snapshot_config_space.py --write
"""

import json
import os
import sys

import pytest

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")
if GOLDEN_DIR not in sys.path:
    sys.path.insert(0, GOLDEN_DIR)

import snapshot_config_space  # noqa: E402


@pytest.fixture(scope="module")
def reference():
    if not os.path.isfile(snapshot_config_space.REFERENCE):
        pytest.skip("no recorded reference for the parameter spaces")
    with open(snapshot_config_space.REFERENCE, "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def current():
    return snapshot_config_space.build()


def test_every_example_is_still_there(reference, current):
    assert sorted(current) == sorted(reference)


def test_configuration_names_are_unchanged(reference, current):
    for directory in sorted(reference):
        expected = sorted(reference[directory]["configurations"])
        assert sorted(current[directory]["configurations"]) == expected, directory


def test_configuration_contents_are_unchanged(reference, current):
    for directory in sorted(reference):
        assert current[directory]["configurations"] == reference[directory]["configurations"], directory


def test_variable_values_are_unchanged(reference, current):
    for directory in sorted(reference):
        assert current[directory]["variable_values"] == reference[directory]["variable_values"], directory


def test_variants_are_unchanged(reference, current):
    """
    The variants are the jobs the variables of an instance expand into, so a
    change here changes the result paths of a workspace that did nothing.
    """
    for directory in sorted(reference):
        assert current[directory]["variants"] == reference[directory]["variants"], directory


def test_generation_flags_are_unchanged(reference, current):
    for directory in sorted(reference):
        for key in ("generation_enabled", "generation_valid"):
            assert current[directory][key] == reference[directory][key], "{0} [{1}]".format(directory, key)


def test_the_reference_is_not_empty(reference):
    """A silently empty reference would make every test above pass for nothing."""
    assert len(reference) > 10
    assert any(entry["configurations"] for entry in reference.values())
    assert any(entry["variants"] for entry in reference.values())
