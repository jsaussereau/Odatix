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
Write-back cache in front of the results files.

Every finished job exports its own results, and an incremental export used to
re-read and rewrite the whole results file each time: the cost of one export
grew with the number of results already in it, so a batch of N jobs paid O(N^2)
of YAML, and the seconds spent parsing showed up as a frozen job monitor.

This module removes both halves of that cost for the process that owns the
file:

  * the parse, by keeping the last (units, records) written or read in memory
    and handing it back as long as the file on disk still matches it;
  * most of the writes, by letting a caller declare a burst of exports
    (deferred_writes()) during which stores are only marked dirty, and the file
    is actually written at most every ``interval`` seconds -- plus once when
    the burst ends.

The cache is guarded by the file's (mtime, size): anything written behind its
back -- another process, a hand edit -- invalidates the entry and the next load
goes to disk. Deferring writes is therefore safe for correctness but does make
the file lag behind by up to ``interval`` for outside readers (Odatix Explorer
polls it while jobs run), so callers must flush before anything downstream
reads the file back.

Only one thread may store to a given path at a time: the cache holds a single
in-memory version of a file, and two writers would each build their update from
the same base and lose the other's.
"""

import os
import threading
import time

import odatix.lib.printc as printc
import odatix.lib.results_schema as results_schema

script_name = os.path.basename(__file__)

DEFAULT_FLUSH_INTERVAL_S = 2.0

_lock = threading.RLock()
_entries = {}
_local = threading.local()


class _Entry:
  """One cached results file: its content, what it looked like on disk, and whether it still has to be written."""

  __slots__ = ("units", "records", "stat", "dirty", "last_write")

  def __init__(self, units, records, stat):
    self.units = units
    self.records = records
    self.stat = stat
    self.dirty = False
    self.last_write = 0.0


def _stat_of(path):
  """(mtime_ns, size) of a file, or None if it does not exist."""
  try:
    info = os.stat(path)
  except OSError:
    return None
  return (info.st_mtime_ns, info.st_size)


def _key(path):
  return os.path.realpath(path)


def _deferral():
  """The deferral interval declared by the current thread, or None if it writes through."""
  return getattr(_local, "interval", None)


class deferred_writes(object):
  """
  Context manager: within it, stores made by *this* thread are coalesced.

  A store marks the file dirty and writes it only if ``interval`` seconds have
  passed since the last write; the caller decides when the burst is over by
  calling flush() (or flush_due() to keep coalescing). Leaving the context
  flushes what is still pending.
  """

  def __init__(self, interval=DEFAULT_FLUSH_INTERVAL_S):
    self.interval = interval
    self._previous = None

  def __enter__(self):
    self._previous = _deferral()
    _local.interval = self.interval
    return self

  def __exit__(self, exception_type, exception_value, traceback):
    _local.interval = self._previous
    flush()
    return False


def load(path):
  """
  Return (units, records) for a results file, from memory when possible.

  The returned objects are the cached ones: the caller is expected to store
  them back (possibly updated) and must not hand them to another writer.
  Missing or unparsable files come back empty, like a first export.
  """
  key = _key(path)
  with _lock:
    entry = _entries.get(key)
    if entry is not None and (entry.dirty or entry.stat == _stat_of(key)):
      return entry.units, entry.records

    stat = _stat_of(key)
    units, records = _read(key)
    _entries[key] = _Entry(units, records, stat)
    return units, records


def _read(path):
  """
  Read a results file of any supported format as (units, records).

  Older formats are auto-converted to v2 records, so the next write upgrades
  the file in place. A missing or unparsable file starts empty, like a first
  export: a results file is a by-product, never an input to protect.
  """
  if not os.path.isfile(path):
    return {}, []
  try:
    results_file = results_schema.load_results_file(path)
  except Exception:
    printc.warning('Could not parse existing results file "' + path + '", starting over', script_name=script_name)
    return {}, []
  return results_file.units, results_file.records


def store(path, units, records):
  """
  Publish (units, records) as the content of a results file.

  Written straight away, unless the calling thread is inside deferred_writes()
  and the previous write is too recent -- then the file is only marked dirty
  and a later flush()/flush_due() writes it.

  Raises:
      OSError: If an immediate write fails.
  """
  key = _key(path)
  with _lock:
    entry = _entries.get(key)
    if entry is None:
      entry = _Entry(units, records, None)
      _entries[key] = entry
    else:
      entry.units = units
      entry.records = records
    entry.dirty = True

    interval = _deferral()
    if interval is not None and (time.time() - entry.last_write) < interval:
      return
    _write(key, entry)


def _write(key, entry):
  """Write one entry to disk and record what the file now looks like. Caller holds the lock."""
  results_schema.dump_results_file(key, entry.units, entry.records)
  entry.dirty = False
  entry.last_write = time.time()
  entry.stat = _stat_of(key)


def flush(path=None):
  """
  Write every dirty entry (or only ``path``), whatever the deferral interval.

  Call it before anything outside this process reads the file back: the end of
  a batch, the end of a run, a hand-off to the explorer or to a search loop.

  Raises:
      OSError: If a write fails. Entries left dirty are retried on the next flush.
  """
  with _lock:
    keys = [_key(path)] if path is not None else list(_entries)
    for key in keys:
      entry = _entries.get(key)
      if entry is not None and entry.dirty:
        _write(key, entry)


def flush_due(path=None):
  """Write the dirty entries whose deferral interval has elapsed, and leave the others pending."""
  interval = _deferral()
  if interval is None:
    return flush(path)
  with _lock:
    keys = [_key(path)] if path is not None else list(_entries)
    now = time.time()
    for key in keys:
      entry = _entries.get(key)
      if entry is not None and entry.dirty and (now - entry.last_write) >= interval:
        _write(key, entry)


def invalidate(path=None):
  """
  Forget cached content, dropping anything not written yet.

  Only for a caller that knowingly replaces or removes a file outside of
  store() -- everyday staleness is already caught by the (mtime, size) guard.
  """
  with _lock:
    if path is None:
      _entries.clear()
    else:
      _entries.pop(_key(path), None)
