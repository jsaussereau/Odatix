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
Registration of Odatix Explorer into a host Dash app.

The host (Odatix GUI or the standalone shell) must be a
dash.Dash(use_pages=True) app providing in its root layout:
  - a "theme" div whose className carries the app theme ("theme <name>"),
  - the "theme-dropdown" theme selector,
  - an "odatix-settings" dcc.Store holding at least {"result_path": ...}.
"""

import os

from odatix.explorer.core.store import STORE


def register_explorer(app=None, settings=None):
  """
  Register the explorer pages and callbacks into the current Dash app, and
  optionally point the result store at the workspace result path.

  Args:
      app: the host dash.Dash instance (unused, kept for call-site clarity —
          Dash pages and callbacks register into the app of the process).
      settings: an OdatixSettings instance or a settings dict, used for the
          initial result path (the odatix-settings store keeps it up to date
          afterwards).
  """
  import odatix.explorer.pages  # noqa: F401 — importing registers the pages
  from odatix.explorer.callbacks import register_callbacks
  register_callbacks()

  result_path = None
  if isinstance(settings, dict):
    result_path = settings.get("result_path")
  elif settings is not None and getattr(settings, "valid", False):
    result_path = getattr(settings, "result_path", None)
  if result_path and os.path.isdir(result_path):
    STORE.configure(result_path)
