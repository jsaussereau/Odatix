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
The design space of a parameter domain.

A domain describes its configurations with *rules* -- a set of variables, a
name and, when it substitutes text into the design, a template::

    configurations:
      name: "${width}bits"
      template: "parameter WIDTH = ${width};"

    variables:
      width:
        type: range
        settings: {from: 8, to: 64, step: 8}

Those rules do not have to be turned into files before a run: a
:class:`ConfigSet` resolves them on demand, which is what lets a run
materialize only the configurations it evaluates. Writing them out with
"odatix generate" stays possible, and is the only thing that ever creates a
manifest (see :class:`Manifest`).

Configurations can also be written by hand, one ".txt" file per configuration,
the way they always could. The two live together: a hand-written file whose
name a rule also produces replaces what the rule would have produced, which is
how a single configuration is corrected without giving up the rules.
"""

import hashlib
import os

from natsort import natsorted

import odatix.lib.printc as printc
from odatix.lib.config_generator import (
    ConfigGenerator,
    duplicate_point_names,
    get_variables,
    parse_constraints,
    parse_rule_sets,
    rule_set_variables,
)
from odatix.workspace.errors import WorkspaceError

__all__ = [
    "ORIGIN_GENERATED",
    "ORIGIN_EDITED",
    "ORIGIN_MANUAL",
    "ORIGIN_BLACKLISTED",
    "ORIGINS",
    "DuplicateNameError",
    "ResolvedConfig",
    "Manifest",
    "Axis",
    "ParameterSpace",
    "ConfigSet",
    "config_set_rules",
    "implicit_template",
    "implicit_config_name",
    "config_set_at",
    "is_sub_domain",
    "config_file",
    "selected_config_file",
    "resolved_names",
    "load_domain_settings",
    "CONFIG_EXTENSION",
    "CACHE_DIRNAME",
]

#: Extension of a configuration file. Kept here too so this module does not
#: have to import the collection it is meant to feed.
CONFIG_EXTENSION = ".txt"

#: Where a configuration resolved during a run is written, inside the directory
#: of the domain. Nothing a user writes ever lands there, and deleting it only
#: means the next run resolves the same configurations again.
CACHE_DIRNAME = ".odatix_configs"

#: Produced by the rules, and not written to disk (or written exactly as the
#: rules produce it).
ORIGIN_GENERATED = "generated"

#: Produced by the rules, but the file on disk says something else: the file
#: wins, and regenerating leaves it alone.
ORIGIN_EDITED = "edited"

#: A file the rules know nothing about. A domain without rules holds only
#: these, which is what every workspace written before all this holds.
ORIGIN_MANUAL = "manual"

# Produced by the rules but explicitly excluded from the domain's runnable
# configurations. It is retained for the editor so it can be restored.
ORIGIN_BLACKLISTED = "blacklisted"

ORIGINS = (ORIGIN_GENERATED, ORIGIN_EDITED, ORIGIN_MANUAL, ORIGIN_BLACKLISTED)


class DuplicateNameError(WorkspaceError):
    """
    Several points of a space are named the same.

    A configuration is known by its name everywhere else in Odatix, so points
    sharing one cannot be told apart: all but one would quietly vanish from the
    sweep. The name template has to tell them apart instead.
    """


def content_hash(content):
    """
    The fingerprint of the content of a configuration, as the manifest records
    it.

    Line endings are normalized, because an editor rewriting them is not the
    user changing the parameters.
    """
    text = "" if content is None else str(content)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


######################################
# A resolved configuration
######################################

class ResolvedConfig(object):
    """
    One configuration of a domain, whatever it came from.

    This is what the rest of Odatix works with: a name, the text substituted
    into the design, and -- when a rule produced it -- the values its variables
    were assigned, which is what a search needs to reason about the point
    rather than about its name.
    """

    __slots__ = ("name", "content", "values", "origin", "generated_content")

    def __init__(self, name, content, values=None, origin=ORIGIN_MANUAL, generated_content=None):
        self.name = str(name)
        #: What this configuration holds: the file when there is one, otherwise
        #: what the rules render.
        self.content = "" if content is None else str(content)
        self.values = dict(values) if values else {}
        self.origin = origin
        #: What the rules render, kept apart from :attr:`content` so that an
        #: edited configuration can be taken back to its rule. None when no
        #: rule produces this configuration.
        self.generated_content = generated_content

    @property
    def filename(self):
        return self.name + CONFIG_EXTENSION

    @property
    def from_rules(self):
        """Whether the rules of the domain produce this configuration."""
        return self.origin in (ORIGIN_GENERATED, ORIGIN_EDITED)

    def __repr__(self):
        return "<ResolvedConfig {0!r} ({1})>".format(self.name, self.origin)

    def __eq__(self, other):
        if not isinstance(other, ResolvedConfig):
            return NotImplemented
        return (
            self.name == other.name
            and self.content == other.content
            and self.values == other.values
            and self.origin == other.origin
        )

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result


######################################
# Manifest
######################################

class Manifest(object):
    """
    What "odatix generate" wrote in a domain, and what it looked like.

    Its only job is to keep a later generation from overwriting a
    configuration that was edited by hand since. It is therefore written by
    "odatix generate" and by nothing else: a workspace whose configurations are
    written by hand, or whose rules are resolved on the fly, never has one, and
    nothing about it has to be known to use Odatix.

    Deleting it is always safe. Without it every file simply counts as
    hand-written, which is the careful reading: nothing is ever regenerated
    over something the user may have written.
    """

    #: Name of the manifest file, inside the directory of the domain.
    FILENAME = ".odatix_generated.yml"

    HEADER = (
        "# Written by \"odatix generate\": the configurations it generated, and what they\n"
        "# looked like. It is what keeps a later \"odatix generate\" from overwriting a\n"
        "# configuration you edited by hand.\n"
        "#\n"
        "# You never have to write or read this file. Deleting it is safe: every\n"
        "# configuration is then treated as hand-written, and none is ever regenerated\n"
        "# over your changes.\n"
    )

    VERSION = 1

    def __init__(self, path):
        #: Directory of the domain.
        self.path = path
        #: ``{configuration name: fingerprint}``.
        self.generated = {}
        self.load()

    @property
    def file(self):
        return os.path.join(self.path, self.FILENAME)

    @property
    def exists(self):
        return os.path.isfile(self.file)

    def load(self):
        """Read the manifest, leaving it empty when there is none to read."""
        self.generated = {}
        if not self.exists:
            return self
        try:
            import yaml

            with open(self.file, "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            printc.warning(
                "Ignoring unreadable generation manifest \"{0}\": {1}".format(self.file, e),
                script_name=os.path.basename(__file__),
            )
            return self

        if isinstance(data, dict) and isinstance(data.get("generated"), dict):
            self.generated = {str(name): str(digest) for name, digest in data["generated"].items()}
        return self

    def save(self):
        """
        Write the manifest, or remove it when there is nothing left to record --
        an empty manifest would only be a file to wonder about.
        """
        if not self.generated:
            return self.delete()

        os.makedirs(self.path, exist_ok=True)
        lines = [self.HEADER, "version: {0}\n".format(self.VERSION), "generated:\n"]
        for name in natsorted(self.generated):
            lines.append("  {0}: {1}\n".format(name, self.generated[name]))
        with open(self.file, "w") as f:
            f.write("".join(lines))
        return self

    def delete(self):
        if self.exists:
            os.remove(self.file)
        self.generated = {}
        return self

    def record(self, name, content):
        self.generated[str(name)] = content_hash(content)
        return self

    def forget(self, name):
        self.generated.pop(str(name), None)
        return self

    def knows(self, name):
        return str(name) in self.generated

    def matches(self, name, content):
        """Whether a file still holds what the generation wrote in it."""
        digest = self.generated.get(str(name))
        return digest is not None and digest == content_hash(content)

    def __repr__(self):
        return "<Manifest {0} ({1} generated)>".format(self.path, len(self.generated))


######################################
# Parameter space
######################################

class Axis(object):
    """
    One free choice of a parameter space.

    Usually one variable and the values it takes. Variables declared with the
    same ``group`` share an axis instead of having one each: they are chosen
    together, position by position, so a "couple" of parameters stays paired
    whichever way the space is explored. An axis is therefore a list of rows,
    each row an assignment of the variables it holds.
    """

    __slots__ = ("variables", "rows")

    def __init__(self, variables, rows):
        self.variables = [str(name) for name in variables]
        self.rows = [dict(row) for row in rows]

    @property
    def label(self):
        """How the axis is named to a user: its variables, paired ones joined."""
        return " + ".join(self.variables)

    def values_of(self, variable):
        """The values one variable of this axis takes, in order."""
        return [row[variable] for row in self.rows if variable in row]

    def __len__(self):
        return len(self.rows)

    def __repr__(self):
        return "<Axis {0} ({1} values)>".format(self.label, len(self.rows))


class ParameterSpace(object):
    """
    The variables of a domain, and the points they stand for.

    The rules are interpreted by :class:`ConfigGenerator`, which is where every
    variable type lives: the dimensions ("range", "list", "power_of_two",
    "multiples", "bool"), the set operations between them, the derived values
    ("function", "format", "conversion"), the pairing of variables by "group"
    and the formatting of each value.

    What this adds is a way in: the points can be enumerated, or picked one by
    one from an assignment of the variables, which is what tells an exhaustive
    sweep and a search apart.
    """

    def __init__(self, variables, name="", template=None, source="", debug=False,
                 implicit_name=False, implicit_template=False, blacklist=(),
                 constraints=(), rule_sets=()):
        #: ``{variable name: declaration}``, as written in the settings file.
        self.variables = dict(variables) if variables else {}
        #: Template the name of a configuration is built from.
        self.name = name or ""
        #: Template the content is built from, or None for a domain that
        #: substitutes into commands rather than into the design.
        self.template = template
        #: Whether that name/template is what the file says, or what a domain
        #: of a single variable means without saying it (see
        #: :func:`implicit_template`). An editor shows an implicit one as a
        #: suggestion rather than as text the user wrote.
        self.implicit_name = implicit_name
        self.implicit_template = implicit_template
        #: Names the rules produce but that this domain does not run.
        self.blacklist = frozenset(str(name) for name in (blacklist or ()))
        #: Boolean expressions over the variables a point has to satisfy. A
        #: point that does not is not part of the space at all -- unlike a
        #: blacklisted one, which exists but is not run.
        #: Normalized as ``[(expression, message), ...]``, whichever of the
        #: two forms they were written in.
        self.constraints = parse_constraints({"constraints": list(constraints or ())})
        #: The rule sets, when the domain declares several: a list of blocks,
        #: each with its own name, template and constraints. What they describe
        #: is the **union** of what each produces -- nothing is combined across
        #: them, which is what a parameter deciding which other parameters mean
        #: anything asks for. Empty when a single set of rules is declared, and
        #: then :attr:`name` and :attr:`template` are the rules.
        self.rule_sets = [dict(block) for block in (rule_sets or ())]
        #: Where this came from, for error messages.
        self.source = source
        self.debug = debug
        self._generator = None
        self._generated = None

    @property
    def is_empty(self):
        return not self.variables

    @property
    def generates(self):
        """Whether these rules produce configurations at all."""
        return bool(self.variables) and bool(self.name or self.rule_sets)

    @property
    def generator(self):
        """
        The engine behind the rules.

        It is fed the form it has always read, so that every variable type keeps
        being interpreted by the one implementation there has ever been.
        """
        if self._generator is None:
            if self.rule_sets:
                blocks = []
                for block in self.rule_sets:
                    template = block.get("template", "")
                    if isinstance(template, list):
                        template = "\n".join(str(line) for line in template)
                    rules = {
                        "name": str(block.get("name", "") or ""),
                        "template": template if template is not None else "",
                    }
                    constraints = parse_constraints(block)
                    if constraints:
                        rules["constraints"] = [
                            {"expr": expression, "message": message}
                            for expression, message in constraints
                        ]
                    declared = block.get("variables")
                    if isinstance(declared, (list, tuple, dict)):
                        rules["variables"] = list(declared)
                    blocks.append(rules)
                data = {CONFIGURATIONS_KEY: blocks, "variables": self.variables}
                self._generator = ConfigGenerator(data=data, silent=True, debug=self.debug)
                return self._generator
            data = {
                CONFIGURATIONS_KEY: {
                    "template": self.template if self.template is not None else "",
                    "name": self.name,
                },
                "variables": self.variables,
            }
            if self.constraints:
                data[CONFIGURATIONS_KEY]["constraints"] = [
                    {"expr": expression, "message": message}
                    for expression, message in self.constraints
                ]
            self._generator = ConfigGenerator(data=data, silent=True, debug=self.debug)
        return self._generator

    @property
    def valid(self):
        return self.generates and self.generator.valid

    def _generate(self):
        """
        The points and values the rules produce, generated once.

        Expanding a space is the expensive part of reading one, and the two
        halves of the answer are asked for separately (`points` and `values`,
        often both, sometimes several times over). The rules a space was built
        from never change after it is built -- same reason `generator` is kept
        -- so the expansion is kept too.
        """
        if self._generated is None:
            if not self.valid:
                self._generated = ([], {})
            else:
                points, values = self.generator.generate_points()
                self._generated = (points, values)
        return self._generated

    def _generated_points(self):
        """Every point the rules produce before their configuration blacklist."""
        return self._generate()[0]

    def points(self):
        """
        Every point of the space, in generation order.

        Raises:
            DuplicateNameError: when the name template gives two points the
                same name.
        """
        points = [point for point in self._generated_points() if point.name not in self.blacklist]
        self._reject_duplicates(points)
        return points

    def blacklisted_points(self):
        """The points hidden by this domain's configuration blacklist."""
        return [point for point in self._generated_points() if point.name in self.blacklist]

    def point(self, assignment):
        """
        The single point an assignment of the variables stands for, without
        enumerating anything else.

        This is what a search calls: it chooses the values, and gets back the
        configuration they name and the text they render into.

        Args:
            assignment (dict): the value of each dimension variable.
        """
        if not self.valid:
            return None
        point = self.generator.derive_point(assignment)
        return None if point is not None and point.name in self.blacklist else point

    def axes(self):
        """
        What a point of this space is free to choose, and what it may choose
        there (see :meth:`ConfigGenerator.dimensions`).

        An axis is a *group* of variables rather than a single one, because
        variables declared with the same ``group`` move together. Choosing one
        row per axis is choosing a point, and taking every combination of the
        axes is exactly what :meth:`points` enumerates -- which is what makes an
        exhaustive sweep one search strategy among others rather than a
        different mechanism.

        Returns:
            list: the :class:`Axis` of the space, in declaration order. Empty
            when the rules describe no space.
        """
        if not self.valid:
            return []
        return [Axis(axis["variables"], axis["rows"]) for axis in self.generator.dimensions()]

    def subspaces(self):
        """
        The spaces this one is the union of.

        A domain declaring several rule sets is not one space but several, laid
        side by side: a choice on the axes of one means nothing in another, so
        there is no single set of axes to offer. Anything that explores rather
        than enumerates works on the subspaces -- each of them has axes, points
        and a size of its own -- and what it finds belongs to the union all the
        same.

        Returns:
            list: the :class:`ParameterSpace` of each rule set, or ``[self]``
            when a single set of rules is declared.
        """
        if not self.rule_sets:
            return [self]
        subspaces = []
        for block in self.rule_sets:
            template = block.get("template", None)
            if isinstance(template, list):
                template = "\n".join(str(line) for line in template)
            # The same subset the engine hands that rule set: the variables
            # its rules use, and nothing else -- a variable another rule set is
            # about must not become an axis here.
            variables = rule_set_variables(block, self.variables)
            subspaces.append(
                ParameterSpace(
                    variables,
                    name=str(block.get("name", "") or ""),
                    template=template,
                    source=self.source,
                    debug=self.debug,
                    blacklist=self.blacklist,
                    constraints=parse_constraints(block),
                )
            )
        return subspaces

    def size(self):
        """
        How many points the axes stand for, counted rather than enumerated.

        This is what a budget is compared against: a space of ten million
        points is counted in the time it takes to multiply a few numbers, and
        that number is precisely the reason not to sweep it.

        Constraints are not applied here -- they are known only once a point is
        assembled -- so this is an upper bound as soon as there is one. What
        the space really holds is :meth:`count`, which enumerates.
        """
        if self.rule_sets:
            # Side by side, not combined: the union holds as many points as its
            # subspaces hold together.
            return sum(subspace.size() for subspace in self.subspaces())
        total = 1
        for axis in self.axes():
            total *= len(axis)
        return total

    def assignment(self, choice):
        """
        The assignment a choice of one row per axis stands for.

        Args:
            choice (sequence): the index of the chosen row on each axis, in the
                order :meth:`axes` returns them.

        Returns:
            dict: the value of each dimension variable, ready for :meth:`point`.
        """
        assignment = {}
        for axis, index in zip(self.axes(), choice):
            assignment.update(axis.rows[index % len(axis)])
        return assignment

    def values(self):
        """
        ``{variable: [value, ...]}``, the values each variable takes -- what a
        preview shows, and what a search samples from.
        """
        return self._generate()[1]

    def count(self):
        """How many points the space holds."""
        return len(self.points())

    def _reject_duplicates(self, points):
        duplicates = duplicate_point_names(points)
        if not duplicates:
            return
        name, assignments = natsorted(duplicates)[0], None
        assignments = duplicates[name]
        detail = " and ".join(
            "{" + ", ".join("{0}: {1}".format(k, v) for k, v in sorted(values.items())) + "}"
            for values in assignments[:2]
        )
        where = " in \"{0}\"".format(self.source) if self.source else ""
        raise DuplicateNameError(
            "The name \"{0}\" is given to {1} configurations{2}: {3}. "
            "Every configuration needs its own name, so \"{4}\" has to tell them apart -- "
            "it is missing a variable.".format(
                name, len(assignments), where, detail, self.name,
            )
        )


######################################
# Config set
######################################

class ConfigSet(object):
    """
    Everything a parameter domain resolves to: what its rules produce, and what
    is written in its directory.

    Resolving costs nothing but the combinations of *this* domain -- never the
    cross product of the whole instance -- so a run can ask what a domain holds
    without anything having been generated first.
    """

    def __init__(self, path, space=None, debug=False):
        #: Directory of the domain. May not exist.
        self.path = path
        #: The rules, empty for a domain holding only hand-written files.
        self.space = space if space is not None else ParameterSpace({}, source=path)
        self.debug = debug

    ######################################
    # What is on disk
    ######################################

    @property
    def manifest(self):
        return Manifest(self.path)

    def files(self):
        """``{name: content}`` of the configuration files of the domain."""
        found = {}
        if not self.path or not os.path.isdir(self.path):
            return found
        for entry in os.listdir(self.path):
            if not entry.endswith(CONFIG_EXTENSION):
                continue
            full = os.path.join(self.path, entry)
            if not os.path.isfile(full):
                continue
            with open(full, "r") as f:
                found[entry[:-len(CONFIG_EXTENSION)]] = f.read()
        return found

    ######################################
    # Resolution
    ######################################

    def resolve(self):
        """
        The configurations of this domain, in natural order.

        A file replaces what the rules produce under the same name, so
        correcting one configuration by hand never means giving up the rules.
        A file the rules do not produce is a configuration of its own. And a
        leftover from an earlier generation -- recorded in the manifest,
        untouched since, no longer produced -- is not part of the space any
        more, so it is left out.
        """
        files = self.files()
        manifest = self.manifest
        generated = {}
        if self.space.generates:
            for point in self.space.points():
                generated[point.name] = point
        blacklisted = {point.name: point for point in self.space.blacklisted_points()}

        resolved = {}

        for name, point in generated.items():
            if name in files and files[name] != point.content:
                resolved[name] = ResolvedConfig(
                    name, files[name], point.values, ORIGIN_EDITED, generated_content=point.content,
                )
            else:
                resolved[name] = ResolvedConfig(
                    name, point.content, point.values, ORIGIN_GENERATED, generated_content=point.content,
                )

        for name, content in files.items():
            if name in resolved:
                continue
            if name in blacklisted and content == blacklisted[name].content:
                # This is the generated configuration the blacklist names,
                # whether it was materialized with a manifest or written before
                # one existed. A changed file still remains a manual override.
                continue
            if manifest.knows(name) and manifest.matches(name, content):
                # Written by an earlier generation and untouched since, but the
                # rules no longer produce it: a leftover, not a configuration.
                continue
            resolved[name] = ResolvedConfig(name, content, None, ORIGIN_MANUAL)

        return [resolved[name] for name in natsorted(resolved)]

    def blacklisted(self):
        """Rule-produced configurations excluded from runs, kept for the editor."""
        if not self.space.blacklist:
            return []

        files = self.files()
        resolved = {}
        for point in self.space.blacklisted_points():
            # A hand-written file remains a configuration of its own. A file
            # equal to the generated content stays excluded and can still be
            # restored from the editor, even when no manifest exists.
            if point.name in files and files[point.name] != point.content:
                continue
            resolved[point.name] = ResolvedConfig(
                point.name, point.content, point.values, ORIGIN_BLACKLISTED,
                generated_content=point.content,
            )
        return [resolved[name] for name in natsorted(resolved)]

    def resolve_point(self, assignment):
        """
        The configuration a given assignment of the variables stands for,
        without resolving the rest of the space.

        A file of the same name still wins, so a hand-written correction is
        honoured whichever way the point was reached.
        """
        point = self.space.point(assignment)
        if point is None:
            return None
        files = self.files()
        if point.name in files and files[point.name] != point.content:
            return ResolvedConfig(
                point.name, files[point.name], point.values, ORIGIN_EDITED, generated_content=point.content,
            )
        return ResolvedConfig(
            point.name, point.content, point.values, ORIGIN_GENERATED, generated_content=point.content,
        )

    def names(self):
        """The names of the configurations, in natural order."""
        return [config.name for config in self.resolve()]

    def count(self):
        """
        How many configurations this domain holds, without rendering any of
        them.
        """
        return len(self.resolve())

    def leftovers(self):
        """
        The names of the files an earlier generation wrote, that its rules no
        longer produce and that nobody has edited since -- what "--clean"
        removes, and nothing else.
        """
        manifest = self.manifest
        if not manifest.generated:
            return []
        produced = set(name for name in self._generated_names())
        return natsorted([
            name
            for name, content in self.files().items()
            if name not in produced and manifest.knows(name) and manifest.matches(name, content)
        ])

    def _generated_names(self):
        if not self.space.generates:
            return []
        return [point.name for point in self.space.points()]

    ######################################
    # Materialization
    ######################################

    def materialize(self, directory=None, overwrite=False, clear=False, prune=False):
        """
        Write the configurations to disk.

        A run materializes into the work directory of its job, which is where
        the configurations are needed and where they belong. "odatix generate"
        materializes into the directory of the domain, which is the only thing
        that ever writes a manifest there.

        Args:
            directory (str): where to write. The directory of the domain by
                default, which is the case that records a manifest.
            overwrite (bool): replace a configuration whose file was edited.
                Without it, edited configurations are left as they are.
            clear (bool): delete every configuration file first.
            prune (bool): delete the leftovers of an earlier generation --
                never a file that was written by hand or edited since.

        Returns:
            list: the names written, in natural order.
        """
        target = directory or self.path
        into_domain = os.path.abspath(target) == os.path.abspath(self.path)

        os.makedirs(target, exist_ok=True)
        manifest = self.manifest if into_domain else None

        if clear:
            for entry in os.listdir(target):
                if entry.endswith(CONFIG_EXTENSION):
                    os.remove(os.path.join(target, entry))
            if manifest is not None:
                manifest.generated = {}
        elif prune and manifest is not None:
            for name in self.leftovers():
                os.remove(os.path.join(target, name + CONFIG_EXTENSION))
                manifest.forget(name)

        written = []
        for config in self.resolve():
            content = config.content

            if config.origin == ORIGIN_MANUAL and into_domain:
                # Already on disk, and nothing generated it: nothing to write.
                continue
            if config.origin == ORIGIN_EDITED and into_domain:
                if not overwrite:
                    # The user edited it. Regenerating over it is exactly what
                    # the manifest exists to prevent.
                    continue
                # Asked for explicitly: take the configuration back to what its
                # rule says, dropping the edit.
                content = config.generated_content

            path = os.path.join(target, config.filename)
            with open(path, "w") as f:
                f.write(content)
            written.append(config.name)

            if manifest is not None and config.from_rules:
                manifest.record(config.name, content)

        if manifest is not None:
            manifest.save()

        return natsorted(written)

    def file_of(self, name):
        """
        The path of the file holding one configuration, written on the way when
        only a rule describes it.

        This is what makes generation stop being a step to run beforehand: a job
        asks for the configuration it is about to run, and gets a file whether it
        was written by hand, generated earlier, or resolved just now.

        A configuration that exists as a file in the domain is used as it is --
        the file always wins, so a hand-written correction is honoured. Anything
        resolved on the fly is written under :data:`CACHE_DIRNAME` instead of in
        the domain, so a run never adds files to what the user keeps.

        Returns:
            str: path of the file, or None when the domain has no such
            configuration.
        """
        name = str(name)
        direct = os.path.join(self.path, name + CONFIG_EXTENSION)
        if os.path.isfile(direct):
            return direct

        if not self.space.generates:
            return None

        point = None
        for candidate in self.space.points():
            if candidate.name == name:
                point = candidate
                break
        if point is None:
            return None

        cache = os.path.join(self.path, CACHE_DIRNAME)
        path = os.path.join(cache, name + CONFIG_EXTENSION)
        if os.path.isfile(path):
            with open(path, "r") as f:
                if f.read() == point.content:
                    return path

        os.makedirs(cache, exist_ok=True)
        with open(path, "w") as f:
            f.write(point.content)
        return path

    def __repr__(self):
        return "<ConfigSet {0} ({1} configurations)>".format(self.path, len(self.resolve()))


######################################
# Reading the rules out of a settings file
######################################

#: Where the rules are declared.
CONFIGURATIONS_KEY = "configurations"

#: Where they used to be, together with the flag that used to turn them on.
LEGACY_SETTINGS_KEY = "generate_configurations_settings"
LEGACY_ENABLE_KEY = "generate_configurations"


def _variable_names(variables):
    """The variables a domain declares, in the order it declares them."""
    return [str(name) for name in (variables or {}) if str(name).strip()]


def implicit_template(variables):
    """
    What a domain means without writing its content template down: its values,
    one per line, in the order the variables are declared::

        variables:
          width:
            type: range
            settings: {from: 4, to: 12, step: 4}

    writes "${width}" between its delimiters, and saying so adds nothing. A
    domain of several variables writes one value per line, which is what a list
    of parameters looks like -- anything else (a "parameter X = ..." around each
    value, say) still has to be written out.

    Returns:
        str: the template, or None when the domain declares no variable.
    """
    names = _variable_names(variables)
    if not names:
        return None
    return "\n".join("${" + name + "}" for name in names)


def implicit_config_name(variables):
    """
    What a domain means without writing its name template down: its values,
    joined by an underscore, in the order the variables are declared -- the name
    of a configuration says what it is.

    Returns:
        str: the template, or None when the domain declares no variable.
    """
    names = _variable_names(variables)
    if not names:
        return None
    return "_".join("${" + name + "}" for name in names)


def config_set_rules(settings, source="", implicit=False):
    """
    The rules a settings file declares, whichever way it declares them.

    Odatix has described the same thing three ways, and all three keep working:

    - ``configurations: {name, template}`` with ``variables`` at the root, the
      form written from now on;
    - ``generate_configurations: Yes`` with
      ``generate_configurations_settings: {name, template}``, the form that
      used to turn generation on;
    - ``variables`` alone, which stands for a domain substituting into
      commands rather than into the design, and therefore has no template.

    Reading them here, rather than at each place that needs them, is what lets
    the flag disappear from the settings without any file having to be
    rewritten.

    Args:
        settings (dict): content of a settings file.
        source (str): path of that file, for error messages.

    Returns:
        ParameterSpace: the rules, empty when the file declares none.
    """
    if not isinstance(settings, dict):
        return ParameterSpace({}, source=source)

    variables, _legacy = get_variables(settings)

    def space_of(rules):
        template = rules.get("template", None)
        if isinstance(template, list):
            template = "\n".join(str(line) for line in template)
        blacklist = rules.get("blacklist", ())
        if not isinstance(blacklist, (list, tuple, set)):
            blacklist = ()
        return declared(
            str(rules.get("name", "") or ""), template, written=True,
            blacklist=blacklist, constraints=parse_constraints(rules),
        )

    def declared(name, template, written=False, blacklist=(), constraints=()):
        """
        The rules, with what a domain leaves unsaid filled in.

        Half-written rules are filled in whatever the domain: a domain that
        names its configurations describes them, so the half it left out is the
        obvious one -- its values -- even where a bare ``variables`` block would
        have meant nothing.
        """
        fill = implicit or written
        default_name = implicit_config_name(variables) if fill else None
        default_template = implicit_template(variables) if fill else None
        implied_name = default_name is not None and not name
        implied_template = default_template is not None and not template
        return ParameterSpace(
            variables,
            name=default_name if implied_name else name,
            template=default_template if implied_template else template,
            source=source,
            implicit_name=implied_name,
            implicit_template=implied_template,
            blacklist=blacklist,
            constraints=constraints,
        )

    rules = settings.get(CONFIGURATIONS_KEY)

    # Several rule sets: their points are the union of what each produces.
    blocks = parse_rule_sets(rules)
    if blocks:
        blacklist = []
        for block in blocks:
            declared = block.get("blacklist", ())
            if isinstance(declared, (list, tuple, set)):
                blacklist.extend(declared)
        return ParameterSpace(
            variables,
            source=source,
            blacklist=blacklist,
            rule_sets=blocks,
        )

    # Settings objects always carry an empty block, so its mere presence cannot
    # decide. The editor writes ``enabled`` only when an empty block explicitly
    # means the defaults of its variables.
    if isinstance(rules, dict) and (
        rules.get("enabled")
        or rules.get("name")
        or rules.get("template")
        or (implicit and (rules.get("blacklist") or rules.get("constraints")))
    ):
        return space_of(rules)

    legacy = settings.get(LEGACY_SETTINGS_KEY)
    if bool(settings.get(LEGACY_ENABLE_KEY, False)) and isinstance(legacy, dict):
        return space_of(legacy)

    # Variables without a template. In a parameter domain of a single variable
    # that says everything already: the configurations are named after its
    # values and hold them. Anywhere else -- a domain whose values are
    # substituted into commands, or several variables to combine -- nothing is
    # implied, and the rules describe nothing until they are written.
    return declared("", None)


######################################
# Reading a domain directly from disk
######################################

#: What a settings file is called, repeated here so that reading a domain does
#: not drag the whole workspace package into the run flows.
SETTINGS_FILENAME = "_settings.yml"


def load_domain_settings(path):
    """
    The settings a domain directory holds, as a plain dict ({} when there are
    none to read, or when they cannot be read).
    """
    settings_file = os.path.join(path, SETTINGS_FILENAME)
    if not os.path.isfile(settings_file):
        return {}
    try:
        import yaml

        with open(settings_file, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        printc.warning(
            "Ignoring unreadable settings file \"{0}\": {1}".format(settings_file, e),
            script_name=os.path.basename(__file__),
        )
        return {}
    return data if isinstance(data, dict) else {}


def is_sub_domain(path):
    """
    Whether a directory is a named parameter domain of an instance, rather than
    the instance itself: its parent holds a settings file too.

    It is what tells the variables of a file what they are for. In a named
    domain they can only describe its configurations, so a single one describes
    them on its own (see :func:`implicit_template`). At the root of an
    architecture or of a workflow the same variables may instead be substituted
    into its commands -- a virtual parameter domain -- so nothing is implied
    there, and the rules say what they mean.
    """
    parent = os.path.dirname(os.path.abspath(path))
    return os.path.isfile(os.path.join(parent, SETTINGS_FILENAME))


def config_set_at(path, settings=None, debug=False, implicit=None):
    """
    The :class:`ConfigSet` of a domain directory, reading its settings file when
    they are not handed over.

    Args:
        implicit (bool): whether a single variable describes the configurations
            of this domain on its own. Read from the directory itself when it
            is not said (see :func:`is_sub_domain`).
    """
    data = settings if settings is not None else load_domain_settings(path)
    source = os.path.join(path, SETTINGS_FILENAME)
    if implicit is None:
        implicit = is_sub_domain(path)
    return ConfigSet(path, config_set_rules(data, source=source, implicit=implicit), debug=debug)


def selectors_at(path, settings=None, messages=None):
    """
    The selectors a domain directory declares (see
    :mod:`odatix.workspace.selectors`), in the order they are written.
    """
    from odatix.workspace import selectors

    data = settings if settings is not None else load_domain_settings(path)
    return selectors.parse(data, messages=messages, where='"' + os.path.join(path, SETTINGS_FILENAME) + '"')


def matched_config_file(path, name, value=None, settings=None, debug=False, messages=None):
    """
    The file holding the configuration a directory substitutes for ``name``,
    selectors included: what :func:`config_file` finds, and, when the directory
    holds no such configuration, what its "match" block answers for it.

    Args:
        path (str): the directory of configurations.
        name (str): the configuration of the domain being run.
        value: what that configuration substitutes, when it is a single number,
            which is what a selector reads as "$value".
        messages (list): filled with what the user should be told.

    Returns:
        tuple: ``(path of the file, selector that answered)``. The selector is
        None when the configuration was found by name, and both are None when
        the directory has nothing for it.
    """
    from odatix.workspace import selectors
    from odatix.workspace.selection import Message

    data = settings if settings is not None else load_domain_settings(path)
    found = config_file(path, name, settings=data, debug=debug)
    if found is not None:
        return found, None

    declared = selectors_at(path, settings=data, messages=messages)
    if not declared:
        return None, None
    where = '"' + os.path.join(path, SETTINGS_FILENAME) + '"'
    selector, target = selectors.select(declared, name, value, messages=messages, where=where)
    if selector is None:
        return None, None

    found = config_file(path, target, settings=data, debug=debug)
    if found is None:
        if messages is not None:
            messages.append(Message(
                "error",
                'Selector "' + selector + '" in ' + where + ' substitutes "' + target
                + '", which is not a configuration of "' + path + '"',
                ["This directory holds: " + (", ".join(resolved_names(path, settings=data)) or "nothing")],
            ))
        return None, selector
    return found, selector


def config_file(path, name, settings=None, debug=False):
    """
    The file holding one configuration of a domain directory, resolved on the
    fly when only a rule describes it (see :meth:`ConfigSet.file_of`).

    This is what the run flows call instead of building the path themselves, so
    that a configuration described by a rule needs nothing to have been
    generated beforehand.

    Returns:
        str: path of the file, or None when the domain has no such
        configuration.
    """
    return config_set_at(path, settings=settings, debug=debug).file_of(name)


def resolved_names(path, settings=None, debug=False):
    """
    The names of the configurations a domain directory holds, files and rules
    together, in natural order.

    This is what a wildcard matches: a configuration a rule describes is one of
    the domain's, whether or not it has ever been written to disk.
    """
    return config_set_at(path, settings=settings, debug=debug).names()


def selected_config_file(root, selection):
    """
    The file holding the configuration a job selection names
    ("<instance>/<configuration>"), resolved on the fly like :func:`config_file`.

    Falls back to where the file would be, so that a caller reporting a missing
    configuration still has a path to name.
    """
    text = str(selection)
    domain, separator, name = text.rpartition("/")
    if not separator:
        return os.path.join(root, text + CONFIG_EXTENSION)
    found = config_file(os.path.join(root, domain), name)
    if found is not None:
        return found
    return os.path.join(root, domain, name + CONFIG_EXTENSION)
