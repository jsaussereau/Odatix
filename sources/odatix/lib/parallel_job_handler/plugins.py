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
What the job handler asks the program using it to do.

A job crosses the transport to reach its session, which runs in another
process: what it should do when it is over cannot travel as a function. It
travels as a name -- ``{"kind": "synthesis", ...}`` for an export -- and the
session looks that name up here. The handlers themselves are registered by
plugins: modules a session imports when it starts (see :func:`load`), which
call the ``register_*`` functions below on import.

Four families of named handlers:

- ``post_run``: run once a job succeeded, off the scheduler thread, as
  ``handler(job=job, export_config=config) -> bool`` (False fails the job);
- ``post_batch``: run once every job of a batch retired, as
  ``handler(action_dict)``;
- ``progress``: how a job of a given ``progress_mode`` reads its progress, as
  ``handler(job) -> 0..100`` (the "default" mode is built in);

and single services, each optional:

- ``export_buffer``: an object with ``deferred(interval_s)`` (a context
  manager), ``flush()`` and ``flush_due()``, wrapped around the exports so
  that a burst of them is written at once;
- ``step_store``: an object with ``record(tmp_dir, step, flow)``,
  ``forget_from(tmp_dir, index)`` and ``count(tmp_dir)``, which keeps the
  steps of a job that are done so that a later run can resume after them;
- ``version``: a function returning the version a session reports;
- ``resource_guard_defaults``: a function returning (enabled, cpu_limit,
  mem_limit) for the sessions that are not told;
- ``session_access``: a function of a workspace root returning who its sessions
  are shared with ("user", "group", "other", or None when it does not say),
  and where it read that, as a pair;
- ``daemon_pythonpath``: a function of a workspace root returning directories
  a daemon started there must find its plugins in.
"""

import contextlib
import importlib

from .config import CONFIG

__all__ = [
    "PluginError",
    "register_post_run",
    "register_post_batch",
    "register_progress",
    "register_service",
    "post_run_handler",
    "post_batch_handler",
    "progress_handler",
    "service",
    "load",
    "loaded",
]

POST_RUN = "post_run"
POST_BATCH = "post_batch"
PROGRESS = "progress"

SERVICES = (
    "export_buffer",
    "step_store",
    "version",
    "resource_guard_defaults",
    "session_access",
    "daemon_pythonpath",
)

_handlers = {POST_RUN: {}, POST_BATCH: {}, PROGRESS: {}}
_services = {}
_loaded = []


class PluginError(Exception):
    """A plugin that cannot be loaded, or a name nothing was registered under."""


def _kind(name):
    return str(name or "").strip().lower()


def _register(family, kind, handler):
    kind = _kind(kind)
    if not kind:
        raise PluginError("a " + family + " handler needs a name")
    if not callable(handler):
        raise PluginError("the " + family + " handler '" + kind + "' is not callable")
    _handlers[family][kind] = handler
    return handler


def register_post_run(kind, handler):
    """Run `handler` after each successful job whose ``post_run_export`` names `kind`."""
    return _register(POST_RUN, kind, handler)


def register_post_batch(kind, handler):
    """Run `handler` once a batch whose ``post_batch_action`` names `kind` is over."""
    return _register(POST_BATCH, kind, handler)


def register_progress(mode, handler):
    """Read the progress of the jobs whose ``progress_mode`` is `mode` with `handler`."""
    return _register(PROGRESS, mode, handler)


def register_service(name, value):
    """Provide one of the :data:`SERVICES`."""
    if name not in SERVICES:
        raise PluginError("unknown job handler service '" + str(name) + "'")
    _services[name] = value
    return value


def _lookup(family, kind):
    load()
    return _handlers[family].get(_kind(kind))


def post_run_handler(kind):
    """The handler registered for an export `kind`, or None."""
    return _lookup(POST_RUN, kind)


def post_batch_handler(kind):
    """The handler registered for a batch action `kind`, or None."""
    return _lookup(POST_BATCH, kind)


def progress_handler(mode):
    """The handler registered for a progress `mode`, or None."""
    return _lookup(PROGRESS, mode)


def service(name, default=None):
    """A service a plugin provides, or `default`."""
    load()
    return _services.get(name, default)


class _NoExportBuffer(object):
    """What the exports run inside when no plugin buffers them: nothing."""

    @contextlib.contextmanager
    def deferred(self, interval_s):
        yield

    def flush(self):
        pass

    def flush_due(self):
        pass


NO_EXPORT_BUFFER = _NoExportBuffer()


def export_buffer():
    return service("export_buffer", NO_EXPORT_BUFFER)


def load(modules=None):
    """
    Import the plugin modules not imported yet: `modules`, else those set in
    the configuration (CONFIG.plugins). Returns the modules loaded so far.

    A module that cannot be imported raises PluginError: a session missing the
    plugin its jobs name would only fail them one by one, later, with a less
    useful message.
    """
    names = list(CONFIG.plugins) if modules is None else list(modules)
    for name in names:
        name = str(name)
        if name in _loaded:
            continue
        # Marked first: a plugin importing the package would come back here.
        _loaded.append(name)
        try:
            importlib.import_module(name)
        except Exception as e:
            _loaded.remove(name)
            raise PluginError("cannot load the job handler plugin '" + name + "': " + str(e))
        if name not in CONFIG.plugins:
            CONFIG.plugins.append(name)
    return list(_loaded)


def loaded():
    """The plugin modules imported so far."""
    return list(_loaded)
