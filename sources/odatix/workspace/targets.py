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
The synthesis targets of an EDA tool.

Each tool has one target file ("target_<tool>.yml") holding the list of targets
its jobs run on, plus whatever else that tool needs (its constraint file, its
install path, ...). Only the "targets" list is consumed by the run flows, so a
target that is turned off is kept in the file as a commented-out entry
("# - <target>"), the way these files have always been written by hand: it
stays visible, and it can be turned back on later.
"""

import copy
import io
import os
import re

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from odatix.workspace.entries import check_name
from odatix.workspace.errors import AlreadyExistsError, NotFoundError
from odatix.workspace.yaml_io import parse_bool, read_yaml

__all__ = ["Target", "TargetFile", "TargetFileCollection"]


# "  - name" (enabled) or "  # - name" (disabled), optional trailing comment
_target_item_pattern = re.compile(r'^\s+-\s*([^#]+?)\s*(?:#.*)?$')
_target_commented_pattern = re.compile(r'^\s*#\s*-\s*([^#]+?)\s*(?:#.*)?$')
_targets_key_pattern = re.compile(r'^targets\s*:')
_commented_target_line_pattern = re.compile(r'^\s*#\s*-\s*\S')


def _scan_targets_block(text):
    """
    Scan the "targets:" block of a target file, line by line, and return the
    ordered list of (name, enabled) entries: plain list items are enabled,
    commented-out items ("# - <target>") are disabled.
    """
    entries = []
    in_block = False
    for line in text.splitlines():
        if _targets_key_pattern.match(line):
            in_block = True
            continue
        if not in_block:
            continue
        item_match = _target_item_pattern.match(line)
        commented_match = _target_commented_pattern.match(line)
        if item_match:
            entries.append((item_match.group(1).strip().strip("\"'"), True))
        elif commented_match:
            entries.append((commented_match.group(1).strip().strip("\"'"), False))
        elif line.strip() == "" or line.lstrip().startswith("#"):
            continue  # blank lines and other comments do not end the block
        elif not line[0].isspace():
            in_block = False  # next top-level key
    return entries


def _scrub_commented_targets(commented_map, key):
    """
    Remove "# - <target>" lines from the ruamel comments attached to a key,
    keeping any other comment line. Tokens left empty are dropped entirely
    (empty comment tokens corrupt the ruamel emitter output).
    """
    ca_items = getattr(getattr(commented_map, "ca", None), "items", None)
    if not ca_items or key not in ca_items:
        return

    def scrub_token(token):
        if token is None or not hasattr(token, "value"):
            return token
        kept = [
            line for line in token.value.splitlines(keepends=True)
            if not _commented_target_line_pattern.match(line)
        ]
        token.value = "".join(kept)
        return token if token.value != "" else None

    slots = ca_items[key]
    for index, slot in enumerate(slots):
        if isinstance(slot, list):
            kept_tokens = [token for token in (scrub_token(item) for item in slot) if token is not None]
            slots[index] = kept_tokens if kept_tokens else None
        else:
            slots[index] = scrub_token(slot)
    if all(slot is None for slot in slots):
        del ca_items[key]


######################################
# Targets
######################################

class Target(object):
    """
    One synthesis target of a tool.

    A target that is not enabled is remembered but not run.
    """

    def __init__(self, name, enabled=True, script_copy_enable=False, script_copy_source="", original_name=None):
        self.name = str(name)
        self.enabled = bool(enabled)
        self.script_copy_enable = parse_bool(script_copy_enable, False)
        self.script_copy_source = str(script_copy_source or "")
        #: Name this target had in the file, so its settings follow a rename.
        self.original_name = str(original_name) if original_name else self.name

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, Target):
            return data
        data = data if isinstance(data, dict) else {}
        return cls(
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            script_copy_enable=data.get("script_copy_enable", False),
            script_copy_source=data.get("script_copy_source", ""),
            original_name=data.get("original_name"),
        )

    def to_dict(self):
        return {
            "name": self.name,
            "enabled": self.enabled,
            "script_copy_enable": self.script_copy_enable,
            "script_copy_source": self.script_copy_source,
        }

    def enable(self):
        self.enabled = True
        return self

    def disable(self):
        self.enabled = False
        return self

    def __repr__(self):
        return "<Target {0!r}{1}>".format(self.name, "" if self.enabled else " (disabled)")

    def __eq__(self, other):
        if isinstance(other, Target):
            return self.to_dict() == other.to_dict()
        if isinstance(other, dict):
            return self.to_dict() == other
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result


class TargetFile(object):
    """
    The target file of one EDA tool.

    Changes made through this object are held in memory until :meth:`save`,
    which rewrites the target list while leaving the rest of the file (its
    comments, its constraint file, its install path, ...) as it was.
    """

    def __init__(self, workspace, tool, target_path=None):
        self.workspace = workspace
        self.tool = str(tool)
        #: Directory the target files live in. Taken from the workspace unless
        #: given here, so a target file can also be worked on on its own.
        self._target_path = target_path
        self._targets = None

    ######################################
    # Location
    ######################################

    @property
    def target_path(self):
        if self._target_path is not None:
            return self._target_path
        return self.workspace.paths.target_path

    @property
    def fallback_path(self):
        """
        Where a target file kept at the old default location is looked up. It
        belongs to the workspace, so it is resolved against it and never against
        the directory the caller happens to be in.
        """
        if self.workspace is None:
            return None
        return self.workspace.paths.target_fallback_path

    @property
    def path(self):
        """
        Path of the target file, as Odatix resolves it: the name comes from the
        tool ("target_file" in its tool.yml), and an existing file found next to
        the workspace settings is edited where it is rather than moved.
        """
        import odatix.lib.eda_tools as eda_tools

        return eda_tools.resolve_target_file(self.tool, self.target_path, fallback_dir=self.fallback_path)

    @property
    def exists(self):
        return os.path.isfile(self.path)

    ######################################
    # Targets
    ######################################

    def _load(self):
        if self._targets is not None:
            return self._targets

        path = self.path
        data = read_yaml(path, default={})
        if not isinstance(data, dict):
            data = {}

        # File order, with the commented-out entries as disabled targets.
        entries = []
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    entries = _scan_targets_block(f.read())
            except OSError:
                entries = []

        seen = set(name for name, _enabled in entries)

        # Entries only the YAML parser sees (a flow-style list, for instance).
        enabled_names = data.get("targets") or []
        disabled_names = data.get("disabled_targets") or []
        if isinstance(enabled_names, list):
            entries += [(str(name), True) for name in enabled_names if str(name) not in seen]
            seen.update(str(name) for name in enabled_names)
        if isinstance(disabled_names, list):
            entries += [(str(name), False) for name in disabled_names if str(name) not in seen]

        target_settings = data.get("target_settings")
        if not isinstance(target_settings, dict):
            target_settings = {}

        targets = []
        added = set()
        for name, enabled in entries:
            name = str(name)
            if name == "" or name in added:
                continue
            added.add(name)
            settings = target_settings.get(name)
            settings = settings if isinstance(settings, dict) else {}
            targets.append(Target(
                name=name,
                enabled=enabled,
                script_copy_enable=settings.get("script_copy_enable", False),
                script_copy_source=settings.get("script_copy_source", ""),
            ))
        self._targets = targets
        return self._targets

    @property
    def targets(self):
        """The targets of the tool, in file order."""
        return self._load()

    @targets.setter
    def targets(self, value):
        self._targets = [Target.from_dict(target) for target in (value or [])]

    def reload(self):
        self._targets = None
        return self

    def names(self):
        return [target.name for target in self.targets]

    def enabled_names(self):
        """Names of the targets the jobs of this tool actually run on."""
        return [target.name for target in self.targets if target.enabled]

    def __iter__(self):
        return iter(self.targets)

    def __len__(self):
        return len(self.targets)

    def __contains__(self, item):
        name = item.name if isinstance(item, Target) else item
        return any(target.name == name for target in self.targets)

    def __getitem__(self, name):
        for target in self.targets:
            if target.name == name:
                return target
        raise NotFoundError("No such target for tool '{0}': '{1}'.".format(self.tool, name))

    def get(self, name, default=None):
        for target in self.targets:
            if target.name == name:
                return target
        return default

    def exists_target(self, name):
        return name in self

    ######################################
    # Editing
    ######################################

    def add(self, name, enabled=True, script_copy_enable=False, script_copy_source="", save=True):
        """Add a target and, unless told otherwise, write the file back."""
        name = check_name(name, "target")
        if name in self:
            raise AlreadyExistsError("Target '{0}' already exists.".format(name))
        target = Target(name, enabled, script_copy_enable, script_copy_source)
        self.targets.append(target)
        if save:
            self.save()
        return target

    def remove(self, name, save=True):
        """Remove a target and its per-target settings."""
        target = self[name]
        self._targets = [item for item in self.targets if item.name != target.name]
        if save:
            self.save()
        return self

    def rename(self, name, new_name, save=True):
        """Rename a target, carrying its per-target settings over."""
        target = self[name]
        new_name = check_name(new_name, "target")
        if new_name != target.name and new_name in self:
            raise AlreadyExistsError("Target '{0}' already exists.".format(new_name))
        target.name = new_name
        if save:
            self.save()
        return target

    def duplicate(self, name, new_name, save=True):
        """Copy a target, per-target settings included."""
        source = self[name]
        new_name = check_name(new_name, "target")
        if new_name in self:
            raise AlreadyExistsError("Target '{0}' already exists.".format(new_name))
        copied = Target.from_dict(source.to_dict())
        copied.name = new_name
        copied.original_name = source.name
        self.targets.append(copied)
        if save:
            self.save()
        return copied

    def enable(self, name, save=True):
        self[name].enable()
        if save:
            self.save()
        return self

    def disable(self, name, save=True):
        self[name].disable()
        if save:
            self.save()
        return self

    ######################################
    # Writing
    ######################################

    def save(self):
        """
        Write the target list back, keeping the comments and every other key of
        the file. Disabled targets are written as commented-out entries.
        """
        path = self.path
        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True

        settings = None
        if os.path.exists(path):
            with open(path, "r") as f:
                settings = yaml_obj.load(f)
        if settings is None:
            settings = CommentedMap()

        old_target_settings = settings.get("target_settings")
        if not isinstance(old_target_settings, dict):
            old_target_settings = {}

        ordered = []  # (name, enabled), deduplicated
        new_target_settings = CommentedMap()
        seen = set()
        for target in self.targets:
            name = str(target.name).strip()
            original_name = str(target.original_name or name)
            if name == "":
                name = original_name
            if name == "" or name in seen:
                continue
            seen.add(name)
            ordered.append((name, bool(target.enabled)))

            # Carry over existing per-target settings (possibly under the old name)
            per_target = old_target_settings.get(original_name, old_target_settings.get(name))
            per_target = copy.deepcopy(per_target) if isinstance(per_target, dict) else CommentedMap()
            if target.script_copy_enable:
                per_target["script_copy_enable"] = True
                per_target["script_copy_source"] = str(target.script_copy_source or "")
            else:
                per_target.pop("script_copy_enable", None)
                per_target.pop("script_copy_source", None)
            if per_target:
                new_target_settings[name] = per_target

        # The commented-out entries are re-emitted below: drop the ones attached
        # as comments to the "targets" key (the comments of the old list items go
        # away with the list itself).
        _scrub_commented_targets(settings, "targets")

        # The whole block is rewritten textually below ("targets: []" placeholder)
        settings["targets"] = []
        settings.pop("disabled_targets", None)  # legacy representation
        if new_target_settings:
            settings["target_settings"] = new_target_settings
        else:
            settings.pop("target_settings", None)

        buffer = io.StringIO()
        yaml_obj.dump(settings, buffer)
        text = buffer.getvalue()

        if ordered:
            block_lines = ["targets:"]
            for name, enabled in ordered:
                block_lines.append("  - {0}".format(name) if enabled else "  # - {0}".format(name))
            # Only the placeholder line is replaced: letting the pattern eat the
            # surrounding whitespace would drop the newline that ends the file.
            text = re.sub(r"(?m)^targets:[ \t]*\[\][ \t]*$", lambda _: "\n".join(block_lines), text, count=1)

        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

        for target in self.targets:
            target.original_name = target.name
        return self

    ######################################
    # Other settings of the file
    ######################################

    def settings(self):
        """
        Everything the target file holds, as plain values. Useful to read the
        keys that belong to the tool rather than to the target list (its
        constraint file, its install path, ...).
        """
        data = read_yaml(self.path, default={})
        return data if isinstance(data, dict) else {}

    def __repr__(self):
        return "<TargetFile {0!r} {1}>".format(self.tool, self.names())


class TargetFileCollection(object):
    """
    The target files of a workspace, one per EDA tool: ``ws.targets["vivado"]``.
    """

    def __init__(self, workspace):
        self.workspace = workspace

    def __getitem__(self, tool):
        return TargetFile(self.workspace, tool)

    def get(self, tool, default=None):
        target_file = TargetFile(self.workspace, tool)
        return target_file if target_file.exists else default

    def __contains__(self, tool):
        return TargetFile(self.workspace, tool).exists

    def names(self):
        """Tools this workspace has a target file for."""
        import odatix.lib.eda_tools as eda_tools

        return [tool for tool in eda_tools.list_tools() if TargetFile(self.workspace, tool).exists]

    def __iter__(self):
        for tool in self.names():
            yield TargetFile(self.workspace, tool)

    def __repr__(self):
        return "<TargetFileCollection {0}>".format(self.names())
