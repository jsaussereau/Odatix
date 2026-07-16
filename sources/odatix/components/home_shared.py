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

"""Shared Home page building blocks for Odatix GUI and Odatix Explorer."""

from typing import Any, Callable, Iterable, Mapping

from dash import dcc, html
from dash.development.base_component import Component


def home_header(title: str, subtitle: str = "") -> Component:
  children = [html.H1(title, className="xp-home-title")]
  if subtitle:
    children.append(html.P(subtitle, className="xp-home-subtitle"))
  return html.Div(children, className="xp-home-header")


def home_card(card: Mapping[str, Any], visual: Component) -> Component:
  content = html.Div(
    [
      visual,
      html.Div(card.get("name", ""), className="xp-card-title"),
      html.Div(card.get("description", ""), className="xp-card-description"),
    ],
    className="xp-card",
  )

  href = card.get("link")
  if href:
    return dcc.Link(content, href=href, className="xp-card-link")

  card_id = card.get("id")
  if card_id:
    return html.Button(content, id=card_id, n_clicks=0, type="button", className="xp-card-button")

  return html.Div(content, className="xp-card-link")


def home_card_grid(cards: Iterable[Mapping[str, Any]], visual_factory: Callable[[Mapping[str, Any]], Component]) -> Component:
  return html.Div([home_card(card, visual_factory(card)) for card in cards], className="xp-card-grid")
