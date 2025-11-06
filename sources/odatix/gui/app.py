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

import os
import sys
import dash
from dash import dcc, html

import odatix.gui.navigation as navigation
import odatix.gui.themes as themes

import odatix.lib.printc as printc
from odatix.lib.utils import internal_error
import odatix.lib.term_mode as term_mode
from odatix.lib.settings import OdatixSettings

script_name = os.path.basename(__file__)
error_logfile = "odatix-gui_error.log"

class OdatixApp:
    def __init__(self,  old_settings=None, safe_mode=False, config_file=OdatixSettings.DEFAULT_SETTINGS_FILE, theme=themes.default_theme):
        
        # Get settings
        self.odatix_settings = OdatixSettings(config_file)
        if not self.odatix_settings.valid:
            sys.exit(-1)

        if theme is None:
            self.start_theme = themes.default_theme
        elif theme not in themes.list:
            printc.warning('Theme "' + str(theme) + '" does not exist. Using default theme.')
            self.start_theme = themes.default_theme
        else:
            self.start_theme = theme

        self.old_settings = old_settings
        self.safe_mode = safe_mode

        self.app = dash.Dash(
            name=__name__, 
            use_pages=True,
            title="Odatix",
            update_title="Odatix - Updating...",
            suppress_callback_exceptions=True
        )

        self.app.server.register_error_handler(Exception, self.handle_flask_exception)

        self.setup_layout()
        self.setup_callbacks()

    def handle_flask_exception(self, e):
        """
        Handle flask exceptions
        """
        if self.old_settings is not None:
            term_mode.restore_mode(self.old_settings)
        internal_error(e, error_logfile, script_name)
        if not self.safe_mode:
            os._exit(-1)

    def setup_layout(self):
        """
        Setup the layout of the Dash application.
        """
        self.app.layout = html.Div(
            children=[
                navigation.top_bar(self),
                navigation.side_bar(self),
                dcc.Store(id="previous-url", data=""),
                dcc.Store(id="odatix-settings", data=self.odatix_settings.to_dict()),
                html.Div(
                    [dash.page_container],
                    id="content",
                    className="content",
                    style={
                        "marginLeft": navigation.side_bar_width,
                        "width": "calc(100%-" + navigation.side_bar_width + ")",
                        "height": "100%",
                    },
                ),
            ],
            id="theme",
            style={
                "width": "100%",
                "height": "100%",
                "display": "flex",
                "flexDirection": "column"
            },
        )

    def setup_callbacks(self):
        """
        Setup Dash callbacks for interactivity.
        """
        navigation.setup_callbacks(self)


    def run(self):
        self.app.run(
            # host='0.0.0.0',
            host='127.0.0.1',
            debug=True
        )


if __name__ == "__main__":
    gui = OdatixApp()
    gui.run()
