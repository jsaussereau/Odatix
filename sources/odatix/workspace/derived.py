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
Derived metrics: metrics computed from the ones the runs produced.

A workspace declares them in one file, holding the metrics themselves and the
groups they are computed over. Deriving nothing is the normal state of a
workspace, so a missing file is not an error.
"""

import os

from odatix.workspace.yaml_io import read_document, read_yaml, write_document

__all__ = ["DerivedMetricsFile"]


class DerivedMetricsFile(object):
    """
    The derived metrics file of a workspace.
    """

    def __init__(self, path):
        self.path = path
        self._groups = None
        self._metrics = None

    @property
    def exists(self):
        return os.path.isfile(self.path)

    ######################################
    # Content
    ######################################

    def _load(self):
        if self._groups is not None:
            return
        data = read_yaml(self.path, default={})
        if not isinstance(data, dict):
            data = {}
        groups = data.get("groups")
        metrics = data.get("derived_metrics")
        self._groups = groups if isinstance(groups, dict) else {}
        self._metrics = metrics if isinstance(metrics, dict) else {}

    @property
    def groups(self):
        """The groups the derived metrics are computed over, by name."""
        self._load()
        return self._groups

    @groups.setter
    def groups(self, value):
        self._load()
        self._groups = dict(value) if isinstance(value, dict) else {}

    @property
    def metrics(self):
        """The derived metric definitions, by name."""
        self._load()
        return self._metrics

    @metrics.setter
    def metrics(self, value):
        self._load()
        self._metrics = dict(value) if isinstance(value, dict) else {}

    def reload(self):
        self._groups = None
        self._metrics = None
        return self

    ######################################
    # Editing
    ######################################

    def set(self, name, definition):
        """Add or replace one derived metric."""
        self.metrics[str(name)] = definition
        return self

    def remove(self, name):
        self.metrics.pop(name, None)
        return self

    def set_group(self, name, definition):
        """Add or replace one group."""
        self.groups[str(name)] = definition
        return self

    def remove_group(self, name):
        self.groups.pop(name, None)
        return self

    def to_dict(self):
        return {"groups": dict(self.groups), "derived_metrics": dict(self.metrics)}

    ######################################
    # Writing
    ######################################

    def save(self):
        """
        Write the file back, keeping its comments and any top-level key the API
        does not own.
        """
        self._load()
        document = read_document(self.path)
        document["groups"] = self._groups if self._groups else {}
        document["derived_metrics"] = self._metrics if self._metrics else {}
        write_document(self.path, document)
        return self

    def __repr__(self):
        return "<DerivedMetricsFile {0!r}>".format(self.path)
