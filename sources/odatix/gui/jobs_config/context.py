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

"""Everything that differs between job types, resolved from the ?type=... url parameter."""

import odatix.components.workspace as workspace
from odatix.gui.utils import get_key_from_url
from odatix.lib.settings import OdatixSettings

from odatix.gui.jobs_config.common import _get_synth_settings_path
from odatix.gui.jobs_config.pnr import _pnr_sources_by_tool, _pnr_tool_of

def _run_context(search, odatix_settings) -> dict:
    """
    Resolve everything that differs between job types (architectures vs
    workflows) from the ?type=... url parameter.

    Returns a dict with:
        mode           : "workflow" or "arch"
        base_path      : architectures / workflows directory
        settings_path  : the selection settings file to read/write
        selection_key  : the yaml key holding the selection ("workflows" / "architectures")
        instances      : list of instance names to display
        settings_link  : lambda name -> settings editor url
        config_link    : lambda name -> config editor url
        settings_text  : label of the settings button
        title          : plural heading of the instance section
    """
    settings = odatix_settings or {}
    run_mode = get_key_from_url(search, "type")
    if run_mode == "simulation":
        base_path = settings.get("sim_path", OdatixSettings.DEFAULT_SIM_PATH)
        return {
            "mode": "simulation",
            "base_path": base_path,
            # Simulations run *on* architectures, so a simulation section needs
            # the architecture directory too (unlike every other job type, where
            # base_path is the only directory involved).
            "arch_path": settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH),
            "settings_path": settings.get("simulation_settings_file", OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE),
            "selection_key": "simulations",
            "instances": workspace.get_simulations(base_path),
            "settings_link": lambda name: f"/sim_editor?sim={name}",
            "config_link": lambda name: f"/metric_editor?simulation={name}",
            "config_text": "Edit Metrics",
            "settings_text": "Simulation Settings",
            "title": "Simulations",
        }
    if run_mode == "pnr":
        # A place & route run selects completed synthesis jobs, not
        # architectures: the "instances" are the eda tools that ran them, and
        # each card holds the jobs that tool produced.
        work_root = settings.get("work_path", OdatixSettings.DEFAULT_WORK_PATH)
        sources_by_tool = _pnr_sources_by_tool(work_root, settings)
        return {
            "mode": "pnr",
            "base_path": work_root,
            # The parameter domains of a source are read back from its work
            # directory name, which needs the domain names of the architecture
            # it was synthesized from (see _pnr_split_config_token).
            "arch_path": settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH),
            "settings_path": _get_synth_settings_path(search, settings),
            "selection_key": "sources",
            "instances": list(sources_by_tool.keys()),
            "sources_by_tool": sources_by_tool,
            "settings_link": lambda name: f"/tool_editor?tool={_pnr_tool_of(name)}",
            "config_link": lambda name: f"/metric_editor?tool={_pnr_tool_of(name)}",
            "settings_text": "Tool Settings",
            "config_text": "Edit Metrics",
            "title": "Synthesized designs",
        }
    if run_mode == "workflow":
        base_path = settings.get("workflow_path", OdatixSettings.DEFAULT_WORKFLOW_PATH)
        return {
            "mode": "workflow",
            "base_path": base_path,
            "settings_path": settings.get("workflow_settings_file", OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE),
            "selection_key": "workflows",
            "instances": workspace.get_workflows(base_path),
            "settings_link": lambda name: f"/workflow_editor?workflow={name}",
            "config_link": lambda name: f"/config_editor?workflow={name}",
            "settings_text": "Workflow Settings",
            "config_text": "Edit Configs",
            "title": "Workflows",
        }
    base_path = settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    return {
        "mode": "arch",
        "base_path": base_path,
        "settings_path": _get_synth_settings_path(search, settings),
        "selection_key": "architectures",
        "instances": workspace.get_architectures(base_path),
        "settings_link": lambda name: f"/arch_editor?arch={name}",
        "config_link": lambda name: f"/config_editor?arch={name}",
        "settings_text": "Architecture Settings",
        "config_text": "Edit Configs",
        "title": "Architectures",
    }
