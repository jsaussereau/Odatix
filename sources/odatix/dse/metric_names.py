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

"""
The metrics a campaign can name, known before anything runs.

A metric an objective or a constraint names is a name in a results file, and a
name nothing produces is only found out once a batch is back: hours of
synthesis later, with every design reported as unmeasured. Yet the names are
known in advance, from the files that make them -- the metrics file of the eda
tool (or the "_metrics.yml" of the workflow), the simulations the campaign runs,
and the derived metrics of the workspace -- so a misspelled one is caught when
the exploration is checked, before it is started.

What cannot be known in advance is not guessed at: when what runs a design does
not declare its metrics, nothing is checked.
"""

import difflib

from odatix.lib.results_schema import PARAM_DOMAINS_KEY

__all__ = ["known_metric_names", "all_metric_names", "unknown_metrics", "describe_unknown"]

#: Dimensions a record carries as numbers, which a campaign may name like any
#: metric (see :meth:`odatix.dse.evaluation.Evaluator.metrics_of`), by run.
#: A fixed-frequency synthesis records the frequency it ran at; an fmax
#: synthesis has none to record, since the frequency is what it measures (its
#: "Fmax" metric).
RUN_DIMENSIONS = {
    "custom_freq_synthesis": ("frequency",),
    "pnr": ("frequency",),
}

#: What a campaign most likely means by a name nothing produces for its run.
HINTS = {
    ("fmax_synthesis", "frequency"): "Fmax",
    ("fmax_synthesis", "fmax"): "Fmax",
}

#: The section of a tool's metrics file each run reads, on top of "metrics".
RUN_SECTIONS = {
    "fmax_synthesis": "fmax_synthesis_metrics",
    "custom_freq_synthesis": "custom_freq_synthesis_metrics",
    "pnr": "pnr_metrics",
}


def known_metric_names(workspace, settings, toolchains=None):
    """
    Every metric a design of this campaign may be measured with.

    Args:
        workspace (Workspace): the workspace being explored.
        settings (CampaignSettings): the campaign.
        toolchains (list): what runs the designs, when already resolved (see
            :meth:`~odatix.dse.settings.CampaignSettings.toolchains`).

    Returns:
        set: the names, or None when what runs a design does not say what it
        measures -- nothing is then checked.
    """
    names = set()
    if settings.runs_workflow():
        declared = _workflow_metrics(workspace, settings)
    else:
        declared = _tool_metrics(workspace, settings, toolchains)
        names.update(RUN_DIMENSIONS.get(str(settings.run).strip(), ()))
    if declared is None:
        return None
    names.update(declared)
    # Not a metric: where a metrics file reads the parameter domains from.
    names.discard(PARAM_DOMAINS_KEY)

    try:
        names.update(str(name) for name in (workspace.derived_metrics.metrics or {}))
    except Exception:
        pass
    for simulation in settings.simulation_names():
        try:
            metrics = workspace.simulations[simulation].metrics
            names.update(str(name) for name in (metrics.metrics or {}))
        except Exception:
            continue
    return names


def all_metric_names(workspace):
    """
    Every metric name the workspace knows of, whatever runs it: the metrics of
    each tool (every section), of each workflow and of each simulation, and the
    derived metrics. What a campaign editor suggests; nothing is checked here.
    """
    from odatix.lib import metrics as metrics_lib

    names = set()
    for tool in workspace.tools.all_names():
        try:
            data = _quietly(_load_metrics, metrics_lib, tool, None) or {}
        except Exception:
            continue
        for key in metrics_lib.METRIC_SECTION_KEYS:
            definitions = data.get(key)
            if isinstance(definitions, dict):
                names.update(str(name) for name, definition in definitions.items() if definition is not None)
    for collection in (workspace.workflows, workspace.simulations):
        try:
            entries = [collection[name] for name in collection.names()]
        except Exception:
            continue
        for entry in entries:
            try:
                names.update(str(name) for name in (entry.metrics.metrics or {}))
            except Exception:
                continue
    try:
        names.update(str(name) for name in (workspace.derived_metrics.metrics or {}))
    except Exception:
        pass
    names.discard(PARAM_DOMAINS_KEY)
    return names


def _workflow_metrics(workspace, settings):
    """What the workflows of the campaign read out of their runs."""
    from odatix.workspace.errors import NotFoundError

    names = set()
    for entry in settings.architecture_names():
        try:
            workflow = workspace.workflows[entry]
        except (NotFoundError, KeyError):
            # Said by the check of the campaign itself, more clearly.
            return None
        metrics = workflow.metrics
        if not metrics.exists:
            return None
        names.update(str(name) for name in (metrics.metrics or {}))
        names.update(str(name) for name in (metrics.metadata or {}))
    return names


def _tool_metrics(workspace, settings, toolchains=None):
    """What the eda tools of the campaign read from their reports, for this run."""
    from odatix.lib import metrics as metrics_lib

    chains = [(chain.tool, chain.flow) for chain in (toolchains or [])]
    if not chains:
        tool = (settings.tool_names() or [""])[0] or getattr(workspace, "default_tool", "")
        if not tool:
            return None
        chains = [(tool, (settings.flow_names() or [""])[0])]

    section = RUN_SECTIONS.get(str(settings.run).strip())
    names = set()
    for tool, flow in chains:
        try:
            data = _quietly(_load_metrics, metrics_lib, tool, flow or None)
        except Exception:
            return None
        if not data:
            # A tool that does not declare what it measures (or one that
            # cannot be read): there is nothing to check the names against.
            return None
        for key in ([section] if section else []) + ["metrics"]:
            definitions = data.get(key)
            if isinstance(definitions, dict):
                names.update(str(name) for name, definition in definitions.items() if definition is not None)
    return names


def _load_metrics(metrics_lib, tool, flow):
    """
    The metrics of a tool run with a flow, every file defining them merged --
    or None when it declares none. Unlike the export, which needs them, saying
    nothing about a tool that declares none is the right answer here.
    """
    files = metrics_lib.metrics_files(tool, flow=flow, missing_ok=True)
    if not files:
        return None
    data = {}
    for path in files:
        content = metrics_lib._read_yaml(path)
        if content is None:
            return None
        data = metrics_lib.merge_metrics_data(data, content)
    return data


def _quietly(function, *args):
    """Call `function`, keeping what it prints out of the exploration's log."""
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args)


def unknown_metrics(metrics, names):
    """The metrics of `metrics` that are not in `names`, in order."""
    if names is None:
        return []
    return [metric for metric in metrics if metric not in names]


def describe_unknown(unknown, names, source, run=""):
    """
    Why the campaign cannot run as written: the names nothing produces, a
    likely fix for each, and every name that would do.
    """
    hints = []
    for metric in unknown:
        hint = HINTS.get((str(run).strip(), metric))
        if hint not in names:
            close = difflib.get_close_matches(metric, sorted(names), n=1, cutoff=0.6)
            hint = close[0] if close else None
        hints.append('"{0}"{1}'.format(metric, ' (did you mean "{0}"?)'.format(hint) if hint else ""))
    return (
        "The campaign names metric(s) that nothing it runs measures: {0}. "
        "Fix \"objectives\" or \"constraints\" in \"{1}\". "
        "The metrics it can name are: {2}.".format(
            ", ".join(hints), source, ", ".join(sorted(names, key=lambda name: name.lower())),
        )
    )
