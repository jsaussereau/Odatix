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
Snapshot of what every parameter space of the examples resolves to.

This is the safety net of the unified design space: it records, for each
settings file shipped with Odatix, the configurations it produces (their names
and their contents) and the variants its variables expand into. Rewriting how
that space is described must not change any of it.

Run it to record a new reference::

    python3 tests/golden/snapshot_config_space.py --write

and see :mod:`tests.test_config_space_golden` for the test that compares the
current behaviour against the recorded one.
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCES = os.path.join(REPO_ROOT, "sources")
if SOURCES not in sys.path:
    sys.path.insert(0, SOURCES)

#: Where the reference snapshot is kept.
REFERENCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_space.json")

#: The example trees walked by the snapshot, relative to the repository root.
EXAMPLE_ROOTS = (
    os.path.join("sources", "odatix_examples", "odatix_userconfig", "architectures"),
    os.path.join("sources", "odatix_examples", "odatix_userconfig", "workflows"),
)


def settings_files(root):
    """Every settings file under a tree, by path relative to the repository."""
    import odatix.lib.hard_settings as hard_settings

    found = []
    absolute_root = os.path.join(REPO_ROOT, root)
    if not os.path.isdir(absolute_root):
        return found
    for directory, _subdirs, files in os.walk(absolute_root):
        if hard_settings.param_settings_filename in files:
            found.append(os.path.relpath(directory, REPO_ROOT))
    return sorted(found)


def snapshot_directory(directory):
    """
    What one settings file resolves to: its generated configurations and the
    variants its variables stand for.
    """
    from odatix.lib.config_generator import ConfigGenerator
    import odatix.lib.virtual_param_domain as virtual_param_domain

    absolute = os.path.join(REPO_ROOT, directory)
    entry = {}

    generator = ConfigGenerator(path=absolute, silent=True)
    entry["generation_enabled"] = bool(generator.enabled)
    entry["generation_valid"] = bool(generator.valid)

    configurations, values = generator.generate()
    entry["configurations"] = {name: content for name, content in sorted(configurations.items())}
    entry["variable_values"] = {name: [str(value) for value in vals] for name, vals in sorted(values.items())}

    settings = virtual_param_domain.load_instance_settings(absolute, "")
    if settings is None:
        entry["variants"] = None
    else:
        variants = virtual_param_domain.build_variants(settings, os.path.join(absolute, "_settings.yml"))
        if variants is None:
            entry["variants"] = "error"
        else:
            entry["variants"] = [
                {
                    "requested_param_domains": sorted(variant.get("requested_param_domains", [])),
                    "substitutions": {k: str(v) for k, v in sorted(variant.get("substitutions", {}).items())},
                }
                for variant in variants
            ]

    return entry


def build():
    """The snapshot of every example, keyed by directory."""
    snapshot = {}
    for root in EXAMPLE_ROOTS:
        for directory in settings_files(root):
            snapshot[directory.replace(os.sep, "/")] = snapshot_directory(directory)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="record the current behaviour as the reference")
    args = parser.parse_args()

    snapshot = build()
    payload = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if args.write:
        with open(REFERENCE, "w") as f:
            f.write(payload)
        print("Recorded {0} parameter spaces in {1}".format(len(snapshot), os.path.relpath(REFERENCE, REPO_ROOT)))
    else:
        sys.stdout.write(payload)

    return 0


if __name__ == "__main__":
    sys.exit(main())
