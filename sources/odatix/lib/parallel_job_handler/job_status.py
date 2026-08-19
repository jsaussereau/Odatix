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
How a job status maps to the buckets every monitor counts and filters by.

This lives apart from `handler_core` on purpose: the GUI needs the same
definitions, and importing the handler would drag `curses` into the web
process. `handler_core` computes the snapshot aggregates with them, the GUI
filters with them, and the browser receives them verbatim as
`handler.status_buckets` -- so counting, filtering and sorting can never end up
disagreeing about what "running" means.
"""

RUNNING_STATUSES = ("running", "starting", "export")
QUEUED_STATUSES = ("queued", "paused")
DONE_STATUSES = ("success",)
FAILED_STATUSES = ("failed", "killed", "canceled")

STATUS_BUCKETS = {
    "running": list(RUNNING_STATUSES),
    "queued": list(QUEUED_STATUSES),
    "done": list(DONE_STATUSES),
    "failed": list(FAILED_STATUSES),
}

# Sort priority when sorting by status (most "active" first).
STATUS_SORT_PRIORITY = {
    "running": 0,
    "starting": 1,
    "export": 2,
    "paused": 3,
    "queued": 4,
    "success": 5,
    "failed": 6,
    "killed": 7,
    "canceled": 8,
}


def elapsed_to_seconds(elapsed):
    """Seconds from an "H:MM:SS" elapsed-time string, 0 if unparsable."""
    parts = str(elapsed or "").split(":")
    if len(parts) != 3:
        return 0
    try:
        return max(0, int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
    except Exception:
        return 0
