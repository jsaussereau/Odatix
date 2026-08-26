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
Starting an exploration from the page: working out what it would do, then
handing it to the daemon.

Both phases are the ones "odatix dse" runs -- :meth:`Exploration.check` and
:func:`odatix.dse.driver.build_driver` -- with the confirmation the terminal
asks for replaced by the popup the page shows. The state lives at module level
like the run state of the "Run jobs" page, and is always reached through this
module rather than imported by name, so that the callbacks see what the
background thread wrote.
"""

import threading

import odatix.lib.printc as printc
from odatix.lib.run_report import MessageLog

#: What the check phase is doing, and what it found.
status = {"status": "idle", "error": None}
#: What each selected campaign amounts to, one entry per campaign.
plan = []
#: Everything the check said, as the popup lists it.
messages = MessageLog()
#: The exploration that was checked, kept for the Start button.
checked = None
#: Where the monitor is to be sent once the exploration is enqueued.
monitor_href = None
#: What was checked, as the page holds it: the exploration Start hands over.
request = None

_check_thread = None
_start_thread = None
_start_lock = threading.Lock()
_started = False


def reset():
    """Forget the previous exploration: a new one is being checked."""
    global status, plan, messages, checked, monitor_href, _started
    status = {"status": "checking", "error": None}
    plan = []
    messages = MessageLog()
    checked = None
    monitor_href = None
    _started = False


######################################
# What it would do
######################################

def _describe(campaign):
    """One campaign of the plan, as the popup shows it."""
    entry = {
        "name": campaign.name,
        "campaign": campaign.campaign_name,
        "architecture": campaign.architecture.name,
        "budget": campaign.budget,
        "space": campaign.space_size,
        "batch": int(campaign.search.batch),
        "strategy": campaign.strategy.name,
        "mode": campaign.search.mode,
        "objectives": campaign.describe_objectives(),
        "description": campaign.describe(),
    }
    try:
        entry["toolchains"] = [chain.label for chain in campaign.toolchains]
    except Exception:
        entry["toolchains"] = []
    return entry


def start_check(workspace, settings, campaigns, session=None):
    """
    Work out what the exploration would do, without touching anything.

    Args:
        workspace (Workspace): the workspace being explored.
        settings (DseSettings): how the exploration is run, as the page holds
            it -- saved or not.
        campaigns (list): the campaigns it runs, as the page holds them.
        session (str): the daemon session it would run in.
    """
    global status, plan, checked
    from odatix.dse.campaign import CampaignError, Exploration

    try:
        exploration = Exploration(workspace, settings, session=session, campaigns=campaigns)
        with printc.collect(messages.add):
            campaigns = exploration.check()
            plan = [_describe(campaign) for campaign in campaigns]
        checked = exploration
        status = {"status": "checked", "error": None}
    except CampaignError as error:
        messages.add("error", str(error))
        status = {"status": "error", "error": str(error)}
    except Exception as error:
        messages.add("error", str(error))
        status = {"status": "error", "error": str(error)}


def check(workspace, settings, campaigns, session=None):
    """Run :func:`start_check` in the background, and say it started."""
    global _check_thread, request

    reset()
    request = {
        "workspace": workspace,
        "settings": settings,
        "campaigns": campaigns,
        "session": session,
    }
    _check_thread = threading.Thread(
        target=start_check,
        args=(workspace, settings, campaigns, session),
        daemon=True,
    )
    _check_thread.start()
    return status


def is_checking():
    return _check_thread is not None and _check_thread.is_alive()


######################################
# Doing it
######################################

def _start(workspace, settings, campaigns, session=None):
    """Hand the exploration to the daemon, and remember where to watch it."""
    global status, monitor_href
    from urllib.parse import quote

    from odatix.dse.driver import build_driver, default_session
    from odatix.lib.parallel_job_handler import daemon_control

    try:
        with printc.collect(messages.add):
            session = default_session(session)
            handler = build_driver(
                workspace, settings, session,
                architectures=[campaign.name for campaign in campaigns],
                campaigns=campaigns,
            )
            state, _response = daemon_control.enqueue_parallel_jobs(handler, session=session)
        session_id = str(state.get("session_id", "")).strip() or str(state.get("session_name", "")).strip()
        monitor_href = "/monitor?session={0}".format(quote(session_id or session, safe=""))
        status = {"status": "started", "error": None}
    except Exception as error:
        messages.add("error", "Failed to start the exploration: {0}".format(error))
        status = {"status": "error", "error": str(error)}


def start():
    """
    Start what was checked, once.

    The Start button is polled by the popup like every other run of the app: the
    guard here is what keeps a second click from enqueueing a second driver.
    """
    global _start_thread, _started, status

    if not request:
        return status
    with _start_lock:
        if _started:
            return status
        _started = True
    status = {"status": "starting", "error": None}
    _start_thread = threading.Thread(
        target=_start,
        args=(request["workspace"], request["settings"], request["campaigns"], request["session"]),
        daemon=True,
    )
    _start_thread.start()
    return status
