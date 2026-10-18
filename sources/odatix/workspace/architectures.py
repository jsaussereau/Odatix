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
Architectures: the designs a workspace runs its jobs on.

An architecture is a directory holding a settings file that says where the
design is, how it is built, and how its parameters are substituted, plus the
configurations of its parameter domains.
"""

import copy
import os

import odatix.lib.hard_settings as hard_settings
import odatix.lib.overrides as overrides
from odatix.workspace.configs import (
    CONFIGURATIONS_KEY,
    LEGACY_CONFIGURATION_KEYS,
    ConfigGeneration,
    Configurations,
    ConfigurationsSetting,
    VariablesSetting,
    WithVariables,
    combinations,
    count_combinations,
)
from odatix.workspace.domains import ParameterDomain, ParameterDomainCollection
from odatix.workspace.entries import Collection, Entry
from odatix.workspace.exclusions import parse_exclusions
from odatix.workspace.selection import ExclusionFilter, Message
from odatix.workspace.settings import Setting, Settings
from odatix.workspace.yaml_io import parse_bool

__all__ = [
    "FrequencyBounds",
    "CustomFrequencies",
    "ArchitectureSettings",
    "Architecture",
    "ArchitectureCollection",
    "ResolvedFrequencies",
    "resolve_frequencies",
    "check_bounds",
]


######################################
# Settings
######################################

class FrequencyBounds(Settings):
    """
    The frequency range an fmax binary search runs in, in MHz.

    A bound left unset falls back to the workspace default, so only the bounds
    that are actually set are written.
    """

    lower_bound = Setting(None, type="optional_int", skip_if_empty=True, doc="Lowest frequency tried, in MHz.")
    upper_bound = Setting(None, type="optional_int", skip_if_empty=True, doc="Highest frequency tried, in MHz.")


class CustomFrequencies(Settings):
    """
    The frequencies a fixed-frequency synthesis runs at, in MHz.

    They come as a list, as a range, or as both: a range is expanded and
    appended to the list. A range whose step is missing, zero or "No" is off,
    which is how a block keeps a range it does not currently use.
    """

    frequencies = Setting(
        factory=list, type="int_list", key="list", style="flow", skip_if_empty=True,
        doc="Frequencies to synthesize at, in MHz.",
    )
    list_append = Setting(
        False, type="bool", style="yesno", skip_if_empty=True,
        doc="Whether this list adds to the one of the level above instead of replacing it.",
    )
    lower_bound = Setting(
        None, type="optional_int", skip_if_empty=True, doc="First frequency of the range, in MHz.",
    )
    upper_bound = Setting(
        None, type="optional_int", skip_if_empty=True, doc="Last frequency of the range, in MHz.",
    )
    # Taken as it comes: "No" (a boolean) is how a range is switched off, and
    # telling that from a step of 0 is what the resolution does.
    step = Setting(
        None, type="any", skip_if_empty=True,
        doc="Step between two frequencies of the range, in MHz. \"No\" to use no range.",
    )


class Testbench(Settings):
    """
    The testbench of a design, which every simulation template runs it with,
    unless the simulation names its own (see :mod:`odatix.sim.templates`).
    """

    top = Setting(
        "", type="str", skip_if_empty=True,
        doc="Module or entity at the top of the testbench. Guessed from its files when empty.",
    )
    files = Setting(
        factory=list, type="str_list", style="flow", skip_if_empty=True,
        doc="Its sources, relative to the workspace, like rtl_path. Glob patterns are accepted.",
    )
    parameters = Setting(
        factory=dict, type="dict", skip_if_empty=True,
        doc="Parameters (generics) its top is given. Values may use the placeholders of the "
            "simulation commands: ${width} is the value of the domain \"width\".",
    )
    # Without files, Odatix generates a minimal testbench (see odatix.sim.testbench_gen)
    cycles = Setting(None, type="optional_int", skip_if_empty=True, doc="Cycles the generated testbench runs (1000 when empty).")
    stimulus = Setting(
        "", type="str", skip_if_empty=True,
        doc="What the generated testbench drives the inputs with: \"random\" (when empty) or \"zero\".",
    )
    waves = Setting(None, type="any", skip_if_empty=True, doc="Whether the generated testbench dumps a VCD (Yes when empty).")


class ArchitectureSettings(WithVariables, Settings):
    """
    Settings of an architecture ("<architecture>/_settings.yml"), which are also
    the settings of its main parameter domain.

    What the architecture says for a part of its jobs only lives in the
    "overrides" section: an ordered list of rules, each selecting the jobs it
    applies to by tool, flow, target and configuration, and holding whatever
    those jobs should use instead ("constraints", "file_copy_*",
    "fmax_synthesis", "fixed_freq_synthesis", or any other key of this file).
    See :mod:`odatix.lib.overrides`. The section is not declared here, but it is
    preserved: like any other key Odatix does not know about, it stays in the
    file and in ``settings.extra``.
    """

    dropped_keys = LEGACY_CONFIGURATION_KEYS
    replacement_key = CONFIGURATIONS_KEY
    moved_keys = (
        ("fmax_lower_bound", "fmax_synthesis"), ("fmax_upper_bound", "fmax_synthesis"),
        ("custom_freq_synthesis", "fixed_freq_synthesis"),
    )

    # RTL generation
    generate_rtl = Setting(
        False, type="bool", style="yesno", section="RTL generation",
        doc="Whether the RTL is generated by a command instead of read from a directory.",
    )
    design_path = Setting(
        "", type="str", when="generate_rtl",
        doc="Directory of the design sources the generation runs on.",
    )
    design_path_whitelist = Setting(
        factory=list, type="list", when="generate_rtl", style="flow",
        doc="What to copy from the design directory. Everything, when empty.",
    )
    design_path_blacklist = Setting(
        factory=list, type="list", when="generate_rtl", style="flow",
        doc="What not to copy from the design directory.",
    )
    generate_command = Setting("", type="str", when="generate_rtl", doc="Command that generates the RTL.")
    generate_output = Setting("", type="str", when="generate_rtl", doc="Directory the command writes the RTL to.")

    # Source files
    rtl_path = Setting(
        "", type="str", when="!generate_rtl", section="Source files",
        doc="Directory holding the RTL of the design.",
    )
    top_level_file = Setting("", type="str", doc="File holding the top level module.")
    top_level_module = Setting("", type="str", doc="Name of the top level module.")

    # Signals
    clock_signal = Setting("", type="str", section="Signals", doc="Name of the clock signal of the top level.")
    reset_signal = Setting("", type="str", doc="Name of the reset signal of the top level.")
    reset_active_low = Setting(
        None, type="any", style="yesno", skip_if_empty=True,
        doc="Whether the reset is active low. Guessed from its name when empty (rst_n, resetn, nreset).",
    )

    # Parameters
    use_parameters = Setting(
        False, type="bool", style="yesno", section="Delimiters for parameter files",
        doc="Whether the configurations of the main domain are substituted into a file.",
    )
    param_target_file = Setting(
        "", type="str", skip_if_empty=True,
        doc="File the parameters are written into. The top level file, when empty.",
    )
    start_delimiter = Setting("", type="str", doc="Text after which the parameters are written. Escape sequences such as \\n are supported.")
    stop_delimiter = Setting("", type="str", doc="Text before which the parameters are written. Escape sequences such as \\n are supported.")

    # Extra files copied into each work directory
    file_copy_enable = Setting(
        False, type="bool", style="yesno", skip_if_empty=True,
        doc="Whether an extra file is copied into each work directory.",
    )
    file_copy_source = Setting("", type="str", when="file_copy_enable", doc="File to copy.")
    file_copy_dest = Setting("", type="str", when="file_copy_enable", doc="Where to copy it, in the work directory.")

    # Constraint files of this design, read on top of the timing constraint
    # Odatix generates. What only some of its jobs should read -- an IO
    # placement that only makes sense on one board, a floorplan only place &
    # route can use -- goes in a rule of the "overrides" section instead.
    constraints = Setting(
        factory=list, type="list", section="Constraints", skip_if_empty=True,
        doc="Constraint files read by the jobs of this architecture. Either file "
            "paths, or mappings with a \"files\" key and a \"scope\" among "
            "\"synthesis\", \"pnr\" and \"all\".",
    )

    # Testbench run by the simulation templates
    testbench = Setting(
        type=Testbench, section="Testbench", skip_if_empty=True,
        doc="Testbench of the design: \"top\", \"files\" and \"parameters\". "
            "Any simulation template runs it, unless the simulation names its own.",
    )

    # Frequencies
    fmax_synthesis = Setting(
        type=FrequencyBounds, section="Default frequencies (in MHz)", skip_if_empty=True,
        doc="Bounds of the fmax binary search for this architecture.",
    )
    fixed_freq_synthesis = Setting(
        type=CustomFrequencies, skip_if_empty=True,
        doc="Frequencies a fixed-frequency synthesis runs this architecture at "
            "(formerly \"custom_freq_synthesis\", still read).",
    )

    # Configurations
    configurations = ConfigurationsSetting(
        type=Configurations, section="Configurations", skip_if_empty=True,
        doc="Name and template the configurations of the main domain are built from. "
            "A list declares several rule sets, whose union the domain is.",
    )

    variables = VariablesSetting(
        factory=dict, type="dict", section="Variables", skip_if_empty=True,
        doc="Definition of each variable, by name. Variables are the values the "
            "configurations are built from. An architecture with no template "
            "substitutes them as \"${name}\" into its commands instead.",
    )

    attributes = Setting(
        factory=dict, type="dict", section="Attributes", skip_if_empty=True,
        doc="How to read values off the name or the content of the configurations of the "
            "main domain, so that exclusions can be written about hand-written ones. "
            "\"defaults\", \"from_name\", \"from_content\" and \"values\". See "
            "odatix.workspace.attributes.",
    )

    exclusions = Setting(
        factory=list, type="any", section="Exclusions", skip_if_empty=True,
        doc="Combinations of the parameter domains of this architecture that are not part "
            "of its design space. Each one has a \"when\", optionally a \"require\" naming "
            "what it should be instead, a \"kind\" among \"illegal\", \"duplicate\" and "
            "\"dominated\", and a \"message\". See odatix.workspace.exclusions.",
    )

    # Read so that the files written before "configurations" existed keep
    # meaning what they meant. Never written again: see dropped_keys.
    generate_configurations = Setting(False, type="bool", style="yesno", stored=False)
    generate_configurations_settings = Setting(type=ConfigGeneration, stored=False)

    def normalize(self):
        """
        Carry what the former keys hold over to the ones that replace them (see
        :meth:`WithVariables.normalize`), the fmax bounds written before
        "fmax_synthesis" existed included (see :func:`carry_over_legacy_bounds`).
        """
        super(ArchitectureSettings, self).normalize()
        carry_over_legacy_bounds(self)
        carry_over_fixed_freq_key(self)
        return self

    def frequencies(self, target="", configuration="", tool="", flow="", mode="fmax", fallback=None):
        """
        The frequencies a run uses, for one configuration on one target (see
        :func:`resolve_frequencies`).
        """
        return resolve_frequencies(
            self, target=target, configuration=configuration, tool=tool, flow=flow,
            mode=mode, fallback=fallback,
        )


######################################
# Fmax bounds written the former way
######################################

#: The keys the fmax bounds were written with before "fmax_synthesis" existed,
#: each with the key of the block that replaces it.
LEGACY_BOUND_KEYS = (("fmax_lower_bound", "lower_bound"), ("fmax_upper_bound", "upper_bound"))


def _rules(settings):
    rules = settings.extra.get("overrides")
    return [rule for rule in rules if isinstance(rule, dict)] if isinstance(rules, list) else []


def _holds_bound(block, key):
    return isinstance(block, dict) and block.get(key) is not None


def legacy_bound_keys(settings):
    """
    The former bound keys an :class:`ArchitectureSettings` still holds, at its
    root or in a rule of its "overrides" section.
    """
    found = []
    for old, _new in LEGACY_BOUND_KEYS:
        if old in settings.extra or any(old in rule for rule in _rules(settings)):
            found.append(old)
    return found


def carry_over_legacy_bounds(settings):
    """
    Move the former fmax bound keys into the "fmax_synthesis" blocks, wherever
    that keeps every job running at the bounds it ran at.

    A modern block wins over every former key (see
    :func:`resolve_frequencies`), so a former key is either moved to the block
    at its own level, when no block says that bound anywhere, or dropped, when
    the block of the root does and nothing could ever read it. Former keys in
    rules next to modern ones in other rules are left alone: which wins depends
    on the jobs, and only the user can say it in one form. Returns the former
    keys left, as :func:`legacy_bound_keys`.
    """
    if not legacy_bound_keys(settings):
        return []
    rules = copy.deepcopy(settings.extra.get("overrides"))
    changed_rules = False
    for old, new in LEGACY_BOUND_KEYS:
        in_rules = [rule for rule in (rules if isinstance(rules, list) else []) if isinstance(rule, dict) and old in rule]
        modern_root = getattr(settings.fmax_synthesis, new) is not None
        modern_rules = any(
            _holds_bound(rule.get("fmax_synthesis"), new)
            for rule in (rules if isinstance(rules, list) else []) if isinstance(rule, dict)
        )
        if in_rules and modern_rules and not modern_root:
            continue

        if old in settings.extra:
            value = settings.extra.pop(old)
            if not modern_root and value is not None:
                setattr(settings.fmax_synthesis, new, value)
        for rule in in_rules:
            value = rule.pop(old)
            changed_rules = True
            if modern_root or value is None:
                continue
            block = rule.get("fmax_synthesis")
            if not isinstance(block, dict):
                block = rule["fmax_synthesis"] = {}
            block[new] = value
    if changed_rules:
        settings.extra["overrides"] = rules
    return legacy_bound_keys(settings)


######################################
# The fixed-frequency block, formerly "custom_freq_synthesis"
######################################

#: The key of the frequencies of a fixed-frequency synthesis, named after the
#: term of the glossary, and the one it had before.
FIXED_FREQ_KEY = "fixed_freq_synthesis"
FORMER_FIXED_FREQ_KEY = "custom_freq_synthesis"


def _rules_holding(rules, key):
    return isinstance(rules, list) and any(isinstance(rule, dict) and key in rule for rule in rules)


def _renamed_in_rules(rules):
    """The rules of "overrides" with their former block read as the current one."""
    renamed = copy.deepcopy(rules)
    for rule in renamed:
        if isinstance(rule, dict) and FORMER_FIXED_FREQ_KEY in rule:
            value = rule.pop(FORMER_FIXED_FREQ_KEY)
            if FIXED_FREQ_KEY not in rule:
                rule[FIXED_FREQ_KEY] = value
    return renamed


def with_fixed_freq_key(data):
    """
    A plain settings mapping with its "custom_freq_synthesis" blocks read as
    "fixed_freq_synthesis", at the root and in every rule of "overrides". A
    level that says both keeps the current one.
    """
    if not isinstance(data, dict):
        return data
    rules = data.get("overrides")
    if FORMER_FIXED_FREQ_KEY not in data and not _rules_holding(rules, FORMER_FIXED_FREQ_KEY):
        return data
    data = dict(data)
    if FORMER_FIXED_FREQ_KEY in data:
        value = data.pop(FORMER_FIXED_FREQ_KEY)
        if FIXED_FREQ_KEY not in data:
            data[FIXED_FREQ_KEY] = value
    if _rules_holding(rules, FORMER_FIXED_FREQ_KEY):
        data["overrides"] = _renamed_in_rules(rules)
    return data


def carry_over_fixed_freq_key(settings):
    """The same, on an :class:`ArchitectureSettings` (see :meth:`ArchitectureSettings.normalize`)."""
    if FORMER_FIXED_FREQ_KEY in settings.extra:
        value = settings.extra.pop(FORMER_FIXED_FREQ_KEY)
        if FIXED_FREQ_KEY not in settings._file_data:
            settings.fixed_freq_synthesis = value
    rules = settings.extra.get("overrides")
    if _rules_holding(rules, FORMER_FIXED_FREQ_KEY):
        settings.extra["overrides"] = _renamed_in_rules(rules)


######################################
# What a run needs
######################################

#: What an architecture has to say before a run can build a job from it,
#: whatever that run does with it.
REQUIRED_SETTINGS = ("top_level_file", "top_level_module", "clock_signal", "reset_signal")


def validate(settings, path=""):
    """
    What is wrong with the settings of an architecture, as a list of
    :class:`Message`. Its errors keep a run from building its jobs, its
    warnings do not.

    This is only about what the settings file says, not about what is on disk:
    whether the RTL is where it says it is, and whether the top level really
    holds the module and the signals it names, is checked by the run itself,
    which is the only one knowing where its work directory is.

    Args:
        settings: the settings of the architecture, as an
            :class:`ArchitectureSettings` or a plain mapping.
        path (str): the settings file, for the messages.
    """
    data = settings.to_dict() if isinstance(settings, Settings) else (settings if isinstance(settings, dict) else {})
    messages = []

    def missing(key, because=""):
        if data.get(key) is not None:
            # Written, but empty ("reset_signal: ''"): saying the key cannot be
            # found would send the user looking for a line that is there
            text = 'Key "{0}" is empty in "{1}"{2}: a value is required.'
        else:
            text = 'Cannot find key "{0}" in "{1}"{2}.'
        messages.append(Message("error", text.format(key, path, because)))

    for key in REQUIRED_SETTINGS:
        if not data.get(key):
            missing(key)

    if parse_bool(data.get("generate_rtl"), False):
        if not data.get("generate_command"):
            missing("generate_command", " while generate_rtl=true")
        # "design_path" is what the generation runs on, and is what a generated
        # design normally needs, but it is not required here: architectures that
        # generate their RTL without one have always been allowed to run.
    elif not data.get("rtl_path"):
        missing("rtl_path")

    if parse_bool(data.get("use_parameters"), False):
        # An empty delimiter ("start_delimiter:" with nothing after it) says
        # nothing either: there is nowhere to write the parameters.
        for key in ("start_delimiter", "stop_delimiter"):
            if not data.get(key):
                missing(key, " while use_parameters=true")

    if parse_bool(data.get("file_copy_enable"), False):
        for key in ("file_copy_source", "file_copy_dest"):
            if not data.get(key):
                missing(key, " while file_copy_enable=true")

    if data.get("testbench") is not None:
        from odatix.sim.design_info import check_testbench

        problem = check_testbench(data.get("testbench"))
        if problem:
            messages.append(Message("error", '"testbench" in "{0}" {1}.'.format(path, problem)))

    # The former switch only meant something next to the block it switched on.
    # Alone, the design space ignores it and no configuration is generated.
    if (
        parse_bool(data.get("generate_configurations"), False)
        and not isinstance(data.get("generate_configurations_settings"), dict)
        and not data.get("configurations")
    ):
        messages.append(Message(
            "warning",
            '"{0}" sets "generate_configurations" without a "generate_configurations_settings" block: '
            'no configuration is generated.'.format(path),
            hints=['describe the configurations in a "configurations" block (name, template) instead'],
        ))

    return messages


######################################
# Frequency resolution
######################################

#: How the frequencies of a run are written, from the most general to the most
#: specific. An architecture settings file says them once for every job it
#: produces, and again in each rule of its "overrides" section that selects only
#: some of them (see :mod:`odatix.lib.overrides`).
FREQUENCY_LEVELS = ("global", "override")


class ResolvedFrequencies(object):
    """
    The frequencies one configuration of an architecture is run at on one
    target, once every level of its settings file has had its say.

    Attributes:
        lower_bound (int): lowest frequency the fmax binary search tries.
        upper_bound (int): highest frequency it tries.
        frequencies (list): the frequencies a fixed-frequency synthesis runs
            at, the range expanded.
        deprecated_bounds (bool): the file still spells its bounds the old way
            ("fmax_lower_bound" instead of a "fmax_synthesis" block).
        messages (list): what the file has that a user should know about.
    """

    def __init__(self, lower_bound=None, upper_bound=None, frequencies=None,
                 deprecated_bounds=False, messages=None):
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.frequencies = list(frequencies) if frequencies else []
        self.deprecated_bounds = deprecated_bounds
        self.messages = list(messages) if messages else []

    def __repr__(self):
        return "<ResolvedFrequencies {0}-{1} MHz, {2} frequencies>".format(
            self.lower_bound, self.upper_bound, len(self.frequencies)
        )


def check_bounds(lower_bound, upper_bound, step=0, kind="fmax synthesis"):
    """
    What is wrong with a frequency range, as a list of :class:`Message` (empty
    when it can be run).
    """
    messages = []
    for name, value in (("Lower bound", lower_bound), ("Upper bound", upper_bound), ("Step", step)):
        if isinstance(value, bool) or not isinstance(value, int):
            messages.append(Message("error", '{0} for {1} is "{2}" which is a "{3}" while it should be an integer{4}'.format(
                name, kind, value, type(value).__name__, ' or "No"' if name == "Step" else "",
            )))
    if messages:
        return messages
    if upper_bound <= lower_bound:
        messages.append(Message("error", "The upper bound ({0}) for {1} must be strictly greater than the lower bound ({2})".format(
            upper_bound, kind, lower_bound,
        )))
    return messages


def _cascade(blocks, key):
    """
    Read a key from the most specific level that holds it.

    A level that is there but does not hold the key hands over to the next one,
    which is what makes a target-wide setting apply to every configuration that
    does not override it.
    """
    value = None
    for block in blocks:
        value = block.get(key)
        if key in block:
            return value, True
    return value, False


def resolve_frequencies(settings, target="", configuration="", tool="", flow="", mode="fmax", fallback=None):
    """
    The frequencies a run uses for one configuration of an architecture.

    Args:
        settings: the settings of the architecture, as an
            :class:`ArchitectureSettings` or a plain mapping.
        target (str): the synthesis target, which a rule of the "overrides"
            section can select.
        configuration (str): the configuration, which a rule can select too.
        tool (str): the EDA tool running the job, which a rule can select.
        flow (str): the flow of that tool the job runs.
        mode (str): "fmax" for a binary search, "custom_freq" for a synthesis at
            given frequencies.
        fallback (list): frequencies to use when the file names none. The
            Odatix default when not given.

    Returns:
        ResolvedFrequencies
    """
    data = settings.to_dict() if isinstance(settings, Settings) else (settings if isinstance(settings, dict) else {})
    messages = []

    def levels(key):
        """The blocks holding a key, most specific first, the invalid ones reported."""
        try:
            found = overrides.blocks(
                data, key, tool=tool, flow=flow, target=target, configuration=configuration,
            )
        except overrides.OverrideError as error:
            messages.append(Message("error", str(error)))
            return []
        blocks = []
        for value in found:
            if isinstance(value, dict):
                blocks.append(value)
            else:
                messages.append(Message("error", 'Key "{0}" does not hold a list of settings.'.format(key)))
        return blocks

    data = with_fixed_freq_key(data)
    if mode == "custom_freq":
        return _resolve_custom_frequencies(levels(FIXED_FREQ_KEY), fallback, messages)
    return _resolve_fmax_bounds(levels("fmax_synthesis"), _legacy_bound_levels(data, tool, flow, target, configuration), messages)


def _legacy_bound_levels(data, tool, flow, target, configuration):
    """
    Every level of a file, most specific first, for the keys that are read as
    they come rather than out of a block.
    """
    try:
        rules = overrides.select(data, tool=tool, flow=flow, target=target, configuration=configuration)
    except overrides.OverrideError:
        rules = []
    rules.reverse()
    rules.append(data if isinstance(data, dict) else {})
    return rules


def _resolve_fmax_bounds(blocks, legacy_levels, messages):
    # How the bounds were written before "fmax_synthesis" existed. They are
    # still read, and still reported as deprecated, but a modern block wins.
    lower_bound = upper_bound = None
    deprecated = False
    for key, name in (("fmax_lower_bound", "lower"), ("fmax_upper_bound", "upper")):
        value, defined = _cascade(legacy_levels, key)
        if defined:
            deprecated = True
            if name == "lower":
                lower_bound = value
            else:
                upper_bound = value

    # A block bound left empty (None, which is what to_dict() writes for an
    # unset one) does not hide the legacy bound or a less specific block.
    for block in reversed(blocks):
        if block.get("lower_bound") is not None:
            lower_bound = block["lower_bound"]
        if block.get("upper_bound") is not None:
            upper_bound = block["upper_bound"]

    if lower_bound is None:
        lower_bound = hard_settings.default_fmax_lower_bound
    if upper_bound is None:
        upper_bound = hard_settings.default_fmax_upper_bound

    return ResolvedFrequencies(
        lower_bound=lower_bound, upper_bound=upper_bound, deprecated_bounds=deprecated, messages=messages,
    )


def _resolve_custom_frequencies(blocks, fallback, messages):
    lower_bound, lower_defined = _cascade(blocks, "lower_bound")
    upper_bound, upper_defined = _cascade(blocks, "upper_bound")
    step, step_defined = _cascade(blocks, "step")

    frequencies = _resolve_frequency_list(blocks)

    # A step that is missing, zero, or "No" means the block keeps a range it
    # does not currently use.
    if step_defined and step not in (0, False) and lower_defined and upper_defined:
        range_messages = check_bounds(lower_bound, upper_bound, step, kind="fixed-frequency synthesis")
        if not range_messages and step < 0:
            # A negative step used to give an empty range, and so no frequency
            # from it, without a word.
            range_messages = [Message("error", (
                'Step for fixed-frequency synthesis is {0}: it must be strictly positive, '
                'or 0 / "No" to use no range'
            ).format(step))]
        messages.extend(range_messages)
        if not range_messages:
            frequencies = frequencies + list(range(lower_bound, upper_bound + 1, step))

    if not frequencies:
        frequencies = list(fallback) if fallback else list(hard_settings.default_custom_freq_list)

    return ResolvedFrequencies(frequencies=frequencies, messages=messages)


def _resolve_frequency_list(blocks):
    """
    The frequency list of the most specific level that holds one.

    A level that sets "list_append" keeps the list of the level above it and
    adds its own to it, which is how a target runs at a few frequencies more
    than the ones every target runs at. Without it, the most specific list is
    the whole set and the levels above are not read.
    """
    frequencies = None
    appending = False
    for block in blocks:  # most specific first
        if "list" not in block:
            continue
        values = list(block.get("list") or [])
        if frequencies is None:
            frequencies = values
        elif appending:
            frequencies = frequencies + values
        else:
            break
        appending = bool(block.get("list_append", False))
        if not appending:
            break
    return frequencies if frequencies is not None else []


######################################
# Architectures
######################################

class Architecture(Entry):
    """
    One architecture of a workspace.

    Its settings are those of its main parameter domain, so
    ``arch.settings`` and ``arch.domains.main.settings`` are the same object,
    and ``arch.configs`` are the configurations of that main domain.
    """

    kind = "architecture"

    #: Settings class of the main domain of this kind of instance.
    settings_class = ArchitectureSettings

    #: Whether the value of a parameter domain is substituted into the commands
    #: this kind of instance runs, rather than into a file of its sources. A
    #: domain that substitutes nothing into a file ("use_parameters: no") is
    #: still a dimension of the sweep when it does -- which is what a workflow
    #: replacing "${domain}" in its tasks is made of.
    substitutes_in_commands = False

    def __init__(self, workspace, root, name):
        super(Architecture, self).__init__(workspace, root, name)
        self._main = ParameterDomain(self, hard_settings.main_parameter_domain)

    ######################################
    # Settings
    ######################################

    @property
    def main_domain(self):
        """The parameter domain this architecture carries itself."""
        return self._main

    @property
    def settings_path(self):
        return self._main.settings_path

    @property
    def settings(self):
        """The settings of this architecture, read from file on first access."""
        return self._main.settings

    @settings.setter
    def settings(self, value):
        self._main.settings = value

    def reload(self):
        """Forget the settings held in memory and read them from file again."""
        self._main.reload()
        return self

    def save(self, regenerate=False):
        """Write the settings of this architecture back to its file."""
        self._main.save(regenerate=regenerate)
        return self

    def update(self, values=None, **kwargs):
        """Change some settings and write them back, in one call."""
        self.settings.update(values, **kwargs)
        return self.save()

    ######################################
    # Domains and configurations
    ######################################

    @property
    def domains(self):
        """The parameter domains of this architecture, the main one first."""
        return ParameterDomainCollection(self)

    @property
    def configs(self):
        """The configurations of the main parameter domain."""
        return self._main.configs

    @property
    def attributes(self):
        """
        How the configurations of each of its domains are read, as a
        ``{domain: Attributes}`` mapping (see
        :mod:`odatix.workspace.attributes`).
        """
        return {domain.name: domain.attributes for domain in self.domains}

    def exclusions(self, applied=None):
        """
        The combinations of its parameter domains this architecture does not
        have (see :mod:`odatix.workspace.exclusions`).

        Args:
            applied (list): which kinds to apply -- ``illegal`` and
                ``duplicate`` when nothing says otherwise, a campaign being the
                one entitled to ask for ``dominated`` too.

        Returns:
            ExclusionSet: the rules, empty when the architecture declares none.
        """
        return parse_exclusions(
            self.settings.to_dict(), source=self.settings_path, applied=applied,
        )

    def parameter_domains(self):
        """
        The configurations of every domain that actually uses parameters, as a
        ``{domain: [configuration, ...]}`` mapping. Domains that substitute
        nothing, and domains without configurations, are left out: they add no
        axis to the sweep.
        """
        result = {}
        for domain in self.domains:
            # A domain substituting nothing into a file still is an axis when
            # what it feeds is a command (see substitutes_in_commands).
            if not domain.use_parameters and not self.substitutes_in_commands:
                continue
            names = domain.configuration_names()
            if names:
                result[domain.name] = names
        return result

    def variable_combinations(self):
        """
        The combinations of the variables this architecture substitutes into
        its commands (the variables of a file without a configuration template),
        each a list of ``"variable/value"`` selectors. Paired variables are
        zipped, the others crossed, as a run does. Empty without such variables.
        """
        import odatix.lib.virtual_param_domain as virtual_param_domain

        settings = self.settings.to_dict()
        if not self.substitutes_in_commands:
            # An architecture only sweeps the variables its generation command
            # uses, as a run does: anything else substitutes into nothing.
            names = virtual_param_domain.get_virtual_domain_names(settings)
            command = settings.get("generate_command", "") if settings.get("generate_rtl", False) else ""
            if not (virtual_param_domain.referenced_variable_names(command) & names):
                return []
        variants = virtual_param_domain.build_variants(
            settings=self.settings.to_dict(), settings_file=self.settings_path,
        )
        return [list(variant.get("requested_param_domains", [])) for variant in variants or []]

    def combinations(self, exclusions=True):
        """
        Every configuration combination of this architecture, written the way a
        job selection names it: its parameter domains crossed with its
        variables (see :meth:`variable_combinations`).

        This is the full sweep, every domain included -- what the selection
        ``"<arch>/* + <domain>/* + ..."`` runs, naming every domain. A selection
        that leaves a domain out (``"<arch>/*"``) does not sweep it: the
        sources keep the value written in them.

        Args:
            exclusions (bool): leave out the combinations the architecture
                excludes (see :meth:`exclusions`), as a run does.
        """
        found = combinations(self.parameter_domains(), self.name)
        variables = self.variable_combinations()
        if variables:
            found = [base + tokens for base in (found or [[self.name]]) for tokens in variables]
        if exclusions and found:
            excluder = self._exclusion_filter()
            if not excluder.empty:
                found = [tokens for tokens in found if excluder.check("+".join(tokens)) is None]
        return found

    def count_combinations(self, exclusions=True):
        """
        How many configuration combinations this architecture amounts to: the
        length of :meth:`combinations`, i.e. how many jobs the full sweep runs
        per target and frequency.
        """
        domains = self.parameter_domains()
        variables = self.variable_combinations()
        count = count_combinations(domains)
        total = max(count, 1) * len(variables) if variables else count
        if not exclusions or not total:
            return total
        excluder = self._exclusion_filter()
        if excluder.empty:
            return total
        return _count_kept(self.name, domains, variables, excluder)

    def _exclusion_filter(self):
        """
        The exclusion filter of this architecture, reading its rules from the
        settings in memory -- what :meth:`preview_configurations` shows --
        rather than from the file, which may not be saved yet.
        """
        from odatix.workspace.attributes import parse_attributes
        from odatix.workspace.selection import MAIN_DOMAIN

        excluder = ExclusionFilter.of(self)
        excluder._exclusions = self.exclusions()
        excluder._attributes[MAIN_DOMAIN] = parse_attributes(self.settings.to_dict())
        return excluder

    def preview_configurations(self):
        """
        The configurations the rules of the main parameter domain describe, as
        a ``{name: content}`` mapping, without writing anything (see
        :meth:`ParameterDomain.preview_configurations`; the other domains have
        their own, under :attr:`domains`).
        """
        return self._main.preview_configurations()

    def frequencies(self, target="", configuration="", tool="", flow="", mode="fmax", fallback=None):
        """
        The frequencies this architecture is run at, for one of its
        configurations on one target (see :func:`resolve_frequencies`).
        """
        return self.settings.frequencies(
            target=target, configuration=configuration, tool=tool, flow=flow,
            mode=mode, fallback=fallback,
        )

    def generate_configurations(self, overwrite=False, clear=False, domains=None):
        """
        Generate the configurations of the domains that are set to generate
        them, and return what was written, as a ``{domain: [name, ...]}``
        mapping.

        Args:
            overwrite (bool): replace configurations that already exist.
            clear (bool): delete the existing configurations of a domain first.
            domains (list): restrict the generation to these domains.
        """
        written = {}
        for domain in self.domains:
            if domains is not None and domain.name not in domains:
                continue
            if not domain.describes_configurations:
                continue
            names = domain.generate_configurations(overwrite=overwrite, clear=clear)
            if names:
                written[domain.name] = names
        return written


def _count_kept(name, domains, variables, excluder):
    """
    How many combinations the exclusions keep, without listing them all.

    Only the axes the rules read (a domain, the variables, the main domain)
    decide whether a combination is out; the others multiply. So only the
    product of the axes they read is walked: the full sweep of a big space
    with one rule about two domains costs as many checks as those two domains
    have combinations.
    """
    from itertools import product

    from odatix.lib.expressions import names_in

    main = hard_settings.main_parameter_domain
    variable_names = set(token.partition("/")[0] for tokens in variables for token in tokens)
    read = set()
    for rule in excluder.exclusions.active():
        for expression in (rule.when, rule.require):
            for written in names_in(expression or ""):
                root = str(written).split(".")[0]
                if root == "architecture":
                    continue
                if root in domains and root != main:
                    read.add(root)
                elif root in variable_names:
                    read.add("__variables__")
                else:
                    read.add(main)
    axes = [(domain, names) for domain, names in domains.items() if names]
    if variables:
        axes.append(("__variables__", variables))
    walked = [(axis, values) for axis, values in axes if axis in read]
    multiplier = 1
    for axis, values in axes:
        if axis not in read:
            multiplier *= len(values)
    kept = 0
    for choice in product(*[values for _axis, values in walked]):
        tokens = [name]
        picked = dict(zip([axis for axis, _values in walked], choice))
        if main in picked:
            tokens = ["{0}/{1}".format(name, picked[main])]
        for axis, value in picked.items():
            if axis == "__variables__":
                tokens += list(value)
            elif axis != main:
                tokens.append("{0}/{1}".format(axis, value))
        if excluder.check("+".join(tokens)) is None:
            kept += 1
    return kept * multiplier


class ArchitectureCollection(Collection):
    """The architectures of a workspace."""

    entry_class = Architecture

    def _initialize(self, entry, **settings):
        if settings:
            entry.update(settings)
