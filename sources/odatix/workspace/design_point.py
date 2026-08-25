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
Where a job sits in the design space of its architecture, written down by the
job itself.

A record already says which configuration of each parameter domain a job ran:
that is its name, and a name is all a hand-written configuration is. A
configuration a rule produced is more than that -- it stands for one value of
each variable of its domain -- and those values are what a search reasons
about. Recovering them afterwards means asking every point of every domain what
it would be called and hoping exactly one answers, which is guesswork over a
question the job had the answer to all along.

So the job writes it down. Every run does, not only an exploration: a sweep run
last month is a hundred points of the space already measured, and the only
thing that kept a search from starting there was that nobody had recorded where
they were.

What is written is the *coordinates* -- ``{axis: value}``, one entry per
variable -- and not the genome the search operates on. A genome is a tuple of
indices into the axes of one particular space, and the space a campaign
searches is not the one a plain synthesis knows: it pins domains a selection
fixed, adds an axis for the frequency and another for the toolchain, and
renumbers everything when the architecture gains a parameter. Coordinates
survive all of it, and turning them back into a genome is a lookup per axis
(see :meth:`odatix.dse.space.ArchitectureSpace.genome_of`), not an inference.
"""

import os
import re

import odatix.lib.hard_settings as hard_settings
import odatix.lib.results_schema as results_schema
from odatix.lib.config_generator import get_variables

__all__ = [
    "POINT_KEY",
    "POINT_META_PREFIX",
    "coordinates",
    "label_of",
    "point_of_meta",
]

#: Where the coordinates live in the ``param_domains.yml`` of a job directory,
#: and what they are called in the meta of a result record. The "_" prefix of
#: the meta keys keeps them out of the record identity, of the dimensions a
#: chart offers and of the joins derived metrics run on: they say where a
#: record is, not what it is.
POINT_KEY = results_schema.POINT_KEY
POINT_META_PREFIX = results_schema.POINT_META_PREFIX

MAIN_DOMAIN = hard_settings.main_parameter_domain

#: What each domain directory resolves to, kept for the length of a run: a
#: batch prepares hundreds of jobs and the domains they share are the same
#: files every time.
_resolved_cache = {}
_virtual_cache = {}


def label_of(domain, variable):
    """
    How one coordinate is named: ``variable`` in the main domain and in the
    variables of the commands, ``domain.variable`` anywhere else.

    The same spelling :class:`odatix.dse.space.SearchAxis` uses, so that a
    coordinate and an axis are named by the same string.
    """
    if not domain or domain == MAIN_DOMAIN:
        return str(variable)
    return "{0}.{1}".format(domain, variable)


def point_of_meta(meta):
    """The coordinates a record carries, as ``{axis: value}``."""
    if not isinstance(meta, dict):
        return {}
    found = {}
    for key, value in meta.items():
        key = str(key)
        if key.startswith(POINT_META_PREFIX):
            axis = key[len(POINT_META_PREFIX):]
            if axis:
                found[axis] = str(value)
    return found


def coordinates(arch_path, arch_name, param_domains=None, virtual_domains=None,
                main_param_file=None):
    """
    Where a job about to run sits in the design space of its architecture.

    Nothing here can make a run fail: a domain whose settings cannot be read,
    or a configuration whose rules no longer produce it, contributes no
    coordinate and the job goes on. A point that is not recorded is a result a
    search will not start from, which is exactly where things stood before.

    Args:
        arch_path (str): the directory the architectures live in.
        arch_name (str): what the job runs, as ``"<architecture>/<config>"`` or
            just ``"<architecture>"``.
        param_domains (list): the :class:`~odatix.lib.param_domain.ParamDomain`
            of the job, the main one excepted.
        virtual_domains (dict): ``{variable: value}``, the variables of the
            commands this job was expanded for.
        main_param_file (str): the configuration file of the main domain, when
            the job knows it. Where the main domain lives is read from it
            rather than guessed from ``arch_path``, which is what lets a
            workflow -- whose directories are laid out its own way -- record
            its coordinates like everything else.

    Returns:
        dict: ``{axis: value}``, empty when nothing could be read.
    """
    found = {}
    architecture = re.sub("/.*", "", str(arch_name or ""))
    configuration = re.sub(".*/", "", str(arch_name or ""))
    if not architecture:
        return found

    main_path = (
        os.path.dirname(str(main_param_file)) if main_param_file
        else os.path.join(str(arch_path or ""), architecture)
    )
    if configuration and configuration != architecture:
        found.update(_domain_values(main_path, MAIN_DOMAIN, configuration))

    for param_domain in param_domains or []:
        name = str(getattr(param_domain, "domain", "") or "")
        value = str(getattr(param_domain, "domain_value", "") or "")
        if not name or not value:
            continue
        param_file = getattr(param_domain, "param_file", None)
        path = os.path.dirname(str(param_file)) if param_file else os.path.join(
            str(arch_path or ""), architecture, name
        )
        found.update(_domain_values(path, name, value))

    found.update(_virtual_values(main_path, virtual_domains))
    return found


def _domain_values(path, domain, configuration):
    """
    What the variables of one domain are worth in one of its configurations.

    A configuration written by hand has none -- its name is everything it says,
    and the name is already in the record.
    """
    values = _resolved(path).get(str(configuration))
    if not values:
        return {}
    return {label_of(domain, name): str(value) for name, value in values.items()}


def _resolved(path):
    """``{configuration: {variable: value}}`` for one domain directory."""
    path = os.path.realpath(path) if path else ""
    if path in _resolved_cache:
        return _resolved_cache[path]

    found = {}
    if path and os.path.isdir(path):
        try:
            from odatix.workspace.space import config_set_at

            for config in config_set_at(path).resolve():
                if config.values:
                    found[str(config.name)] = dict(config.values)
        except Exception:
            found = {}
    _resolved_cache[path] = found
    return found


def _virtual_values(path, virtual_domains):
    """
    What the variables of the commands are worth, as the space spells them.

    The job knows them the way its directory is named -- sanitized, with the
    unit of the variable appended -- and a search knows them as the values its
    rules produced. They are matched here, once per architecture, so that a
    coordinate is the value and not its rendering.
    """
    wanted = {
        str(name): str(value)
        for name, value in (virtual_domains or {}).items()
        if str(value) != ""
    }
    if not wanted:
        return {}

    variants = _virtual_variants(path)
    if variants is None:
        # Nothing could be built from the settings: the rendering is the best
        # the job can say about itself, and it is what its directory is called.
        return {label_of("", name): value for name, value in wanted.items()}

    for rendered, values in variants:
        if all(rendered.get(name) == value for name, value in wanted.items()):
            return {label_of("", name): str(value) for name, value in values.items()}
    return {label_of("", name): value for name, value in wanted.items()}


def _virtual_variants(path):
    """
    Every point of the variables of one architecture, as ``(rendered, values)``.

    Built from the very same :class:`~odatix.dse.space.VirtualDomainSpace` a
    search reads, so that the values recorded are the ones its axes hold.
    Returns None when the architecture declares no such variables, or when its
    settings cannot be read.
    """
    import itertools

    path = os.path.realpath(path) if path else ""
    if path in _virtual_cache:
        return _virtual_cache[path]

    variants = None
    try:
        from odatix.dse.space import VirtualDomainSpace
        from odatix.workspace.space import load_domain_settings

        settings = load_domain_settings(path) or {}
        variables, _legacy = get_variables(settings)
        if variables:
            space = VirtualDomainSpace(variables, source=path)
            if space.axes:
                variants = []
                for choice in itertools.product(*[range(len(axis)) for axis in space.axes]):
                    rendered, values, _contents = space.resolve(choice)
                    if rendered is None:
                        continue
                    variants.append((rendered, values))
    except Exception:
        variants = None

    _virtual_cache[path] = variants
    return variants
