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
Structured outcome of a "check settings" phase.

The check phase of every run script sorts the requested jobs into categories
(new, cached, invalid, ...) before anything is launched. That classification
used to live in a set of parallel lists per handler, printed by hand and, on the
GUI side, recovered by parsing the printed text back. JobPlan holds it once:

  - the run scripts fill it while they check,
  - the CLI prints it (print_summary),
  - the GUI reads it directly to build the run popup.

Adding a category means adding one entry to CATEGORIES; every consumer follows.
"""

import re

import odatix.lib.printc as printc


class Category:
    NEW = "new"
    OVERWRITE = "overwrite"
    INCOMPLETE = "incomplete"
    CACHED = "cached"
    DAEMON = "daemon"
    ERROR = "error"


# label:       short name, used by the GUI badges
# description: full sentence, used for the CLI checklist and the GUI tooltips
# color:       CLI color of the checklist section
# glyph/style: GUI badge symbol and css status modifier
# runs:        whether the jobs of this category are actually going to be launched
# severity:    display order, most important first (GUI)
# cli_order:   display order of the CLI checklist (least to most severe)
CATEGORIES = {
    Category.ERROR: {
        "glyph": "✗",
        "style": "failed",
        "label": "Invalid",
        "description": "Invalid settings, (skipped, see errors above)",
        "color": printc.colors.RED,
        "runs": False,
        "severity": 0,
        "cli_order": 5,
    },
    Category.OVERWRITE: {
        "glyph": "↻",
        "style": "warning",
        "label": "Overwritten",
        "description": "Existing results (will be overwritten)",
        "color": printc.colors.YELLOW,
        "runs": True,
        "severity": 1,
        "cli_order": 1,
    },
    Category.INCOMPLETE: {
        "glyph": "↻",
        "style": "warning",
        "label": "Incomplete",
        "description": "Incomplete results (will be overwritten)",
        "color": printc.colors.YELLOW,
        "runs": True,
        "severity": 2,
        "cli_order": 2,
    },
    Category.NEW: {
        "glyph": "+",
        "style": "passed",
        "label": "New",
        "description": "New {noun}",
        "color": printc.colors.ENDC,
        "runs": True,
        "severity": 3,
        "cli_order": 4,
    },
    Category.CACHED: {
        "glyph": "=",
        "style": "incomplete",
        "label": "Existing",
        "description": "Existing results (skipped -> use '-o' to overwrite)",
        "color": printc.colors.CYAN,
        "runs": False,
        "severity": 4,
        "cli_order": 0,
    },
    Category.DAEMON: {
        "glyph": "≡",
        "style": "incomplete",
        "label": "In a session",
        "description": "Already managed in a session (skipped)",
        "color": printc.colors.CYAN,
        "runs": False,
        "severity": 5,
        "cli_order": 3,
    },
}

# Categories by display order.
SEVERITY_ORDER = sorted(CATEGORIES, key=lambda name: CATEGORIES[name]["severity"])
CLI_ORDER = sorted(CATEGORIES, key=lambda name: CATEGORIES[name]["cli_order"])


_ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")


def plain(text):
    """
    A display name without its terminal color codes. Job names are built for the
    CLI checklist and may carry them (the grey " @ 250 MHz" suffix, ...).
    """
    return _ANSI_PATTERN.sub("", str(text))


def category_description(category, noun="architectures"):
    """Full description of a category, e.g. for a checklist heading."""
    return CATEGORIES[category]["description"].format(noun=noun)


def meta(category):
    """Display metadata of a category (label, glyph, style, ...)."""
    return CATEGORIES[category]


def runs(category):
    """Whether the jobs of this category are going to be launched."""
    return CATEGORIES.get(category, {}).get("runs", False)


class JobPlan:
    """
    The jobs a check phase found, each with its category and optional details.

    Entries keep insertion order; `name` is the display name already used by the
    CLI checklist, so both front-ends show the exact same wording.
    """

    def __init__(self):
        self.entries = []

    def add(self, name, category, **details):
        """Record one job. `details` holds extra facts to display (tasks, target, ...)."""
        if category not in CATEGORIES:
            raise ValueError("Unknown job category: " + str(category))
        self.entries.append({"name": str(name), "category": category, "details": details})

    def merge(self, other, suffix=""):
        """
        Append the entries of another plan, optionally suffixing their names.
        Used when a single run covers several eda tools: one plan per tool, one
        checklist for the user.
        """
        for entry in other.entries:
            self.entries.append({
                "name": entry["name"] + suffix,
                "category": entry["category"],
                "details": dict(entry["details"]),
            })

    def names(self, category, colored=True):
        """
        Names of the jobs of one category, in insertion order. `colored=False`
        strips the terminal color codes, for anything but a terminal.
        """
        names = [entry["name"] for entry in self.entries if entry["category"] == category]
        return names if colored else [plain(name) for name in names]

    def counts(self):
        counts = {category: 0 for category in CATEGORIES}
        for entry in self.entries:
            counts[entry["category"]] += 1
        return counts

    def run_count(self):
        """How many jobs are actually going to be launched."""
        return sum(1 for entry in self.entries if runs(entry["category"]))

    def sorted_entries(self):
        """Entries by category severity, then by name."""
        return sorted(
            self.entries,
            key=lambda entry: (CATEGORIES[entry["category"]]["severity"], entry["name"].lower()),
        )

    def to_list(self):
        """JSON-serializable form (dcc.Store, daemon api, ...)."""
        return [dict(entry, details=dict(entry["details"])) for entry in self.entries]

    def print_summary(self, noun="architectures"):
        """The CLI checklist: one section per non-empty category."""
        for category in CLI_ORDER:
            names = self.names(category)
            if not names:
                continue
            print()
            printc.bold(category_description(category, noun) + ":")
            printc.color(CATEGORIES[category]["color"])
            for name in names:
                print("  - " + name)
            printc.endc()

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __bool__(self):
        return bool(self.entries)


# Message levels, in display order.
MESSAGE_LEVELS = ["error", "warning", "tip", "note"]
MESSAGE_LEVEL_TITLES = {
    "error": "Errors",
    "warning": "Warnings",
    "tip": "Tips",
    "note": "Notes",
}


class MessageLog:
    """
    The diagnostics emitted during a check phase, deduplicated.

    Fed straight from printc (see printc.collect), so no output parsing is
    involved: `log = MessageLog()` then `with printc.collect(log.add): ...`.
    The same message is usually emitted once per configuration, hence `count`.
    """

    def __init__(self):
        self.messages = []
        self._index = {}

    def add(self, level, message, script=""):
        message = str(message).strip()
        if not message:
            return
        key = (level, message)
        if key in self._index:
            self.messages[self._index[key]]["count"] += 1
            return
        self._index[key] = len(self.messages)
        self.messages.append({"level": level, "message": message, "script": script, "count": 1})

    def of_level(self, level):
        return [message for message in self.messages if message["level"] == level]

    def total(self, level):
        """How many messages of that level were emitted, duplicates included."""
        return sum(message["count"] for message in self.of_level(level))

    def counts(self):
        return {level: len(self.of_level(level)) for level in MESSAGE_LEVELS}

    def to_list(self):
        return [dict(message) for message in self.messages]

    def __len__(self):
        return len(self.messages)

    def __bool__(self):
        return bool(self.messages)
