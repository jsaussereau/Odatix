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
Where the Configuration Generator used to be.

Generating configuration files was a step of its own as long as a run needed
the files to exist. It no longer does: a run resolves what the rules of a
domain describe, so describing them belongs next to the configurations they
produce -- in the configuration editor, one folded panel per parameter domain
(odatix.gui.config_rules).

The route is kept so that a bookmark, a link in a document or an old
"odatix-gui" invocation lands on the domain it was pointing at rather than on a
404.
"""

import dash
from dash import html, dcc, Input, Output

import odatix.gui.ui_components as ui
from odatix.gui.utils import get_key_from_url, get_instance_mode

page_path = "/config_generator"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Configuration Editor',
    name='Configuration Generator',
    order=5,
)


def editor_link(search):
    """The configuration editor of whatever instance the old URL named."""
    mode, instance_name = get_instance_mode(search)
    key = "workflow" if mode == "workflow" else "arch"
    if not instance_name:
        return "/architectures"
    link = "/{0}?{1}={2}".format("config_editor", key, instance_name)
    domain = get_key_from_url(search, "domain")
    if domain:
        link += "&domain={0}".format(domain)
    return link


@dash.callback(
    Output({"page": page_path, "type": "redirect"}, "pathname"),
    Output({"page": page_path, "type": "redirect"}, "search"),
    Input("url", "search"),
    Input("url", "pathname"),
)
def redirect_to_editor(search, pathname):
    if pathname != page_path:
        return dash.no_update, dash.no_update
    link = editor_link(search)
    path, _, query = link.partition("?")
    return path, ("?" + query) if query else ""


layout = html.Div(
    children=[
        dcc.Location(id="url"),
        dcc.Location(id={"page": page_path, "type": "redirect"}),
        ui.empty_state(
            "The configuration generator is now part of the configuration editor, "
            "under \"Configuration rules\" in each parameter domain."
        ),
    ],
    className="page-content",
)
