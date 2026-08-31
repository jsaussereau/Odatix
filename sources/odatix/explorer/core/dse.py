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
The exploration archives, as the explorer reads them.

The designs a campaign evaluated are exported as an ordinary results source
and read by the result store like everything else (see
:mod:`odatix.dse.export`). What is *not* in there is the search itself: what
was being looked for, how the front grew batch after batch, and which designs
failed and why. That is in the archives the campaigns write
(``<result_path>/dse/<campaign>.yml``), and this module reads them.

Reads are cached by modification time, the way the result store watches its
own files: an exploration is read *while it runs*, so the page has to poll,
and re-parsing every archive twice a second to answer "has it changed" would
not do.
"""

import os
import threading

import yaml

from odatix.lib.yaml_loader import SafeLoader as _YamlLoader

DSE_SUBDIR = "dse"


class Campaign(object):
  """One exploration archive, as it was written."""

  def __init__(self, name, path, data=None):
    self.name = name
    self.path = path
    self._lock = threading.RLock()
    self._data = data if isinstance(data, dict) else None
    self._error = None
    self._read = data is not None

  ######################################
  # Read when asked, not when listed
  ######################################

  def _load(self):
    """
    Parse the archive, once.

    The page lists every campaign of the workspace to fill its picker but draws
    one: parsing them all up front is most of a second per megabyte thrown away,
    and there are workspaces with a dozen archives.
    """
    with self._lock:
      if self._read:
        return
      self._read = True
      try:
        with open(self.path, "r") as file:
          data = yaml.load(file, Loader=_YamlLoader) or {}
        if isinstance(data, dict):
          self._data = data
        else:
          self._data, self._error = {}, "not an exploration archive"
      except Exception as error:
        self._data, self._error = {}, str(error)

  @property
  def data(self):
    self._load()
    return self._data or {}

  @property
  def error(self):
    self._load()
    return self._error

  ######################################
  # What it was looking for
  ######################################

  @property
  def architecture(self):
    return str(self.data.get("architecture") or self.name)

  @property
  def strategy(self):
    return str(self.data.get("strategy") or "")

  @property
  def objectives(self):
    """
    ``[{"metric": ..., "goal": "min"|"max"}, ...]``, however the archive wrote
    them -- a bare metric name means minimize, which is what the settings mean
    by it too.
    """
    objectives = []
    for entry in self.data.get("objectives") or []:
      if isinstance(entry, dict):
        metric = str(entry.get("metric", "") or "")
        goal = str(entry.get("goal", "min") or "min")
      else:
        metric, goal = str(entry), "min"
      if metric:
        objectives.append({"metric": metric, "goal": goal})
    return objectives

  @property
  def constraints(self):
    return [entry for entry in (self.data.get("constraints") or []) if isinstance(entry, dict)]

  @property
  def feasible(self):
    """
    Whether the answer meets the constraints -- None when there were none.

    False is the campaign saying it never found the feasible part of the
    space: the designs it reports are the closest it got, not the answer.
    """
    if not self.constraints:
      return None
    return bool(self.data.get("feasible"))

  ######################################
  # What it found
  ######################################

  @property
  def front(self):
    return [record for record in (self.data.get("front") or []) if isinstance(record, dict)]

  @property
  def evaluations(self):
    return [record for record in (self.data.get("evaluations") or []) if isinstance(record, dict)]

  @property
  def history(self):
    """How the front grew, one entry per batch (empty for older archives)."""
    return [entry for entry in (self.data.get("history") or []) if isinstance(entry, dict)]

  @property
  def failed(self):
    return [record for record in self.evaluations if record.get("failed")]

  def counts(self):
    """The headline numbers of the campaign."""
    evaluated = self.data.get("evaluated")
    measured = self.data.get("measured")
    return {
      "space": self.data.get("designs_in_space") or 0,
      "evaluated": len(self.evaluations) if evaluated is None else evaluated,
      "measured": len(self.evaluations) - len(self.failed) if measured is None else measured,
      "failed": len(self.failed),
      "front": len(self.front),
      "batches": len(self.history),
      "hypervolume": self.data.get("hypervolume"),
    }

  def __repr__(self):
    return "<Campaign {0} ({1} on the front)>".format(self.name, len(self.front))


class CampaignStore(object):
  """
  The archives of a result directory, re-read only when they change.

  A process-wide singleton like the result store, and for the same reason: the
  page polls, and every callback of every browser tab polls with it.
  """

  def __init__(self):
    self._lock = threading.RLock()
    self._cache = {}   # path -> (mtime, size, Campaign)
    self._version = 0

  def directory(self, result_path):
    return os.path.join(str(result_path or ""), DSE_SUBDIR)

  def campaigns(self, result_path):
    """
    Every campaign of a workspace, by name.

    The archives are not parsed here -- a campaign reads its own file the
    first time something asks it for its contents.

    A file that cannot be read is not dropped: it comes back as a campaign
    carrying its error, because "the archive is being written right now" and
    "the archive is broken" look the same for a moment, and a page that made
    the campaign vanish would flicker it away on every save.
    """
    directory = self.directory(result_path)
    if not os.path.isdir(directory):
      return []

    campaigns = []
    with self._lock:
      for filename in sorted(os.listdir(directory)):
        if not filename.endswith((".yml", ".yaml")):
          continue
        path = os.path.join(directory, filename)
        try:
          stat = os.stat(path)
        except OSError:
          continue
        name = os.path.splitext(filename)[0]

        cached = self._cache.get(path)
        if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
          campaigns.append(cached[2])
          continue

        campaign = Campaign(name, path)
        self._cache[path] = (stat.st_mtime, stat.st_size, campaign)
        self._version += 1
        campaigns.append(campaign)
    return campaigns

  def get(self, result_path, name):
    """One campaign by name, or None."""
    for campaign in self.campaigns(result_path):
      if campaign.name == name:
        return campaign
    return None

  def signature(self, result_path):
    """
    What changes when an archive does.

    Compared by the page against what it drew last, so that an exploration
    that is running redraws and one that is not does not.
    """
    directory = self.directory(result_path)
    if not os.path.isdir(directory):
      return ()
    signature = []
    for filename in sorted(os.listdir(directory)):
      if not filename.endswith((".yml", ".yaml")):
        continue
      try:
        stat = os.stat(os.path.join(directory, filename))
      except OSError:
        continue
      signature.append((filename, stat.st_mtime, stat.st_size))
    return tuple(signature)


#: Process-wide singleton, shared by every callback.
CAMPAIGNS = CampaignStore()
