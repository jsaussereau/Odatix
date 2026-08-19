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
The campaigns of a workspace: one file each, and the ones a run selects.

What an exploration is looking for and how it is run are two different
questions, and they used to be answered in one file. They are separated here:
a campaign is a file of "odatix_userconfig/dse_campaigns", holding the
architectures, the objectives, the constraints and the search; and
"dse_settings.yml" only says which of them to run, next to the settings of the
run itself.

That is what makes two campaigns on the same architecture, with the same
domains fixed, two campaigns: they are two files, so they have two names, so
they have two archives (see :attr:`odatix.dse.campaign.Campaign.name`).
"""

import os

from odatix.dse.settings import CampaignSettings
from odatix.workspace.settings import load_settings

__all__ = [
    "CampaignNotFoundError",
    "RunSettings",
    "campaign_path",
    "available_campaigns",
    "load_campaign",
    "resolve_campaigns",
]

#: What a campaign file is called.
EXTENSIONS = (".yml", ".yaml")


class CampaignNotFoundError(RuntimeError):
    """A campaign was named that the workspace does not hold."""


######################################
# Where they are
######################################

def campaign_path(workspace, name):
    """
    The file one campaign is written in, whichever extension it uses.

    Returns:
        str: the file, or the ".yml" one when there is none yet -- which is
        what an error message has to name.
    """
    directory = workspace.paths.dse_campaign_path
    for extension in EXTENSIONS:
        path = os.path.join(directory, "{0}{1}".format(name, extension))
        if os.path.isfile(path):
            return path
    return os.path.join(directory, "{0}.yml".format(name))


def available_campaigns(workspace):
    """The campaigns the workspace holds, by name, in alphabetical order."""
    directory = workspace.paths.dse_campaign_path
    if not os.path.isdir(directory):
        return []
    names = set()
    for entry in os.listdir(directory):
        name, extension = os.path.splitext(entry)
        if extension.lower() in EXTENSIONS and not name.startswith("."):
            names.add(name)
    return sorted(names)


######################################
# Reading them
######################################

def load_campaign(workspace, name, body=None):
    """
    One campaign, read from its file -- or from `body`, when the run already
    holds it.

    Args:
        workspace (Workspace): the workspace being explored.
        name (str): what the campaign is called, which is what its file is
            called.
        body (dict): the campaign as an exploration handed to the daemon writes
            it, inline. Its file is not read when one is given.

    Returns:
        CampaignSettings: what the campaign is looking for, named.

    Raises:
        CampaignNotFoundError: there is no such campaign.
    """
    if body is not None:
        settings = CampaignSettings.from_dict(body)
    else:
        path = campaign_path(workspace, name)
        if not os.path.isfile(path):
            raise CampaignNotFoundError(_not_found_message(workspace, name, path))
        settings = load_settings(CampaignSettings, path)
    object.__setattr__(settings, "name", name)
    return settings


def resolve_campaigns(workspace, settings, names=None):
    """
    The campaigns a run selects, read and named.

    Args:
        workspace (Workspace): the workspace being explored.
        settings (DseSettings): what the run was asked to do.
        names (list): campaigns named on the command line, which replace the
            ones the settings file selects.

    Returns:
        list: one :class:`~odatix.dse.settings.CampaignSettings` per campaign,
        in the order they were named.

    Raises:
        CampaignNotFoundError: one of them does not exist.
    """
    if names:
        entries = [(str(name).strip(), None) for name in names if str(name).strip()]
    else:
        entries = settings.campaign_entries()
    return [load_campaign(workspace, name, body) for name, body in entries]


def inline(settings, campaigns):
    """
    Write the campaigns into the run settings, as their own bodies.

    An exploration handed to the daemon is given one file and reads nothing
    else: what the command line resolved has to be in it, campaigns included,
    or the worker would read the campaign files again and undo every override
    (see :mod:`odatix.dse.driver`).
    """
    settings.campaigns = [
        {campaign.name: campaign.to_dict()} for campaign in campaigns
    ]
    return settings


def _not_found_message(workspace, name, path):
    """What to say when a campaign is named that is not there."""
    available = available_campaigns(workspace)
    message = "No campaign called \"{0}\": \"{1}\" does not exist.".format(name, path)
    if available:
        return message + " This workspace holds: {0}.".format(", ".join(available))
    return message + (
        " A campaign is a file of \"{0}\", saying which architectures to explore, what makes "
        "a design good, and how long to look for it.".format(workspace.paths.dse_campaign_path)
    )


######################################
# What a campaign is run with
######################################

class RunSettings(object):
    """
    One campaign, together with the settings of the run it is part of.

    A campaign says what to search for; the run says how it is run -- how many
    jobs at once, whether what is already done is evaluated again. Both are
    read the same way by everything that runs a design, so both are reached
    through one object rather than being passed around as a pair.

    Args:
        campaign (CampaignSettings): what this campaign is looking for.
        settings (DseSettings): the run it is part of.
    """

    def __init__(self, campaign, settings):
        self.campaign = campaign
        self.settings = settings

    @property
    def name(self):
        """What the campaign is called, which is what its file is called."""
        return getattr(self.campaign, "name", "")

    def __setattr__(self, attribute, value):
        # A setting is written where it is read from, or the campaign and the
        # object standing for it would not say the same thing.
        if attribute not in ("campaign", "settings"):
            if type(self.campaign).spec(attribute) is not None:
                setattr(self.campaign, attribute, value)
                return
            if type(self.settings).spec(attribute) is not None:
                setattr(self.settings, attribute, value)
                return
        object.__setattr__(self, attribute, value)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __getattr__(self, attribute):
        # Anything the campaign does not answer is a setting of the run: the
        # two never declare the same key, so there is nothing to arbitrate.
        try:
            return getattr(self.campaign, attribute)
        except AttributeError:
            pass
        try:
            return getattr(self.settings, attribute)
        except AttributeError:
            raise AttributeError(attribute)

    def __repr__(self):
        return "<RunSettings {0}>".format(self.name)
