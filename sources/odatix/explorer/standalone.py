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
Standalone shell of Odatix Explorer: a minimal Dash app hosting the explorer
pages outside of Odatix GUI, with the same theming (the GUI assets folder is
served directly, so both share themes.css / explorer.css / style.css).
"""

import os

import dash
from dash import dcc, html
from dash.dependencies import Input, Output

import odatix.gui
import odatix.gui.themes as gui_themes
import odatix.components.motd as motd
import odatix.lib.printc as printc
import odatix.lib.term_mode as term_mode
from odatix.lib.utils import internal_error

from odatix.explorer.integration import register_explorer
from odatix.explorer.core.store import STORE

script_name = os.path.basename(__file__)
error_logfile = "odatix-explorer_error.log"

top_bar_height = "50px"


class ExplorerStandaloneApp:
  def __init__(self, result_path="results", old_settings=None, safe_mode=False, theme=None):
    if theme is None or theme not in gui_themes.list:
      if theme is not None:
        printc.warning('Theme "' + str(theme) + '" does not exist. Using default theme.', script_name=script_name)
      theme = gui_themes.default_theme
    self.start_theme = theme
    self.result_path = result_path
    self.old_settings = old_settings
    self.safe_mode = safe_mode

    gui_assets = os.path.join(os.path.dirname(os.path.abspath(odatix.gui.__file__)), "assets")

    self.app = dash.Dash(
      name=__name__,
      use_pages=True,
      pages_folder="",  # pages register themselves at import (register_explorer)
      assets_folder=gui_assets,
      title="Odatix Explorer",
      update_title=None,
      suppress_callback_exceptions=True,
    )

    self.app.server.register_error_handler(Exception, self.handle_flask_exception)

    register_explorer(self.app)
    self._register_root_redirect()
    STORE.configure(result_path)

    self.setup_layout()
    self.setup_callbacks()

  def _register_root_redirect(self):
    dash.register_page("explorer_root", path="/", layout=lambda **kwargs: dcc.Location(id="xp-root-redirect", pathname="/explorer"))

  def handle_flask_exception(self, e):
    if self.old_settings is not None:
      term_mode.restore_mode(self.old_settings)
    internal_error(e, error_logfile, script_name)
    if not self.safe_mode:
      os._exit(-1)

  def top_bar(self):
    version = motd.read_version()
    pages = [page for page in dash.page_registry.values() if str(page.get("path", "")).startswith("/explorer/")]
    pages.sort(key=lambda page: page.get("order", 0))
    return html.Div(
      children=[
        dcc.Link(
          id="navbar-title",
          className="link",
          href="/explorer",
          children=[
            html.Span(
              html.Div(
                children=[
                  html.Span("Odatix Explorer " + str(version), className="link-title1 title"),
                  html.Span("Home", className="link-title2 title"),
                ],
                className="link-container",
              ),
              className="mask",
            )
          ],
          style={"position": "block", "marginLeft": "30px", "left": "75px", "zIndex": "2", "transition": "marginLeft 0.25s"},
        ),
        html.Div(
          [
            html.Div(
              [
                html.Div(dcc.Link(page["name"], href=page["relative_path"], className="nav-link"))
                for page in pages
              ],
              className="nav-links",
            ),
            html.Div(
              children=[
                dcc.Dropdown(
                  id="theme-dropdown",
                  options=[{"label": theme, "value": theme} for theme in gui_themes.list],
                  value=self.start_theme,
                  className="theme-dropdown",
                  clearable=False,
                  style={"width": "150px", "marginRight": "20px", "marginTop": "3px"},
                )
              ],
              className="tooltip delay bottom auto",
              **{"data-tooltip": "Select Theme"},
            ),
          ],
          id="nav-right",
          style={"display": "flex", "position": "absolute", "right": "0", "alignItems": "center", "justifyContent": "right", "zIndex": "1000"},
        ),
      ],
      style={"height": top_bar_height},
      className="navbar",
      id="navbar",
    )

  def setup_layout(self):
    self.app.layout = html.Div(
      children=[
        self.top_bar(),
        dcc.Location(id="url-global"),
        dcc.Store(id="odatix-settings", data={"result_path": self.result_path}),
        html.Div([dash.page_container], id="content", className="content", style={"height": "100%"}),
      ],
      id="theme",
      className="theme " + self.start_theme,
      style={"width": "100%", "height": "100%", "display": "flex", "flexDirection": "column"},
    )

  def setup_callbacks(self):
    @self.app.callback(
      Output("theme", "className"),
      Input("theme-dropdown", "value"),
    )
    def update_theme(theme):
      return "theme " + str(theme)

  def run(self):
    self.app.run(host="127.0.0.1", debug=True)


if __name__ == "__main__":
  ExplorerStandaloneApp().run()
