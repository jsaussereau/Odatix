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
The metrics a workflow or a simulation extracts from its runs.

Both keep them in a "_metrics.yml" file next to their settings, in the same
format: a "metrics" mapping of name to definition, and an optional "metadata"
mapping declaring extra dimensions of the result. Metrics written directly at
the top level of the file (the layout Odatix used before "metadata" existed)
are still read, and are moved under "metrics" the next time the file is
written.
"""

import os

from odatix.workspace.yaml_io import read_document, read_yaml, write_document

__all__ = ["METRICS_FILENAME", "MetricsFile"]

#: Name of the metrics file of a workflow or of a simulation.
METRICS_FILENAME = "_metrics.yml"


class MetricsFile(object):
    """
    The metrics definition file of a workflow or of a simulation.

    ``metrics`` and ``metadata`` are read on first access and written back by
    :meth:`save`, which keeps the comments and the keys the API does not own.
    """

    def __init__(self, path):
        self.path = path
        self._metrics = None
        self._metadata = None

    @property
    def exists(self):
        return os.path.isfile(self.path)

    ######################################
    # Content
    ######################################

    def _load(self):
        if self._metrics is not None:
            return
        data = read_yaml(self.path, default={})
        if not isinstance(data, dict):
            data = {}
        if "metrics" in data:
            metrics = data.get("metrics") or {}
            metadata = data.get("metadata") or {}
        else:
            # Legacy layout: the metrics are the whole document.
            metrics = data
            metadata = {}
        self._metrics = metrics if isinstance(metrics, dict) else {}
        self._metadata = metadata if isinstance(metadata, dict) else {}

    @property
    def metrics(self):
        """The metric definitions, by name."""
        self._load()
        return self._metrics

    @metrics.setter
    def metrics(self, value):
        self._metrics = dict(value) if isinstance(value, dict) else {}
        if self._metadata is None:
            self._metadata = {}

    @property
    def metadata(self):
        """The extra result dimensions declared by the file, by name."""
        self._load()
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        self._load()
        self._metadata = dict(value) if isinstance(value, dict) else {}

    def reload(self):
        self._metrics = None
        self._metadata = None
        return self

    ######################################
    # Editing
    ######################################

    def set(self, name, definition):
        """Add or replace one metric definition."""
        self.metrics[str(name)] = definition
        return self

    def remove(self, name):
        """Drop one metric definition."""
        self.metrics.pop(name, None)
        return self

    def to_dict(self):
        return {"metrics": dict(self.metrics), "metadata": dict(self.metadata)}

    ######################################
    # Writing
    ######################################

    def save(self):
        """
        Write the file back, keeping its comments and anything else it holds.
        """
        self._load()
        data = read_document(self.path)

        if "metrics" not in data:
            # Migrate the legacy layout: what was at the top level is now the
            # content of "metrics", so only "metadata" may stay where it is.
            for key in list(data.keys()):
                if key != "metadata":
                    del data[key]

        data["metrics"] = self._metrics
        if self._metadata:
            data["metadata"] = self._metadata
        else:
            data.pop("metadata", None)

        write_document(self.path, data)
        return self

    def delete(self):
        if self.exists:
            os.remove(self.path)
        return self

    def __repr__(self):
        return "<MetricsFile {0!r}>".format(self.path)
