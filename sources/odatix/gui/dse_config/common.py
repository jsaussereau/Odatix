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

"""What the two exploration pages share: where things are read and written, and
the small conversions between what a widget holds and what a settings file says."""

import os
from urllib.parse import quote

import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
from odatix.dse.campaigns import EXTENSIONS, available_campaigns, campaign_path, load_campaign
from odatix.dse.settings import CampaignSettings, DseSettings
from odatix.workspace.settings import load_settings, save_settings

#: The campaign list, and the editor of one campaign.
page_path = "/dse"
editor_path = "/dse_campaign"

#: What evaluating one design may run.
RUN_OPTIONS = [
    {"label": "Fmax synthesis", "value": "fmax_synthesis"},
    {"label": "Fixed-frequency synthesis", "value": "custom_freq_synthesis"},
    {"label": "Workflow", "value": "workflow"},
]

#: How the designs to evaluate are chosen.
STRATEGY_OPTIONS = [
    {"label": "Genetic", "value": "genetic"},
    {"label": "Bayesian", "value": "bayesian"},
    {"label": "Random", "value": "random"},
    {"label": "Exhaustive", "value": "exhaustive"},
]

#: Whether a decision waits for a whole batch, or fills slots as they free up.
MODE_OPTIONS = [
    {"label": "Batch", "value": "batch"},
    {"label": "Continuous (async)", "value": "async"},
]

GOAL_OPTIONS = [
    {"label": "Maximize", "value": "max"},
    {"label": "Minimize", "value": "min"},
]

#: What the exploration settings form holds, and what it falls back to. Shared
#: by the widgets and the saved baseline, so a fresh load never claims there are
#: unsaved changes.
DSE_SETTINGS_DEFAULTS = {
    "overwrite": False,
    "nb_jobs": 8,
    "log_size_limit": 300,
    "exit_when_done": False,
}


######################################
# Reading and writing
######################################

def dse_settings(workspace):
    """How the exploration is run, and which campaigns it runs."""
    return load_settings(DseSettings, workspace.paths.dse_settings_file)


def save_dse_settings(workspace, settings):
    """Write it back, keeping the comments the file already holds."""
    path = workspace.paths.dse_settings_file
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return save_settings(settings, path)


def campaign_names(workspace):
    """Every campaign the workspace holds, in alphabetical order."""
    return available_campaigns(workspace)


def read_campaign(workspace, name):
    """One campaign, or fresh defaults when it does not exist yet."""
    try:
        return load_campaign(workspace, name)
    except Exception:
        settings = CampaignSettings()
        object.__setattr__(settings, "name", name)
        return settings


def save_campaign(workspace, name, settings):
    """Write one campaign to its own file of the campaign directory."""
    directory = workspace.paths.dse_campaign_path
    os.makedirs(directory, exist_ok=True)
    # Written like the commented campaign "odatix init" writes (DS-09).
    from odatix.lib.settings import OdatixSettings
    template = os.path.join(
        OdatixSettings.odatix_init_path, "odatix_userconfig", "dse_campaigns", "campaign_template.yml",
    )
    return save_settings(settings, campaign_path(workspace, name),
                         template=template if os.path.isfile(template) else None)


def delete_campaign(workspace, name):
    """Remove a campaign file, whichever extension it uses."""
    directory = workspace.paths.dse_campaign_path
    for extension in EXTENSIONS:
        path = os.path.join(directory, "{0}{1}".format(name, extension))
        if os.path.isfile(path):
            os.remove(path)


def campaign_name_error(name, existing, original_name=None):
    """
    Why a campaign cannot be saved as `name`, or None when it can.

    The name is the one of a file of the campaign directory: it must be a file
    name, and one the campaign list shows -- a name starting with a dot is a
    hidden file, which takes "." and ".." with it.
    """
    if not name:
        return "A campaign needs a name."
    for character in hard_settings.invalid_filename_characters:
        if character in name:
            shown = "' ' (space)" if character == " " else "'{0}'".format(character)
            return "A campaign name is a file name: it cannot contain {0}.".format(shown)
    if name.startswith("."):
        return "A campaign name cannot start with a dot."
    if name != original_name and name in existing:
        return 'A campaign called "{0}" already exists.'.format(name)
    return None


def campaign_link(editor_path, name):
    """The editor of one campaign, whatever its name holds."""
    return "{0}?campaign={1}".format(editor_path, quote(name, safe=""))


def campaign_exists(workspace, name):
    return name in available_campaigns(workspace)


def unique_campaign_name(workspace, base):
    """A name no campaign of the workspace uses yet."""
    existing = set(available_campaigns(workspace))
    if base not in existing:
        return base
    for index in range(1, 1000):
        candidate = "{0}_{1}".format(base, index)
        if candidate not in existing:
            return candidate
    return base


######################################
# What the workspace offers
######################################

def architecture_options(workspace, run_mode=""):
    """
    The designs an exploration may search: the workflows of the workspace when
    what evaluates one is an "odatix workflow" run, its architectures
    otherwise. The two are named in the same field because they are the same
    thing to a search (see :meth:`odatix.dse.settings.CampaignSettings.designs`).
    """
    try:
        collection = workspace.workflows if run_mode == "workflow" else workspace.architectures
        return [{"label": name, "value": name} for name in collection.names()]
    except Exception:
        return []


def simulation_options(workspace):
    """The simulations an evaluation may run every design through."""
    try:
        return [{"label": name, "value": name} for name in workspace.simulations.names()]
    except Exception:
        return []


def tool_options():
    """The eda tools the evaluations may run with."""
    options = []
    for tool in eda_tools.get_supported_tools():
        try:
            label = eda_tools.get_tool_label(tool)
        except Exception:
            label = tool
        options.append({"label": label or tool, "value": tool})
    return options


def flow_options(tools, run_mode="fmax_synthesis"):
    """The flows of the selected tools, named "<flow>" or "<tool>: <flow>"."""
    job_type = run_mode if run_mode in ("fmax_synthesis", "custom_freq_synthesis") else None
    options = []
    seen = set()
    for tool in (tools or []):
        try:
            names = eda_tools.get_flow_names(tool, job_type=job_type)
        except Exception:
            names = []
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            options.append({"label": name, "value": name})
    return options


def target_options(workspace, tools):
    """The targets the selected tools enable."""
    options = []
    seen = set()
    for tool in (tools or []):
        try:
            names = workspace.targets[tool].enabled_names()
        except Exception:
            names = []
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            options.append({"label": name, "value": name})
    return options


def metric_names(workspace):
    """
    Every metric an objective or a constraint may name: what the eda tools read
    from their reports, what the simulations produce, and what the workspace
    derives from them.

    They are suggestions and nothing more -- a metric is a name in a results
    file, and the page never refuses one it does not know.
    """
    from odatix.dse.metric_names import all_metric_names

    names = set(["frequency", "Fmax"])
    try:
        names.update(all_metric_names(workspace))
    except Exception:
        pass
    return sorted(names, key=lambda name: name.lower())


def campaign_metric_names(workspace, campaign):
    """
    The metrics a campaign can name: what what it runs measures, exactly as
    "odatix dse -C" checks the objectives against (see
    :func:`odatix.dse.metric_names.known_metric_names`).

    Returns:
        set: the names, or None when they cannot be known -- no tool named
        yet, a workflow that does not declare its metrics.
    """
    from odatix.dse.metric_names import known_metric_names

    try:
        toolchains = None if campaign.runs_workflow() else campaign.toolchains(workspace)
    except Exception:
        toolchains = None
    try:
        return known_metric_names(workspace, campaign, toolchains)
    except Exception:
        return None


def unknown_metric_warning(workspace, campaign):
    """
    What is wrong with the metrics a campaign names, said the way the check
    of "odatix dse" says it, or None when nothing is -- or when what the
    campaign runs does not say what it measures.
    """
    from odatix.dse.metric_names import unknown_metrics
    import difflib

    names = campaign_metric_names(workspace, campaign)
    if not names:
        return None
    try:
        metrics = campaign.objective_list().measured_metrics
    except Exception:
        return None
    unknown = unknown_metrics(metrics, names)
    if not unknown:
        return None
    hints = []
    for metric in unknown:
        close = difflib.get_close_matches(metric, sorted(names), n=1, cutoff=0.6)
        hints.append('"{0}"{1}'.format(metric, ' (did you mean "{0}"?)'.format(close[0]) if close else ""))
    return (
        "{0} {1} not measured by what this campaign runs: the exploration will refuse to "
        "start until {2} fixed. The metrics it can name are suggested in the fields.".format(
            ", ".join(hints), "is" if len(unknown) == 1 else "are",
            "it is" if len(unknown) == 1 else "they are",
        )
    )


######################################
# Widgets and settings
######################################

def checked(value):
    """Whether a checklist-switch is on."""
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    return bool(value)


def switch_value(enabled):
    return [True] if enabled else []


def to_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_names(value):
    """A setting that is either one name or several, as a list of names."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [str(name).strip() for name in value if str(name).strip()]


def from_names(names):
    """The other way round: one name stays a name, several become a list."""
    names = [str(name).strip() for name in (names or []) if str(name).strip()]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return names


def int_list(text):
    """The comma separated numbers of a text field, as a list."""
    values = []
    for chunk in str(text or "").replace(";", ",").split(","):
        value = to_int(chunk.strip())
        if value is not None:
            values.append(value)
    return values


def int_list_text(values):
    return ", ".join(str(value) for value in (values or []))


######################################
# What a campaign amounts to
######################################

def objective_entries(campaign):
    """The objectives of a campaign as (metric, goal) pairs, however written."""
    entries = []
    for entry in (campaign.objectives or []):
        if isinstance(entry, str):
            entries.append((entry, "min"))
        elif isinstance(entry, dict):
            if len(entry) == 1 and "metric" not in entry:
                metric, goal = list(entry.items())[0]
                entries.append((str(metric), str(goal or "min")))
            else:
                entries.append((str(entry.get("metric", "")), str(entry.get("goal", "min") or "min")))
    return entries


def constraint_entries(campaign):
    """The constraints of a campaign as (metric, min, max) triples."""
    entries = []
    for entry in (campaign.constraints or []):
        if not isinstance(entry, dict):
            continue
        metric = str(entry.get("metric", ""))
        minimum = _first(entry, ("min", "minimum", "at_least"))
        maximum = _first(entry, ("max", "maximum", "at_most"))
        entries.append((metric, minimum, maximum))
    return entries


def _first(entry, keys):
    for key in keys:
        if key in entry and entry[key] is not None:
            return entry[key]
    return None


def architecture_entries(campaign):
    """
    The architectures of a campaign, split into what the entry names and what it
    says about the domains ("AsteRISC + MEM/1024I" -> ("AsteRISC", "+ MEM/1024I")).
    """
    entries = []
    for entry in campaign.architecture_entries():
        text = str(entry).strip()
        head, sep, rest = text.partition("+")
        name = head.strip()
        selection = (sep + rest).strip() if sep else ""
        if "/" in name:
            name, _, configuration = name.partition("/")
            name = name.strip()
            configuration = configuration.strip()
            if configuration and configuration != "*":
                selection = ("/{0} {1}".format(configuration, selection)).strip()
        entries.append((name, selection))
    return entries


def architecture_entry_text(name, selection):
    """The two halves of an architecture row, back as one entry."""
    name = str(name or "").strip()
    selection = str(selection or "").strip()
    if not name:
        return ""
    if not selection:
        return name
    if selection.startswith("/"):
        return "{0}{1}".format(name, selection)
    return "{0} {1}".format(name, selection)


#: Archives already read, by path: (modification time, what was read).
_ARCHIVE_CACHE = {}


def _read_archive(path):
    """The few numbers of an archive the cards show, read once per change."""
    import odatix.lib.yaml_loader as yaml_loader

    try:
        modified = os.path.getmtime(path)
    except OSError:
        return None
    cached = _ARCHIVE_CACHE.get(path)
    if cached is not None and cached[0] == modified:
        return cached[1]
    try:
        with open(path, "r") as f:
            content = yaml_loader.safe_load(f) or {}
    except Exception:
        return None
    if not isinstance(content, dict):
        return None
    numbers = {
        "evaluated": to_int(content.get("evaluated"), 0) or 0,
        "reused": to_int(content.get("reused"), 0) or 0,
        "measured": to_int(content.get("measured"), 0) or 0,
        "front": len(content.get("front") or []),
        "space": to_int(content.get("designs_in_space")),
        "modified": modified,
    }
    _ARCHIVE_CACHE[path] = (modified, numbers)
    return numbers


def campaign_progress(workspace, name, campaign=None):
    """
    Where a campaign is: what its archives say it already evaluated, how many
    designs are on its front, and when it last ran.

    A campaign naming several architectures has one archive per architecture,
    named "<campaign>_<what the entry selects>": they are added up.

    Returns:
        dict: ``evaluated``, ``reused``, ``measured``, ``front``, ``space``
        (None when not known), ``modified`` (a timestamp, or None) and
        ``archives`` (how many were read) -- all zero when it never ran.
    """
    directory = os.path.join(workspace.paths.result_path, "dse")
    paths = [os.path.join(directory, "{0}.yml".format(name))]
    several = campaign is not None and len(campaign.architecture_entries()) > 1
    if several and os.path.isdir(directory):
        prefix = "{0}_".format(name)
        paths = [
            os.path.join(directory, entry) for entry in sorted(os.listdir(directory))
            if entry.startswith(prefix) and entry.endswith(".yml")
        ]
    total = {"evaluated": 0, "reused": 0, "measured": 0, "front": 0, "space": None,
             "modified": None, "archives": 0}
    for path in paths:
        numbers = _read_archive(path)
        if numbers is None:
            continue
        total["archives"] += 1
        for key in ("evaluated", "reused", "measured", "front"):
            total[key] += numbers[key]
        if numbers["space"] is not None and not several:
            total["space"] = numbers["space"]
        total["modified"] = max(total["modified"] or 0, numbers["modified"])
    return total


def designs_left(workspace, name, campaign):
    """
    How many designs the next run of a campaign evaluates at most: its budget
    -- never more than its space, when an archive says how large that is --
    less what it already evaluated.
    """
    badges = campaign_badges(campaign)
    progress = campaign_progress(workspace, name, campaign)
    budget = badges["budget"] * max(len(badges["architectures"]), 1)
    if progress["space"] is not None:
        budget = min(budget, progress["space"])
    return max(0, budget - progress["evaluated"])


def campaign_badges(campaign):
    """The few numbers that say what a campaign is about, for its card."""
    architectures = campaign.architecture_names()
    objectives = objective_entries(campaign)
    return {
        "run": campaign.run,
        "strategy": campaign.search.strategy,
        "budget": to_int(campaign.search.budget, 0) or 0,
        "batch": to_int(campaign.search.batch, 0) or 0,
        "architectures": architectures,
        "objectives": objectives,
        "constraints": constraint_entries(campaign),
        "tools": to_names(campaign.tool),
    }
