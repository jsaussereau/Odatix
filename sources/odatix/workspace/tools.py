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
EDA tools: what a workspace runs its jobs with.

A tool is a directory holding a "tool.yml" (what it can run, and how) and
usually a "metrics.yml" (what to read from its reports). Odatix ships a set of
built-in tools; a workspace can define tools of its own, and can also put an
*overlay* on a built-in one: a file holding the flows it adds to it and the
settings it overrides, everything else still coming from the built-in
definition. Odatix merges the two at run time, and so does
:attr:`Tool.effective_settings`.

The commands of a tool are grouped into flows (one flow per way of running it),
each declaring, per platform and per job type, either a single command or a
sequence of resumable steps. A job type a flow says nothing about is inherited
from the tool's default flow.
"""

import copy
import os

from natsort import natsorted
from ruamel.yaml.comments import CommentedMap, CommentedSeq

import odatix.lib.hard_settings as hard_settings
from odatix.lib.utils import copytree
from odatix.workspace.entries import Collection, Entry, check_name
from odatix.workspace.errors import AlreadyExistsError, NotFoundError
from odatix.workspace.yaml_io import read_document, read_yaml, write_document

__all__ = [
    "TOOL_SETTINGS_FILENAME",
    "TOOL_METRICS_FILENAME",
    "PLATFORMS",
    "JOB_TYPES",
    "STEPPED_JOB_TYPES",
    "OVERRIDABLE_KEYS",
    "METRIC_SECTIONS",
    "Step",
    "JobExecution",
    "Flow",
    "ToolFormat",
    "ToolSettings",
    "ToolMetrics",
    "Tool",
    "ToolCollection",
]

#: Name of the settings file of a tool.
TOOL_SETTINGS_FILENAME = hard_settings.tool_settings_filename  # "tool.yml"

#: Name of the metrics file of a tool.
TOOL_METRICS_FILENAME = "metrics.yml"

#: The platform sections of a tool.yml, in render order.
PLATFORMS = ("unix", "windows")

#: The job types a flow declares a command (or steps) for, in render order.
JOB_TYPES = ("tool_test", "fmax_synthesis", "custom_freq_synthesis", "pnr", "analysis")

#: The job types that can be split into resumable steps. Checking that the tool
#: is installed is a single command by nature, so it is not one of them.
STEPPED_JOB_TYPES = ("fmax_synthesis", "custom_freq_synthesis", "pnr", "analysis")

#: Settings of a built-in tool a workspace may override, i.e. everything but its
#: flows: the built-in flows and their commands belong to Odatix.
OVERRIDABLE_KEYS = (
    "label", "description", "icon", "process_group",
    "report_path", "target_file", "default_metrics_file",
)

#: The metric sections of a tool metrics.yml, in render order, with a label.
METRIC_SECTIONS = [
    ("fmax_synthesis_metrics", "Fmax synthesis metrics"),
    ("custom_freq_synthesis_metrics", "Custom frequency synthesis metrics"),
    ("pnr_metrics", "Place & route metrics"),
    ("metrics", "Common metrics"),
]


def _as_command_list(commands):
    """Normalize a command (a list, or a text with one token per line) to a list."""
    if isinstance(commands, str):
        commands = [line.strip() for line in commands.splitlines() if line.strip()]
    if isinstance(commands, (list, tuple)):
        return [str(command) for command in commands if str(command).strip() != ""]
    return []


def _as_marker_list(markers):
    """Normalize markers (a list, or a comma-separated text) to a list."""
    if isinstance(markers, str):
        return [marker.strip() for marker in markers.split(",") if marker.strip() != ""]
    if isinstance(markers, (list, tuple)):
        return [str(marker) for marker in markers if str(marker).strip() != ""]
    return []


######################################
# What a flow runs
######################################

class Step(object):
    """One resumable step of a job type."""

    def __init__(self, name, command=None, default=False):
        self.name = str(name).strip()
        self.command = _as_command_list(command)
        #: Whether a run that is not told where to stop stops after this step.
        self.default = bool(default)

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, Step):
            return data
        data = data if isinstance(data, dict) else {}
        return cls(data.get("name", ""), data.get("command"), data.get("default", False))

    def to_dict(self):
        return {"name": self.name, "command": list(self.command), "default": self.default}

    def __repr__(self):
        return "<Step {0!r}>".format(self.name)


class JobExecution(object):
    """
    What one flow runs for one job type on one platform.

    Three modes: "inherit" (nothing declared, the tool's default flow applies),
    "command" (a single command) and "steps" (a sequence of resumable steps).
    """

    def __init__(self, mode="inherit", command=None, steps=None):
        self.mode = mode if mode in ("inherit", "command", "steps") else "inherit"
        self.command = _as_command_list(command)
        self.steps = [Step.from_dict(step) for step in (steps or [])]

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, JobExecution):
            return data
        data = data if isinstance(data, dict) else {}
        return cls(data.get("mode", "inherit"), data.get("command"), data.get("steps"))

    def to_dict(self):
        return {
            "mode": self.mode,
            "command": list(self.command),
            "steps": [step.to_dict() for step in self.steps],
        }

    def __repr__(self):
        return "<JobExecution {0}>".format(self.mode)


class Flow(object):
    """
    One way of running a tool: a set of commands, per platform and job type.
    """

    def __init__(self, name, label="", description="", icon="", metrics_file="",
                 is_default=False, platforms=None):
        self.name = str(name).strip()
        self.label = str(label or "")
        self.description = str(description or "")
        self.icon = str(icon or "")
        self.metrics_file = str(metrics_file or "")
        self.is_default = bool(is_default)
        self.platforms = {}
        for platform in PLATFORMS:
            section = (platforms or {}).get(platform, {})
            self.platforms[platform] = dict(
                (job_type, JobExecution.from_dict((section or {}).get(job_type)))
                for job_type in JOB_TYPES
            )

    ######################################
    # Commands
    ######################################

    def execution(self, job_type, platform="unix"):
        """What this flow runs for a job type on a platform."""
        if job_type not in JOB_TYPES:
            raise NotFoundError("Unknown job type: '{0}'.".format(job_type))
        return self.platforms[platform][job_type]

    def command(self, job_type, platform="unix"):
        """The command of a job type, or an empty list when it is not a plain command."""
        execution = self.execution(job_type, platform)
        return list(execution.command) if execution.mode == "command" else []

    def steps(self, job_type, platform="unix"):
        """The steps of a job type, or an empty list when it is not run in steps."""
        execution = self.execution(job_type, platform)
        return list(execution.steps) if execution.mode == "steps" else []

    def set_command(self, job_type, command, platform="unix"):
        """Make a job type run one command."""
        self.platforms[platform][job_type] = JobExecution("command", command=command)
        return self

    def set_steps(self, job_type, steps, platform="unix"):
        """
        Make a job type run a sequence of resumable steps. Each step is a
        ``{"name", "command", "default"}`` mapping or a :class:`Step`.
        """
        if job_type not in STEPPED_JOB_TYPES:
            raise NotFoundError("Job type '{0}' cannot be split into steps.".format(job_type))
        self.platforms[platform][job_type] = JobExecution("steps", steps=steps)
        return self

    def inherit(self, job_type, platform="unix"):
        """Declare nothing for a job type, so the default flow's commands apply."""
        self.platforms[platform][job_type] = JobExecution("inherit")
        return self

    ######################################
    # Conversion
    ######################################

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, Flow):
            return data
        data = data if isinstance(data, dict) else {}
        return cls(
            name=data.get("name", ""),
            label=data.get("label", ""),
            description=data.get("description", ""),
            icon=data.get("icon", ""),
            metrics_file=data.get("metrics_file", ""),
            is_default=data.get("is_default", False),
            platforms=data.get("platforms"),
        )

    def to_dict(self):
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "icon": self.icon,
            "metrics_file": self.metrics_file,
            "is_default": self.is_default,
            "platforms": dict(
                (platform, dict((job, execution.to_dict()) for job, execution in jobs.items()))
                for platform, jobs in self.platforms.items()
            ),
        }

    def declares_nothing(self):
        """
        True when this flow says nothing of its own: no metadata, and not a
        single command or step, on any platform. Such a flow is what reading an
        empty file yields, and writing it back would only add noise.
        """
        if any(getattr(self, key) for key in ("label", "description", "icon", "metrics_file")):
            return False
        for jobs in self.platforms.values():
            for execution in jobs.values():
                if execution.mode == "command" and execution.command:
                    return False
                if execution.mode == "steps" and execution.steps:
                    return False
        return True

    def __repr__(self):
        return "<Flow {0!r}{1}>".format(self.name, " (default)" if self.is_default else "")


def _read_platform_section(section):
    """
    Read what one platform section declares for each job type.
    """
    section = section if isinstance(section, dict) else {}
    jobs = {}
    for job_type in JOB_TYPES:
        if section.get(job_type + "_command") is not None:
            jobs[job_type] = JobExecution("command", command=_as_command_list(section.get(job_type + "_command")))
        elif job_type in STEPPED_JOB_TYPES and isinstance(section.get(job_type + "_steps"), list):
            steps = []
            for entry in section.get(job_type + "_steps"):
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", "") or "").strip()
                if name == "":
                    continue
                steps.append(Step(name, entry.get("command"), entry.get("default", False)))
            jobs[job_type] = JobExecution("steps", steps=steps)
        else:
            jobs[job_type] = JobExecution("inherit")
    return jobs


def _write_platform_section(jobs):
    """
    Build the "unix"/"windows" section of a flow from what it runs. A job type
    left on "inherit" declares nothing.
    """
    section = CommentedMap()
    for job_type in JOB_TYPES:
        execution = jobs.get(job_type)
        if execution is None:
            continue
        if execution.mode == "command":
            commands = _as_command_list(execution.command)
            if commands:
                section[job_type + "_command"] = CommentedSeq(commands)
        elif execution.mode == "steps" and job_type in STEPPED_JOB_TYPES:
            steps_seq = CommentedSeq()
            for step in execution.steps:
                commands = _as_command_list(step.command)
                if step.name == "" or not commands:
                    continue
                item = CommentedMap()
                item["name"] = step.name
                item["command"] = CommentedSeq(commands)
                # Only the step the flow stops at by default says so.
                if step.default:
                    item["default"] = True
                steps_seq.append(item)
            if len(steps_seq) > 0:
                section[job_type + "_steps"] = steps_seq
    return section


######################################
# Log formatting
######################################

class ToolFormat(object):
    """
    How the output of a tool is read: which markers make a line an error or a
    warning, which ones carry a tag, and what to rewrite in it.
    """

    def __init__(self, logs=None, tags=None, replace=None):
        self.logs = dict((str(level), _as_marker_list(markers)) for level, markers in (logs or {}).items())
        self.tags = dict((str(tag), _as_marker_list(markers)) for tag, markers in (tags or {}).items())
        self.replace = self._read_replace(replace)

    @staticmethod
    def _read_replace(replace):
        """
        Read the replacement list, accepting both the file form
        (``{pattern: replacement}``) and the pair form
        (``{"pattern": ..., "replacement": ...}``).
        """
        entries = []
        for entry in replace or []:
            if not isinstance(entry, dict):
                continue
            if "pattern" in entry:
                entries.append({
                    "pattern": str(entry.get("pattern", "")),
                    "replacement": str(entry.get("replacement", "") or ""),
                })
            else:
                for pattern, replacement in entry.items():
                    entries.append({
                        "pattern": str(pattern),
                        "replacement": "" if replacement is None else str(replacement),
                    })
        return entries

    def is_empty(self):
        return not any(self.logs.values()) and not any(self.tags.values()) and not self.replace

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, ToolFormat):
            return data
        data = data if isinstance(data, dict) else {}
        return cls(data.get("logs"), data.get("tags"), data.get("replace"))

    def to_dict(self):
        return {
            "logs": dict((level, list(markers)) for level, markers in self.logs.items()),
            "tags": dict((tag, list(markers)) for tag, markers in self.tags.items()),
            "replace": copy.deepcopy(self.replace),
        }

    def to_document(self, only_non_empty=False):
        """The "format" section as it is written in a tool.yml."""
        document = CommentedMap()
        for section_key, values in (("logs", self.logs), ("tags", self.tags)):
            section = CommentedMap()
            for name, markers in values.items():
                markers = _as_marker_list(markers)
                if markers or not only_non_empty:
                    section[str(name)] = CommentedSeq(markers)
            if len(section) > 0:
                document[section_key] = section
        if self.replace:
            replace_seq = CommentedSeq()
            for entry in self.replace:
                pattern = str(entry.get("pattern", "")).strip()
                if pattern == "":
                    continue
                item = CommentedMap()
                item[pattern] = str(entry.get("replacement", "") or "")
                replace_seq.append(item)
            if len(replace_seq) > 0:
                document["replace"] = replace_seq
        return document

    def __repr__(self):
        return "<ToolFormat logs={0} tags={1} replace={2}>".format(
            len(self.logs), len(self.tags), len(self.replace)
        )


######################################
# Tool settings
######################################

class ToolSettings(object):
    """
    The settings of a tool, as its "tool.yml" describes them.

    The file spreads the flows over three places (the default flow's commands
    sit at the top level, "default_flow" names it, and "flows" holds the rest);
    this object holds them as one list, the default flow first, and puts them
    back where they belong on save.
    """

    #: Keys this class owns; anything else in the file is kept in ``extra``.
    OWNED_KEYS = set(OVERRIDABLE_KEYS) | set(PLATFORMS) | set(["format", "flows", "default_flow"])

    def __init__(self, label="", description="", icon="", process_group=True,
                 report_path="", target_file="", default_metrics_file="",
                 flows=None, format=None, extra=None):
        self.label = str(label or "")
        self.description = str(description or "")
        self.icon = str(icon or "")
        self.process_group = bool(process_group)
        self.report_path = str(report_path or "")
        self.target_file = str(target_file or "")
        self.default_metrics_file = str(default_metrics_file or "")
        self.flows = [Flow.from_dict(flow) for flow in (flows or [])]
        if not self.flows:
            # A tool without a flow can run nothing: it always has at least the
            # default one, exactly like a tool.yml that declares none.
            import odatix.lib.eda_tools as eda_tools

            self.flows = [Flow(eda_tools.DEFAULT_FLOW_NAME, is_default=True)]
        self.format = ToolFormat.from_dict(format)
        self.extra = dict(extra or {})

    ######################################
    # Flows
    ######################################

    @property
    def default_flow(self):
        """The flow that runs when no other is asked for."""
        for flow in self.flows:
            if flow.is_default:
                return flow
        return self.flows[0] if self.flows else None

    def flow_names(self):
        return [flow.name for flow in self.flows]

    def flow(self, name):
        for flow in self.flows:
            if flow.name == name:
                return flow
        raise NotFoundError("No such flow: '{0}'.".format(name))

    def add_flow(self, name, label="", description="", icon="", metrics_file="", is_default=False):
        """Add a flow to the tool, and return it."""
        name = check_name(name, "flow")
        if name in self.flow_names():
            raise AlreadyExistsError("A flow named '{0}' already exists.".format(name))
        flow = Flow(name, label=label, description=description, icon=icon,
                    metrics_file=metrics_file, is_default=is_default)
        if is_default:
            for other in self.flows:
                other.is_default = False
        self.flows.append(flow)
        return flow

    def remove_flow(self, name):
        self.flows = [flow for flow in self.flows if flow.name != name]
        return self

    def set_default_flow(self, name):
        flow = self.flow(name)
        for other in self.flows:
            other.is_default = other is flow
        return flow

    ######################################
    # Conversion
    ######################################

    @classmethod
    def from_dict(cls, data):
        """
        Read a tool, either as its "tool.yml" spells it out (the flows spread
        over "default_flow", the platform sections and "flows") or as this class
        hands it back (:meth:`to_dict`, with the flows as one list). Both are
        accepted so that settings can be passed around without being pinned to
        the file layout.
        """
        if isinstance(data, ToolSettings):
            return data
        data = data if isinstance(data, dict) else {}

        settings = cls(
            label=data.get("label", ""),
            description=data.get("description", ""),
            icon=data.get("icon", ""),
            process_group=data.get("process_group", True),
            report_path=data.get("report_path", ""),
            target_file=data.get("target_file", ""),
            default_metrics_file=data.get("default_metrics_file", ""),
            format=data.get("format"),
            extra=dict((key, value) for key, value in data.items()
                       if key not in cls.OWNED_KEYS and key != "platforms"),
        )

        if isinstance(data.get("flows"), list):
            settings.flows = [Flow.from_dict(flow) for flow in data.get("flows")]
            if settings.flows and not any(flow.is_default for flow in settings.flows):
                settings.flows[0].is_default = True
        elif isinstance(data.get("platforms"), dict):
            # A tool described by its platform sections alone, without flows.
            import odatix.lib.eda_tools as eda_tools

            settings.flows = [Flow(
                eda_tools.DEFAULT_FLOW_NAME, is_default=True,
                platforms=dict(
                    (platform, dict(
                        (job, execution.to_dict())
                        for job, execution in _read_platform_section(
                            data["platforms"].get(platform, {})
                        ).items()
                    ))
                    for platform in PLATFORMS
                ),
            )]
        else:
            settings.flows = cls._read_flows(data)
        return settings

    @staticmethod
    def _read_flows(data):
        """
        Read the flows of a tool.yml as an ordered list, the default flow first.

        The default flow is the one holding the commands declared directly in
        the "unix"/"windows" sections; whatever it also declares under "flows"
        (its label, its description) is merged into it, so there is one entry per
        flow whether or not the file names it.
        """
        import odatix.lib.eda_tools as eda_tools

        default_name = str(data.get("default_flow", "") or "").strip() or eda_tools.DEFAULT_FLOW_NAME

        declared = data.get("flows")
        if not isinstance(declared, dict):
            declared = {}

        names = [default_name] + [str(name) for name in declared if str(name) != default_name]

        flows = []
        for name in names:
            spec = declared.get(name)
            spec = spec if isinstance(spec, dict) else {}
            is_default = name == default_name
            platforms = {}
            for platform in PLATFORMS:
                # The default flow declares its commands at the top level; what
                # it also declares under "flows" overrides them.
                section = spec.get(platform) if isinstance(spec.get(platform), dict) else {}
                if is_default:
                    base = data.get(platform) if isinstance(data.get(platform), dict) else {}
                    merged = dict(base)
                    merged.update(section)
                    section = merged
                platforms[platform] = _read_platform_section(section)
            flows.append(Flow(
                name=name,
                label=spec.get("label", ""),
                description=spec.get("description", ""),
                icon=spec.get("icon", ""),
                metrics_file=spec.get("metrics_file", ""),
                is_default=is_default,
                platforms=dict(
                    (platform, dict((job, execution.to_dict()) for job, execution in jobs.items()))
                    for platform, jobs in platforms.items()
                ),
            ))
        return flows

    def to_dict(self):
        """The settings as plain values, in the canonical shape used by the editors."""
        return {
            "label": self.label,
            "description": self.description,
            "icon": self.icon,
            "process_group": self.process_group,
            "report_path": self.report_path,
            "target_file": self.target_file,
            "default_metrics_file": self.default_metrics_file,
            "flows": [flow.to_dict() for flow in self.flows],
            "format": self.format.to_dict(),
        }

    ######################################
    # Writing
    ######################################

    def to_document(self, header=None):
        """
        Build the full "tool.yml" of a workspace tool.

        The commands of the default flow are written in the top-level
        "unix"/"windows" sections, which is where Odatix reads them; every flow,
        the default one included, gets an entry under "flows" holding its
        metadata and, for the others, what it runs.
        """
        document = CommentedMap()
        if header:
            document.yaml_set_start_comment(header)

        for key in ("label", "description", "icon"):
            value = getattr(self, key)
            if str(value).strip() != "":
                document[key] = str(value)

        document["process_group"] = bool(self.process_group)
        for key in ("report_path", "target_file", "default_metrics_file"):
            value = getattr(self, key)
            if str(value).strip() != "":
                document[key] = str(value)

        named_flows = [flow for flow in self.flows if flow.name != ""]
        if named_flows:
            default_flow = self.default_flow
            if default_flow is not None:
                document["default_flow"] = default_flow.name
                for platform in PLATFORMS:
                    section = _write_platform_section(default_flow.platforms.get(platform, {}))
                    if len(section) > 0:
                        document[platform] = section

            flows_map = CommentedMap()
            for flow in named_flows:
                entry = CommentedMap()
                for key in ("label", "description", "icon", "metrics_file"):
                    value = getattr(flow, key)
                    if str(value).strip() != "":
                        entry[key] = str(value)
                if flow is not default_flow:
                    for platform in PLATFORMS:
                        section = _write_platform_section(flow.platforms.get(platform, {}))
                        if len(section) > 0:
                            entry[platform] = section
                flows_map[flow.name] = entry
            if len(flows_map) > 0:
                document["flows"] = flows_map

        format_document = self.format.to_document(only_non_empty=True)
        if len(format_document) > 0:
            document["format"] = format_document

        for key, value in self.extra.items():
            document[key] = value

        return document

    def overlay_overrides(self, builtin):
        """
        What this workspace says about a built-in tool's settings: only the
        values that differ from the built-in definition, so a setting put back
        to what Odatix says drops out of the workspace file instead of being
        frozen into it.

        The flows are not part of it: the built-in ones belong to Odatix, and
        the added ones are written on their own.
        """
        builtin = ToolSettings.from_dict(builtin) if not isinstance(builtin, ToolSettings) else builtin
        current_values = self.to_dict()
        builtin_values = builtin.to_dict()

        overrides = {}
        for key in OVERRIDABLE_KEYS:
            if current_values.get(key) != builtin_values.get(key):
                overrides[key] = current_values.get(key)

        fmt = {}
        for section_key in ("logs", "tags"):
            current_section = getattr(self.format, section_key)
            builtin_section = getattr(builtin.format, section_key)
            # Built-in entries first, so the file reads in the order of the
            # tool.yml it overrides; a marker list the user cleared is kept as an
            # empty list, which is how the overlay says a built-in one is gone.
            keys = list(builtin_section) + [key for key in current_section if key not in builtin_section]
            section = dict(
                (key, list(current_section.get(key) or []))
                for key in keys
                if list(current_section.get(key) or []) != list(builtin_section.get(key) or [])
            )
            if section:
                fmt[section_key] = section

        if self.format.replace != builtin.format.replace:
            fmt["replace"] = copy.deepcopy(self.format.replace)

        if fmt:
            overrides["format"] = fmt
        return overrides

    def __repr__(self):
        return "<ToolSettings {0!r} flows={1}>".format(self.label, self.flow_names())


def overlay_document(name, overrides, flows, header=None):
    """
    Build the workspace overlay of a built-in tool: the flows it adds, and the
    settings it overrides. Nothing of the built-in flows is written: their
    commands stay owned by Odatix.

    Values are written as given, empty lists included: an empty marker list is
    how an overlay says a built-in one is cleared.
    """
    document = CommentedMap()
    if header:
        document.yaml_set_start_comment(header)

    overrides = overrides if isinstance(overrides, dict) else {}
    for key in OVERRIDABLE_KEYS:
        if key not in overrides:
            continue
        value = overrides.get(key)
        document[key] = bool(value) if key == "process_group" else ("" if value is None else str(value))

    fmt = overrides.get("format") if isinstance(overrides.get("format"), dict) else {}
    format_document = CommentedMap()
    for section_key in ("logs", "tags"):
        section = fmt.get(section_key)
        if isinstance(section, dict) and len(section) > 0:
            section_map = CommentedMap()
            for entry_key, markers in section.items():
                section_map[str(entry_key)] = CommentedSeq(_as_marker_list(markers))
            format_document[section_key] = section_map
    if "replace" in fmt:
        replace_seq = CommentedSeq()
        for entry in ToolFormat._read_replace(fmt.get("replace")):
            pattern = str(entry.get("pattern", "")).strip()
            if pattern == "":
                continue
            item = CommentedMap()
            item[pattern] = str(entry.get("replacement", "") or "")
            replace_seq.append(item)
        format_document["replace"] = replace_seq
    if len(format_document) > 0:
        document["format"] = format_document

    named_flows = [Flow.from_dict(flow) for flow in (flows or [])]
    named_flows = [flow for flow in named_flows if flow.name != "" and not flow.declares_nothing()]
    if named_flows:
        flows_map = CommentedMap()
        for flow in named_flows:
            entry = CommentedMap()
            for key in ("label", "description", "icon", "metrics_file"):
                value = getattr(flow, key)
                if str(value).strip() != "":
                    entry[key] = str(value)
            for platform in PLATFORMS:
                section = _write_platform_section(flow.platforms.get(platform, {}))
                if len(section) > 0:
                    entry[platform] = section
            flows_map[flow.name] = entry
        document["flows"] = flows_map

    return document


######################################
# Tool metrics
######################################

class ToolMetrics(object):
    """
    The metrics of a tool ("metrics.yml"), one mapping per job type plus the
    common ones.

    For a built-in tool, the file holds only what the workspace says about them:
    the metrics it adds, the built-in ones it overrides, and, as entries mapped
    to nothing, the built-in ones it removes.
    """

    def __init__(self, path):
        self.path = path
        self._sections = None

    @property
    def exists(self):
        return os.path.isfile(self.path)

    def _load(self):
        if self._sections is not None:
            return self._sections
        data = read_yaml(self.path, default={})
        sections = {}
        for section_key, _label in METRIC_SECTIONS:
            section = data.get(section_key, {}) if isinstance(data, dict) else {}
            sections[section_key] = section if isinstance(section, dict) else {}
        self._sections = sections
        return self._sections

    @property
    def sections(self):
        """The metric definitions, by section key."""
        return self._load()

    @sections.setter
    def sections(self, value):
        self._sections = dict(
            (section_key, dict(value.get(section_key) or {}) if isinstance(value, dict) else {})
            for section_key, _label in METRIC_SECTIONS
        )

    def reload(self):
        self._sections = None
        return self

    def section(self, section_key):
        if section_key not in self.sections:
            raise NotFoundError("No such metric section: '{0}'.".format(section_key))
        return self.sections[section_key]

    def set(self, name, definition, section_key="metrics"):
        """Add or replace one metric of a section."""
        self.section(section_key)[str(name)] = definition
        return self

    def remove(self, name, section_key="metrics"):
        self.section(section_key).pop(name, None)
        return self

    def to_dict(self):
        return dict((key, dict(value)) for key, value in self.sections.items())

    def save(self):
        """Write the file back, keeping its comments and the keys it does not own."""
        sections = self._load()
        document = read_document(self.path)
        for section_key, _label in METRIC_SECTIONS:
            definitions = sections.get(section_key, {})
            if isinstance(definitions, dict) and len(definitions) > 0:
                document[section_key] = definitions
            else:
                document.pop(section_key, None)
        write_document(self.path, document)
        return self

    def __repr__(self):
        return "<ToolMetrics {0!r}>".format(self.path)


######################################
# Tools
######################################

class Tool(Entry):
    """
    One EDA tool usable by a workspace.

    A tool is either defined by the workspace, or shipped with Odatix. For a
    built-in one, what the workspace holds is an overlay: :attr:`settings` is
    what the overlay says, :attr:`builtin_settings` what Odatix ships, and
    :attr:`effective_settings` what actually runs.
    """

    kind = "tool"

    def __init__(self, workspace, root, name):
        super(Tool, self).__init__(workspace, root, name)
        self._settings = None

    ######################################
    # Location
    ######################################

    @property
    def settings_path(self):
        return os.path.join(self.path, TOOL_SETTINGS_FILENAME)

    @property
    def metrics_path(self):
        return os.path.join(self.path, TOOL_METRICS_FILENAME)

    @property
    def exists(self):
        """A tool exists once it has a tool.yml, an empty directory is not one."""
        return os.path.isfile(self.settings_path)

    @property
    def builtin_dir(self):
        """Directory of the built-in tool of that name, or None when there is none."""
        from odatix.lib.settings import OdatixSettings

        candidate = os.path.join(OdatixSettings.odatix_eda_tools_path, self.name)
        return candidate if os.path.isfile(os.path.join(candidate, TOOL_SETTINGS_FILENAME)) else None

    @property
    def is_builtin(self):
        """
        True when Odatix ships a tool of this name. Whatever the workspace holds
        for it is then an overlay, never a tool of its own.
        """
        return self.builtin_dir is not None

    @property
    def has_overlay(self):
        """True when the workspace holds something for this built-in tool."""
        return self.is_builtin and os.path.isfile(self.settings_path)

    ######################################
    # Settings
    ######################################

    @property
    def document(self):
        """The workspace tool.yml of this tool, as plain values."""
        data = read_yaml(self.settings_path, default={})
        return data if isinstance(data, dict) else {}

    @property
    def builtin_document(self):
        """The tool.yml Odatix ships for this tool, as plain values."""
        builtin_dir = self.builtin_dir
        if builtin_dir is None:
            return {}
        data = read_yaml(os.path.join(builtin_dir, TOOL_SETTINGS_FILENAME), default={})
        return data if isinstance(data, dict) else {}

    @property
    def effective_document(self):
        """
        What actually runs, as plain values: the built-in definition with the
        workspace overlay applied on top, the way Odatix resolves it at run
        time. What an overlay says about the built-in flows is dropped, so this
        is what runs, not what was asked for.
        """
        import odatix.lib.eda_tools as eda_tools

        if not self.is_builtin:
            return self.document
        builtin = self.builtin_document
        overlay = eda_tools.strip_builtin_overrides(
            builtin, self.document, tool=self.name, source=self.settings_path,
        )
        return eda_tools._deep_merge(builtin, overlay)

    @property
    def settings(self):
        """
        The settings of this tool as they apply: its own for a workspace tool,
        the built-in definition with the workspace overlay on top for a built-in
        one.

        These are the settings to edit. Saving a built-in tool writes only what
        they add to (or differ from) the built-in definition, so putting a
        setting back to what Odatix says drops it from the workspace file
        instead of freezing it there. What the overlay holds on its own is
        :attr:`document`.
        """
        if self._settings is None:
            self._settings = ToolSettings.from_dict(
                self.effective_document if self.is_builtin else self.document
            )
        return self._settings

    @settings.setter
    def settings(self, value):
        self._settings = ToolSettings.from_dict(value)

    def reload(self):
        self._settings = None
        return self

    @property
    def builtin_settings(self):
        """The tool.yml Odatix ships for this tool, or empty settings."""
        return ToolSettings.from_dict(self.builtin_document)

    @property
    def effective_settings(self):
        """What actually runs (see :attr:`effective_document`)."""
        return ToolSettings.from_dict(self.effective_document)

    ######################################
    # Metrics and targets
    ######################################

    @property
    def metrics(self):
        """The metrics this tool reads from its reports."""
        return ToolMetrics(self.metrics_path)

    @property
    def targets(self):
        """The synthesis targets this tool runs on."""
        from odatix.workspace.targets import TargetFile

        return TargetFile(self.workspace, self.name)

    ######################################
    # Writing
    ######################################

    def save(self, as_overlay=None):
        """
        Write this tool's file.

        A workspace tool is written whole. A built-in one gets an overlay
        holding only the flows added to it and the settings that differ from the
        built-in definition; an overlay left with nothing to say is removed
        rather than kept empty.

        Args:
            as_overlay (bool): force one of the two, instead of choosing by
                whether Odatix ships a tool of this name.
        """
        from odatix.workspace.yaml_io import file_header

        if as_overlay is None:
            as_overlay = self.is_builtin

        if not as_overlay:
            os.makedirs(self.path, exist_ok=True)
            document = self.settings.to_document(
                header=file_header("Settings for " + self.name)
            )
            write_document(self.settings_path, document)
            return self

        builtin = self.builtin_settings
        builtin_flow_names = builtin.flow_names()
        return self.save_overlay(
            self.settings.overlay_overrides(builtin),
            [
                flow for flow in self.settings.flows
                if flow.name not in builtin_flow_names and not flow.declares_nothing()
            ],
        )

    def save_overlay(self, overrides, flows):
        """
        Write the workspace overlay of a built-in tool from what it overrides
        and the flows it adds, without going through :attr:`settings`.
        """
        document = overlay_document(
            self.name, overrides, flows,
            header=(
                "##############################################\n"
                "# Your changes to the built-in {0} tool\n"
                "##############################################\n"
                "\n"
                "# It is merged over the {0} tool shipped with Odatix: it holds the flows you\n"
                "# added to it and the settings you overrode, everything else (the commands of\n"
                "# {0}'s own flows) still comes from the built-in definition. You can still\n"
                "# modify manually this file as needed.\n"
            ).format(self.name),
        )

        if len(document) == 0:
            # Nothing left of its own: drop the overlay rather than leave an
            # empty one behind, so the tool goes back to being a plain built-in.
            if os.path.isfile(self.settings_path):
                os.remove(self.settings_path)
            if os.path.isdir(self.path) and not os.listdir(self.path):
                os.rmdir(self.path)
            return self

        os.makedirs(self.path, exist_ok=True)
        write_document(self.settings_path, document)
        return self

    def update(self, values=None, **kwargs):
        """Change some settings and write them back, in one call."""
        for source in (values, kwargs):
            for key, value in (source or {}).items():
                setattr(self.settings, key, value)
        return self.save()

    ######################################
    # Lifecycle
    ######################################

    def delete(self):
        """Delete the workspace directory of this tool (a built-in tool stays available)."""
        import shutil

        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
        return self


class ToolCollection(Collection):
    """
    The EDA tools of a workspace.

    Only the tools the workspace defines are listed: what it holds for a
    built-in tool is an overlay on it, not a tool of its own, so it is listed
    with the built-in ones (:meth:`builtin_names`).
    """

    entry_class = Tool

    def names(self):
        """Names of the tools defined by this workspace."""
        path = self.path
        if not path or not os.path.isdir(path):
            return []
        return natsorted([
            entry for entry in os.listdir(path)
            if not entry.startswith("_") and not entry.startswith(".")
            and os.path.isfile(os.path.join(path, entry, TOOL_SETTINGS_FILENAME))
            and not self._make(entry).is_builtin
        ])

    def builtin_names(self):
        """Names of the tools shipped with Odatix."""
        from odatix.lib.settings import OdatixSettings

        root = OdatixSettings.odatix_eda_tools_path
        if not os.path.isdir(root):
            return []
        return natsorted([
            entry for entry in os.listdir(root)
            if not entry.startswith("_") and not entry.startswith(".")
            and os.path.isfile(os.path.join(root, entry, TOOL_SETTINGS_FILENAME))
        ])

    def all_names(self):
        """Every tool usable by this workspace, built-in ones included."""
        names = self.builtin_names()
        return names + [name for name in self.names() if name not in names]

    def __iter__(self):
        for name in self.all_names():
            yield self._make(name)

    def exists(self, name):
        """True when the workspace defines this tool (built-in tools excluded)."""
        return bool(name) and os.path.isfile(os.path.join(self.path, str(name), TOOL_SETTINGS_FILENAME))

    def __getitem__(self, name):
        tool = self._make(name)
        if not tool.exists and not tool.is_builtin:
            raise NotFoundError("No such tool: '{0}'.".format(name))
        return tool

    def get(self, name, default=None):
        tool = self._make(name)
        return tool if (tool.exists or tool.is_builtin) else default

    def create(self, name, **settings):
        """
        Create a workspace tool with a minimal tool.yml, and return it.
        """
        name = check_name(name, self.kind)
        tool = self._make(name)
        if tool.exists:
            raise AlreadyExistsError("A tool named '{0}' already exists.".format(name))
        if tool.is_builtin:
            raise AlreadyExistsError("'{0}' is the name of a tool shipped with Odatix.".format(name))
        tool.settings = ToolSettings(
            label=settings.pop("label", name),
            process_group=settings.pop("process_group", True),
            default_metrics_file=settings.pop("default_metrics_file", "$tool_path/metrics.yml"),
        )
        for key, value in settings.items():
            setattr(tool.settings, key, value)
        tool.save()
        return tool

    def import_builtin(self, name, new_name):
        """
        Copy a built-in tool into the workspace under another name, so it can be
        edited as a tool of its own.
        """
        import odatix.lib.eda_tools as eda_tools

        new_name = check_name(new_name, self.kind)
        source_dir = eda_tools.get_tool_dir(name)
        if not source_dir or not os.path.isdir(source_dir):
            raise NotFoundError("No such tool: '{0}'.".format(name))
        target = self._make(new_name)
        if os.path.exists(target.path):
            raise AlreadyExistsError("A tool named '{0}' already exists.".format(new_name))
        os.makedirs(self.path, exist_ok=True)
        copytree(source_dir, target.path)
        return target
