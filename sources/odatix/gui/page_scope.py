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
Page scoping for Dash callbacks.

Dash dispatches a callback as soon as every one of its ``Input`` components is
present in the current layout. A callback whose inputs are *all* pattern-matching
(``ALL``/``MATCH``) has nothing to anchor it: an ``ALL`` selector that matches
zero components still resolves — to an empty list — so the callback fires on
every page of the app, not just the one it was written for. With ~90 such
callbacks that means a burst of useless round-trips on every navigation.

The fix is to give each of them one concrete input that only exists on their own
page. ``scoped()`` drops that anchor store into a page layout and
``page_callback()`` registers a callback bound to it:

    PAGE = "config_editor"

    @page_callback(PAGE, Output({"type": "row", "index": ALL}, "value"),
                   Input({"type": "field", "index": ALL}, "value"))
    def update_rows(values):   # the anchor argument is stripped for you
        ...

    layout = scoped(PAGE, html.Div([...]))

A scope is not always a page: shared modules (``config_rules``,
``jobs_config``, the explorer shell) register their callbacks under a scope name
of their own, and every page embedding them includes the matching anchor.
"""

import functools

import dash
from dash import dcc, html
from dash.dependencies import Input, State


def anchor_id(scope):
    """Id of the store anchoring `scope`'s callbacks to the pages that host it."""
    return "page-anchor-" + scope


def anchor(scope):
    """Marker store to embed in the layout of every page hosting `scope`."""
    return dcc.Store(id=anchor_id(scope), data=scope)


def scoped(scope, *layout):
    """Wrap a page layout so that `scope`'s callbacks are dispatched on it."""
    return html.Div(
        [anchor(scope), *layout],
        style={"display": "contents"},
    )


def _with_anchor(scope, deps):
    """
    Insert the anchor input as the *first* input of `deps`.

    Dash passes callback arguments as inputs (in declaration order) followed by
    states, so an anchor declared before every other input always lands in
    ``args[0]`` — which is what `page_callback` strips off. The nesting of the
    original deps is preserved: dash unwraps a single output differently
    depending on whether it was passed bare or in a list.
    """
    marker = Input(anchor_id(scope), "data")
    out = []
    inserted = False
    for dep in deps:
        if not inserted:
            if isinstance(dep, (Input, State)):
                out.append(marker)
                inserted = True
            elif isinstance(dep, (list, tuple)) and any(
                isinstance(d, (Input, State)) for d in dep
            ):
                nested = list(dep)
                at = next(
                    i for i, d in enumerate(nested) if isinstance(d, (Input, State))
                )
                nested.insert(at, marker)
                dep = type(dep)(nested) if isinstance(dep, tuple) else nested
                inserted = True
        out.append(dep)
    if not inserted:
        out.append(marker)
    return out


def page_callback(scope, *deps, **kwargs):
    """
    ``dash.callback`` restricted to the pages that embed ``anchor(scope)``.

    Same signature as ``dash.callback`` with the scope name prepended. The
    decorated function keeps its original signature: the anchor value is
    consumed here and never reaches it.
    """
    scoped_deps = _with_anchor(scope, deps)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **func_kwargs):
            return func(*args[1:], **func_kwargs)

        # Dash inspects the signature for its flexible-signature support; keeping
        # `__wrapped__` would expose the *unscoped* one and shift every argument.
        del wrapper.__wrapped__
        dash.callback(*scoped_deps, **kwargs)(wrapper)
        # Return the undecorated function, not the anchor-stripping wrapper:
        # several callbacks are also called directly by another module (the
        # jobs_config simulation callbacks reuse the configuration ones), and
        # such a call must not have its first argument eaten.
        return func

    return decorator


def page_clientside_callback(scope, func, *deps, **kwargs):
    """
    ``dash.clientside_callback`` restricted to `scope`, same anchoring rule.

    The anchor lands in ``args[0]`` of the JavaScript function too; asset-side
    handlers declare it as a leading ``_scope`` parameter and ignore it.
    """
    return dash.clientside_callback(func, *_with_anchor(scope, deps), **kwargs)
