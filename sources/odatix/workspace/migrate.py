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
Rewrite the settings files of a workspace that still use a former format.

Odatix keeps reading the former formats, and the workspace API already writes
the current one whenever it saves a file. What is missing is a way to have it
done for every file at once, without opening each of them in the GUI: that is
:func:`migrate` (``odatix migrate``). Each file is read, normalized and saved
exactly as the API saves it, so its comments and the keys Odatix does not know
about stay where they are, and the former version is kept next to it as a
``.bak`` file.

What is migrated:

- ``generate_configurations`` / ``generate_configurations_settings`` in the
  settings of an architecture, of a workflow, or of one of their parameter
  domains, which become ``configurations`` and ``variables``;
- ``fmax_lower_bound`` / ``fmax_upper_bound`` in the settings of an
  architecture, which become ``fmax_synthesis`` blocks wherever that keeps
  every job running at the same bounds (see
  :func:`odatix.workspace.architectures.carry_over_legacy_bounds`);
- ``disabled_targets`` in a target file, which become commented-out entries
  of ``targets``;
- metrics written at the top level of a ``_metrics.yml`` file, which move
  under ``metrics``.

The deprecated parameter keys of a simulation (``use_parameters``,
``override_parameters``, ...) are not: replacing them by ``param_domains`` is a
change of design, not of spelling.
"""

import os
import shutil
import tempfile

import odatix.lib.yaml_loader as yaml_loader
from odatix.workspace.architectures import ArchitectureSettings, LEGACY_BOUND_KEYS, legacy_bound_keys
from odatix.workspace.configs import LEGACY_CONFIGURATION_KEYS
from odatix.workspace.metrics import MetricsFile
from odatix.workspace.settings import save_settings
from odatix.workspace.targets import TargetFile
from odatix.workspace.yaml_io import read_yaml, write_text

__all__ = ["Migration", "pending", "plan", "migrate"]

#: Suffix of the copy of a file kept as it was before the migration.
BACKUP_SUFFIX = ".bak"


class Migration(object):
    """
    One settings file written in a former format.

    Attributes:
        path (str): the file.
        kind (str): what it holds ("architecture", "workflow", "domain",
            "targets", "metrics").
        former_keys (list): the former keys found in it.
        changes (list): what the migration changes, one line per key of the
            file (``"- key"`` removed, ``"+ key"`` added, ``"~ key"`` rewritten).
        left (list): what the migration cannot do and leaves to the user.
        backup (str): the copy of the file as it was, once migrated with one.
    """

    def __init__(self, path, kind, former_keys, changes=None, left=None, new_text=None):
        self.path = path
        self.kind = kind
        self.former_keys = list(former_keys)
        self.changes = list(changes) if changes else []
        self.left = list(left) if left else []
        self.new_text = new_text
        self.backup = None

    @property
    def changed(self):
        """Whether the migration rewrites the file."""
        return self.new_text is not None

    def __repr__(self):
        return "<Migration {0} {1}>".format(self.kind, self.path)


######################################
# Finding the files
######################################

def _settings_files(workspace):
    """(path, kind, settings object) of each settings file of a parameter domain."""
    for collection, kind in ((workspace.architectures, "architecture"), (workspace.workflows, "workflow")):
        for instance in collection:
            for domain in instance.domains:
                if os.path.isfile(domain.settings_path):
                    yield domain.settings_path, (kind if domain.is_main else "domain"), domain
    for simulation in workspace.simulations:
        for domain in simulation.domains:
            if not domain.is_main and os.path.isfile(domain.settings_path):
                yield domain.settings_path, "domain", domain


def _target_files(workspace):
    seen = set()
    for tool in workspace.tools.all_names():
        target_file = workspace.targets[tool]
        path = target_file.path
        if path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        yield path, tool


def _metrics_files(workspace):
    for collection in (workspace.workflows, workspace.simulations):
        for instance in collection:
            if os.path.isfile(instance.metrics_path):
                yield instance.metrics_path


######################################
# What is former in a file
######################################

def _former_settings_keys(data, architecture):
    if not isinstance(data, dict):
        return []
    found = [key for key in LEGACY_CONFIGURATION_KEYS if key in data]
    if architecture:
        rules = data.get("overrides")
        rules = [rule for rule in rules if isinstance(rule, dict)] if isinstance(rules, list) else []
        for key, _new in LEGACY_BOUND_KEYS:
            if key in data or any(key in rule for rule in rules):
                found.append(key)
    return found


def _former_metrics_layout(data):
    return isinstance(data, dict) and len(data) > 0 and "metrics" not in data


######################################
# Rewriting a file
######################################

def _read_text(path):
    with open(path, "r") as f:
        return f.read()


def _rewritten(path, write):
    """
    The text `write` gives the file, from a copy of it: what the migration
    would write, without touching the file itself.
    """
    directory = tempfile.mkdtemp(prefix="odatix_migrate_")
    try:
        copy = os.path.join(directory, os.path.basename(path))
        shutil.copyfile(path, copy)
        write(copy, directory)
        return _read_text(copy)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _changes(before, after):
    """One line per top-level key the migration removes, adds or rewrites."""
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    lines = []
    for key in before:
        if key not in after:
            lines.append("- " + str(key))
    for key in after:
        if key not in before:
            lines.append("+ " + str(key))
        elif before[key] != after[key]:
            lines.append("~ " + str(key))
    return lines


def _settings_migration(path, kind, domain):
    data = read_yaml(path, default={})
    architecture = kind == "architecture" and issubclass(domain.settings_class, ArchitectureSettings)
    former = _former_settings_keys(data, architecture)
    if not former:
        return None

    # A fresh read: normalized by from_dict, unlike what an editor may hold.
    settings = domain.settings_class.from_dict(data)
    left = []
    if architecture:
        for key in legacy_bound_keys(settings):
            left.append(
                '"{0}" is kept: rules of "overrides" set it next to rules setting "fmax_synthesis", '
                "and which one wins depends on the job. Write it in the \"fmax_synthesis\" blocks.".format(key)
            )

    return _migration(path, kind, former, lambda copy, _directory: save_settings(settings, copy), left)


def _targets_migration(path, tool):
    data = read_yaml(path, default={})
    if not isinstance(data, dict) or "disabled_targets" not in data:
        return None

    def write(copy, directory):
        TargetFile(None, tool, target_path=directory).save()

    return _migration(path, "targets", ["disabled_targets"], write)


def _metrics_migration(path):
    data = read_yaml(path, default={})
    if not _former_metrics_layout(data):
        return None
    return _migration(path, "metrics", ["metrics at the top level"], lambda copy, _directory: MetricsFile(copy).save())


def _migration(path, kind, former, write, left=None):
    text = _rewritten(path, write)
    before = read_yaml(path, default={})
    original = _read_text(path)
    new_text = text if text != original else None
    changes = []
    if new_text is not None:
        changes = _changes(before, yaml_loader.safe_load(text))
    return Migration(path, kind, former, changes=changes, left=left, new_text=new_text)


######################################
# Entry points
######################################

def pending(workspace):
    """
    The files of a workspace written in a former format, as ``(path, former
    keys)`` pairs. Only reads them: cheap enough for a run or a page to ask
    before suggesting :func:`migrate`.
    """
    found = []
    for path, kind, domain in _settings_files(workspace):
        architecture = kind == "architecture" and issubclass(domain.settings_class, ArchitectureSettings)
        keys = _former_settings_keys(read_yaml(path, default={}), architecture)
        if keys:
            found.append((path, keys))
    for path, _tool in _target_files(workspace):
        data = read_yaml(path, default={})
        if isinstance(data, dict) and "disabled_targets" in data:
            found.append((path, ["disabled_targets"]))
    for path in _metrics_files(workspace):
        if _former_metrics_layout(read_yaml(path, default={})):
            found.append((path, ["metrics at the top level"]))
    return found


def plan(workspace):
    """
    The files of a workspace written in a former format, and what migrating
    them would change, without writing anything.

    Returns:
        list of :class:`Migration`
    """
    migrations = []
    for path, kind, domain in _settings_files(workspace):
        migrations.append(_settings_migration(path, kind, domain))
    for path, tool in _target_files(workspace):
        migrations.append(_targets_migration(path, tool))
    for path in _metrics_files(workspace):
        migrations.append(_metrics_migration(path))
    return [migration for migration in migrations if migration is not None]


def _backup_path(path):
    candidate = path + BACKUP_SUFFIX
    index = 1
    while os.path.exists(candidate):
        candidate = "{0}{1}.{2}".format(path, BACKUP_SUFFIX, index)
        index += 1
    return candidate


def migrate(workspace, dry_run=False, backup=True):
    """
    Rewrite every file of a workspace written in a former format.

    Args:
        workspace: the :class:`~odatix.workspace.Workspace`.
        dry_run (bool): only say what would change.
        backup (bool): keep each file as it was, next to it, with a ``.bak``
            suffix (``.bak.1``, ``.bak.2``, ... when one is already there).

    Returns:
        list of :class:`Migration`, the ones rewritten with their ``backup``.
    """
    migrations = plan(workspace)
    if dry_run:
        return migrations
    for migration in migrations:
        if not migration.changed:
            continue
        if backup:
            migration.backup = _backup_path(migration.path)
            shutil.copy2(migration.path, migration.backup)
        write_text(migration.path, migration.new_text)
    return migrations
