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
What a campaign evaluated, written as an ordinary Odatix results file.

The designs of an exploration are already in the results file of the tool that
ran them, mixed in with everything else the workspace ever ran. What is lost
there is that they were a search: which campaign asked for them, in which batch
it asked, and which of them ended up being the answer.

So the campaign writes its designs a second time, as a results source of their
own (``results_dse_<campaign>.yml``). It is a plain v2 results file -- the
explorer reads it like any other, charts it like any other -- with three
dimensions added to every record:

``dse``
    the campaign the design was evaluated by.
``dse_batch``
    which batch proposed it, so the search can be read in order.
``dse_front``
    ``yes`` for the designs nothing dominates: the answer of the campaign.

Which is what makes "plot area against frequency, colored by whether it is on
the front" an ordinary explorer chart rather than a feature.

Nothing here is a new result: the numbers are the ones the run measured, and
deleting these files loses the marking, not the results.
"""

import os

import odatix.lib.results_schema as results_schema
import odatix.lib.results_cache as results_cache
from odatix.dse.space import MAIN_DOMAIN

__all__ = ["results_file_name", "results_path_for", "export_results", "META_DSE",
           "META_BATCH", "META_FRONT", "META_FEASIBLE"]

#: The campaign a record was evaluated by.
META_DSE = "dse"
#: The batch of that campaign that proposed the design.
META_BATCH = "dse_batch"
#: Whether the design is on the Pareto front the campaign found.
META_FRONT = "dse_front"
#: Whether it meets the constraints the campaign declared, when it declared any.
META_FEASIBLE = "dse_feasible"

YES = "yes"
NO = "no"


def results_file_name(campaign):
  """The results file of a campaign, named so the explorer picks it up."""
  safe = "".join(character if character.isalnum() or character in "-_." else "_"
                 for character in str(campaign))
  return "results_dse_{0}.yml".format(safe)


def results_path_for(result_path, campaign):
  return os.path.join(result_path, results_file_name(campaign))


def _meta_of(evaluation):
  """
  What the record says the design is.

  The meta of the record the numbers were read from is the truth of what ran
  -- the type of run, the tool, the flow, the target, the parameter domains --
  so it is kept as it is and only added to. A design that produced no record
  at all has none, and is described from the design itself.
  """
  meta = dict(evaluation.source)
  design = evaluation.design

  meta.setdefault(results_schema.META_ARCHITECTURE, design.architecture)
  meta.setdefault(results_schema.META_CONFIGURATION, design.configuration)
  for domain, configuration in design.configurations.items():
    # A results record names the main domain "main", the way the schema
    # flattens the parameter domains of a run.
    key = results_schema.MAIN_DOMAIN_META_KEY if domain == MAIN_DOMAIN else domain
    meta.setdefault(key, configuration)
  if design.frequency is not None:
    meta.setdefault(results_schema.META_FREQUENCY, design.frequency)
  if design.toolchain is not None:
    meta.setdefault(results_schema.META_TOOL, design.toolchain.tool)
    if design.toolchain.flow:
      meta.setdefault(results_schema.META_FLOW, design.toolchain.flow)
    if design.toolchain.target:
      meta.setdefault(results_schema.META_TARGET, design.toolchain.target)
  return meta


def records_of(archive):
  """
  One record per design the campaign measured.

  A design that failed to build or that produced no number for an objective is
  left out: it has nothing to chart, and what became of it is in the archive,
  which is where a user goes to ask why a design is missing.
  """
  front = set(id(evaluation) for evaluation in archive.front())
  constrained = len(archive.objectives.constraints) > 0

  records = []
  for evaluation in archive.measured:
    meta = _meta_of(evaluation)
    meta[META_DSE] = archive.architecture
    meta[META_BATCH] = evaluation.batch
    meta[META_FRONT] = YES if id(evaluation) in front else NO
    if constrained:
      meta[META_FEASIBLE] = NO if archive.objectives.constraints.unmet(evaluation.metrics) else YES
    records.append(results_schema.make_record(meta, dict(evaluation.metrics)))
  return records


def export_results(archive, path, units=None):
  """
  Write the designs of a campaign as a results source of their own.

  The file is rewritten whole rather than merged into: which designs are on the
  front is a property of the campaign as it stands, and a design that a later
  batch pushed off the front has to stop being marked as being on it.

  Args:
      archive (Archive): the campaign to export.
      path (str): the results file to write.
      units (dict): metric units, as the results files of the tools declare
          them, so the charts label the axes the same way.

  Returns:
      str: the path written, or None when the campaign has measured nothing
      yet -- there is no point in an empty results source.
  """
  records = records_of(archive)
  if not records:
    return None
  results_cache.store(path, units or {}, records)
  return path
