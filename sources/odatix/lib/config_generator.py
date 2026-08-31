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

import os
import re
import sys
import yaml
import math
import itertools
from typing import Optional

import odatix.lib.printc as printc
import odatix.lib.expressions as expressions
import odatix.lib.hard_settings as hard_settings
from odatix.lib.get_from_dict import get_from_dict, Key
import odatix.lib.yaml_loader as yaml_loader

script_name = os.path.basename(__file__)

dimension_types = ("bool", "range", "list", "multiples", "power_of_two")
modification_types = ("union", "disjunctive_union", "intersection", "difference")
combo_types = ("function", "conversion", "format")


#: Key holding the variables of an instance, at the root of its settings file.
variables_key = "variables"

#: Where variables used to be declared, still read for backward compatibility.
legacy_variables_parent = "generate_configurations_settings"

#: Key holding the name and the template the configurations are built from.
configurations_key = "configurations"

#: Key holding the constraints, next to the name and the template.
constraints_key = "constraints"


def parse_constraints(rules):
  """
  The constraints declared next to a name and a template, normalized.

  A constraint is a boolean expression over the variables that a point has to
  satisfy to exist at all. It is written either as the expression alone, or as
  a mapping carrying the message to show when it is what rules a point out::

      constraints:
        - "$p_rf_sp <= $p_rf_read_buf"
        - expr: "$width >= $depth"
          message: "the word has to be at least as wide as the address"

  Args:
      rules (dict): the block the name and the template are read from.

  Returns:
      list: ``[(expression, message), ...]``, in declaration order. Empty when
      nothing is declared.
  """
  if not isinstance(rules, dict):
    return []
  declared = rules.get(constraints_key)
  if declared is None:
    return []
  if not isinstance(declared, (list, tuple)):
    declared = [declared]

  constraints = []
  for entry in declared:
    if isinstance(entry, dict):
      expression = entry.get("expr", entry.get("expression", ""))
      message = entry.get("message", "")
    elif isinstance(entry, (list, tuple)):
      # Already normalized, as this function hands them back.
      expression = entry[0] if entry else ""
      message = entry[1] if len(entry) > 1 else ""
    else:
      expression, message = entry, ""
    expression = str(expression).strip() if expression is not None else ""
    if expression:
      constraints.append((expression, str(message).strip() if message else ""))
  return constraints


def parse_rule_sets(configurations):
  """
  The rule sets a "configurations" block declares.

  A single block describes one set of rules -- one name, one template, one list
  of constraints -- and the configurations it produces are every combination of
  the variables it uses. Written as a *list*, it declares several such sets, and
  what they produce is their **union**: the points of one are not combined with
  the points of another::

      configurations:
        - name: "M${m_value_dec}"
          template: |
            ...
        - name: "P${p_value_dec}"
          template: |
            ...

  This is what a parameter that decides *which other parameters mean anything*
  asks for. Combining the two families would describe designs that do not exist,
  and a single set of rules can only be made to leave them out by pinning the
  unused half with constraints -- which says the same thing far less directly.

  Args:
      configurations (Any): the value of the "configurations" key.

  Returns:
      list: the blocks, in declaration order. Empty when a single block (or
      nothing at all) is declared -- the caller keeps reading it the way it
      always has.
  """
  if not isinstance(configurations, (list, tuple)):
    return []
  return [block for block in configurations if isinstance(block, dict)]


#: What a "$var" or "${var}" placeholder looks like.
_placeholder_re = re.compile(r"\$\{?([A-Za-z_][A-Za-z_0-9]*)\}?")

#: What a bare name looks like in an expression.
_identifier_re = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _template_references(text):
  """The variables a template or a name substitutes, by their placeholders."""
  if text is None:
    return set()
  return set(_placeholder_re.findall(str(text)))


def _expression_references(text):
  """
  The variables an expression reads.

  A constraint or a "function" operand may spell a variable either way, since
  the "$", "{" and "}" are stripped before it is evaluated -- so a bare name
  counts too, unlike in a template, where a bare name is just text.
  """
  if text is None:
    return set()
  text = str(text)
  return _template_references(text) | set(_identifier_re.findall(text))


def _declaration_references(config):
  """The variables a variable's own declaration reads."""
  if not isinstance(config, dict):
    return set()
  settings = config.get("settings", {})
  if not isinstance(settings, dict):
    return set()
  value_type = config.get("type")
  if value_type == "function":
    return _expression_references(settings.get("op", ""))
  if value_type in ("format", "conversion"):
    return _template_references(settings.get("source", ""))
  if value_type in modification_types:
    sources = settings.get("sources", [])
    if not isinstance(sources, (list, tuple)):
      sources = [sources]
    references = set()
    for source in sources:
      references |= _template_references(source)
    return references
  return set()


def rule_set_variables(rules, variables):
  """
  The variables one rule set uses: the ones it names, and the ones those are
  computed from.

  A rule set says which variables it is about by using them, so nothing else has
  to be declared twice. Starting from the placeholders of its name and template
  and the names its constraints read, this follows every variable back through
  the declarations it is derived from, and keeps variables that move together
  (same "group") together.

  A rule set may also say it outright, with a ``variables`` list of names, for
  the case a variable has to vary without appearing anywhere -- the closure is
  taken from that list instead.

  Args:
      rules (dict): one rule set (name, template, constraints, ...).
      variables (dict): every variable declared at the root of the file.

  Returns:
      dict: the subset it uses, in declaration order.
  """
  variables = variables or {}
  declared = rules.get(variables_key) if isinstance(rules, dict) else None
  if isinstance(declared, (list, tuple)):
    reached = set(str(name) for name in declared)
  elif isinstance(declared, dict):
    reached = set(str(name) for name in declared)
  else:
    reached = _template_references(rules.get("name", "")) | _template_references(rules.get("template", ""))
    for expression, _message in parse_constraints(rules):
      reached |= _expression_references(expression)

  reached &= set(variables)

  # Follow the derivations back, and keep paired variables paired.
  groups = {}
  for name, config in variables.items():
    group = config.get("group") if isinstance(config, dict) else None
    group = str(group).strip() if group is not None else ""
    if group:
      groups.setdefault(group, []).append(name)

  while True:
    grown = set(reached)
    for name in reached:
      grown |= _declaration_references(variables.get(name, {})) & set(variables)
      config = variables.get(name, {})
      group = config.get("group") if isinstance(config, dict) else None
      group = str(group).strip() if group is not None else ""
      if group:
        grown |= set(groups.get(group, []))
    if grown == reached:
      break
    reached = grown

  return {name: config for name, config in variables.items() if name in reached}


def get_variables(settings):
  """
  The variables declared by a settings dict.

  Variables are declared at the root of the settings file, since they are not
  specific to configuration generation: they also act as virtual parameter
  domains for workflows and for architectures whose RTL is generated. They used
  to be declared inside "generate_configurations_settings", which is still read
  when the root key is absent.

  Args:
      settings (dict): content of a settings file.

  Returns:
      tuple:
          - variables (dict): the variables, empty when there is none.
          - legacy (bool): True when they were read from their former location.
  """
  if not isinstance(settings, dict):
    return {}, False

  variables = settings.get(variables_key)
  if isinstance(variables, dict):
    return variables, False

  generate_settings = settings.get(legacy_variables_parent)
  if isinstance(generate_settings, dict):
    variables = generate_settings.get(variables_key)
    if isinstance(variables, dict):
      return variables, True

  return {}, False


def _safe_sorted(values):
  """Sort values, falling back to string comparison for mixed types."""
  try:
    return sorted(values)
  except TypeError:
    return sorted(values, key=str)

class GeneratedPoint(object):
  """
  One point of a parameter space: the values its variables were assigned, the
  name it is known by, and the text it is rendered into.

  The name is the identity of a configuration everywhere else in Odatix (job
  selections, result files, work directories), so two points of the same space
  must never share one. The values are carried along as what the point *is*,
  independently of how it happens to be named.
  """

  __slots__ = ("name", "values", "content")

  def __init__(self, name, values, content):
    self.name = name
    self.values = values
    self.content = content

  def __repr__(self):
    return "<GeneratedPoint {0!r} {1!r}>".format(self.name, self.values)


def duplicate_point_names(points):
  """
  The names given to more than one point, as a ``{name: [values, ...]}``
  mapping (empty when every point has its own name).

  A name template that leaves out a variable gives several points the same
  name. Nothing downstream can tell them apart, so the sweep silently loses
  every point but one -- which is why this is reported rather than tolerated.
  """
  by_name = {}
  for point in points:
    by_name.setdefault(point.name, []).append(point.values)
  return {name: values for name, values in by_name.items() if len(values) > 1}


######################################
# Generator
######################################

class ConfigGenerator:
  """
  Generates parameter configurations based on a YAML file defining variable types,
  ranges, and naming templates.
  """

  def __init__(self, path: str = "", data: Optional[dict] = None, silent: bool = False, debug: bool = False, yaml_file: Optional[str] = None):
    """
    Initialize the configuration generator.
    
    Args:
        path (str): Path to the directory containing the "_settings.yml" file.
        data (dict): Optional pre-loaded YAML data to use instead of reading from file.
        silent (bool): If True, suppress warnings for missing keys.
        debug (bool): If True, print debug information.
        yaml_file (str): Where the data comes from, for error messages, when it
            is provided rather than read from a file.
    """
    self.path = path
    self.silent = silent
    self.debug = debug

    self.template = ""
    self.name_template = ""
    self.variables = {}
    self.constraints = []
    #: One generator per rule set when several are declared (see
    #: :func:`parse_rule_sets`), empty when a single one is -- which is what
    #: every method below reads to know whether it is looking at a space or at
    #: the union of several.
    self.rule_sets = []
    #: Constraints whose evaluation failed, reported once instead of per point.
    self._broken_constraints = set()
    self.valid = False
    self.enabled = False
    self.error_messages = []

    if data is not None:
      self.yaml_file = yaml_file if yaml_file else "<provided_data>"
      self.data = data
    else:
      self.yaml_file = os.path.join(self.path, hard_settings.param_settings_filename)
      self._load_yaml()

    self._validate_keys(self.data)

  def _load_yaml(self):
    """
    Load YAML settings and validate the presence of necessary keys.
    
    Returns:
        dict: Parsed YAML data.
    """
    self.data = {}
    if not os.path.isfile(self.yaml_file):
      printc.error(f"YAML file '{self.yaml_file}' does not exist.")
      sys.exit(-1)

    try:
      with open(self.yaml_file, "r") as f:
        data = yaml_loader.safe_load(f)
        if data is None:
          printc.error(f"YAML file \"{self.yaml_file}\" is empty!")
          sys.exit(-1)
    except yaml.YAMLError as e:
      printc.error(f"Invalid YAML file \"{self.yaml_file}\": {e}")
      sys.exit(-1)
    self.data = data

  def _validate_keys(self, data):
    # Check main keys
    hide = not self.debug
    generate_enabled, generate_defined = get_from_dict("generate_configurations", data, self.yaml_file, default_value=False, silent=hide, script_name=script_name)
    generate_settings, generate_settings_defined = get_from_dict("generate_configurations_settings", data, self.yaml_file, silent=hide, script_name=script_name)
    
    # Variables live at the root of the settings file, but are still read from
    # "generate_configurations_settings" when declared the former way.
    root_variables, root_variables_defined = get_from_dict("variables", data, self.yaml_file, type=dict, silent=True, script_name=script_name)
    legacy_variables = None
    legacy_variables_defined = False
    if not root_variables_defined and isinstance(generate_settings, dict):
      legacy_variables, legacy_variables_defined = get_from_dict("variables", generate_settings, self.yaml_file, parent=legacy_variables_parent, type=dict, silent=True, script_name=script_name)

    if root_variables_defined:
      self.variables, variables_defined = root_variables, True
    elif legacy_variables_defined:
      self.variables, variables_defined = legacy_variables, True
    else:
      self.variables, variables_defined = {}, False

    # Several rule sets, whose points are the union of what each produces.
    blocks = parse_rule_sets(data.get(configurations_key))
    if blocks:
      self._build_rule_sets(blocks, variables_defined)
      return

    # The current form: a "configurations" block holding the name and the
    # template. It needs no flag to turn it on -- describing configurations is
    # what asks for them.
    configurations, configurations_defined = get_from_dict(configurations_key, data, self.yaml_file, type=dict, silent=True, script_name=script_name)
    if configurations_defined and isinstance(configurations, dict) and configurations.get("name"):
      self.name_template, name_template_defined = get_from_dict("name", configurations, self.yaml_file, parent=configurations_key, type=str, behavior=Key.MANTADORY, script_name=script_name)
      self.template, template_defined = get_from_dict("template", configurations, self.yaml_file, parent=configurations_key, default_value="", silent=True, script_name=script_name)
      self.constraints = parse_constraints(configurations)
      if not variables_defined:
        get_from_dict("variables", data, self.yaml_file, type=dict, behavior=Key.MANTADORY, script_name=script_name)
      self.valid = name_template_defined and variables_defined
      generate_enabled = self.valid
    elif generate_settings_defined:
      self.template, template_defined = get_from_dict("template", generate_settings, self.yaml_file, parent="generate_configurations_settings", behavior=Key.MANTADORY, script_name=script_name)
      self.name_template, name_template_defined = get_from_dict("name", generate_settings, self.yaml_file, parent="generate_configurations_settings", type=str, behavior=Key.MANTADORY, script_name=script_name)
      self.constraints = parse_constraints(generate_settings)
      if not variables_defined:
        # Report the missing key where it is now expected: at the root.
        get_from_dict("variables", data, self.yaml_file, type=dict, behavior=Key.MANTADORY, script_name=script_name)
      self.valid = generate_settings_defined and template_defined and name_template_defined and variables_defined and generate_defined
    else:
      self.valid = False

    # Concat all strings if template is a list
    if isinstance(self.template, list):
      self.template = "\n".join(map(str, self.template)) 

    if not generate_defined and generate_settings_defined and not self.silent:
      printc.warning('"generate_configurations_settings" is defined while "generate_configurations" is not. Disabling configuration generation.', script_name)
    if generate_defined and generate_enabled and not generate_settings_defined and not self.silent:
      printc.error('Configuration generation is enabled while "generate_configurations_settings" is not defined.', script_name)

    self.enabled = generate_enabled

  def _build_rule_sets(self, blocks, variables_defined):
    """
    Build one generator per rule set.

    Each one is handed the variables its rules use (see
    :func:`rule_set_variables`) and nothing else, so that a variable another
    rule set is about cannot become an axis here: that is precisely what makes
    the union a union rather than a product.

    Args:
        blocks (list): the rule sets, in declaration order.
        variables_defined (bool): whether the file declares variables at all.
    """
    self.rule_sets = []
    if not variables_defined:
      get_from_dict("variables", self.data, self.yaml_file, type=dict, behavior=Key.MANTADORY, script_name=script_name)
      self.valid = False
      self.enabled = False
      return

    for index, block in enumerate(blocks):
      if not block.get("name"):
        printc.error(
          'Rule set #{0} of "{1}" declares no "name", in "{2}".'.format(index + 1, configurations_key, self.yaml_file),
          script_name,
        )
        self.rule_sets = []
        self.valid = False
        self.enabled = False
        return
      sub_data = {
        configurations_key: dict(block),
        variables_key: rule_set_variables(block, self.variables),
      }
      self.rule_sets.append(
        ConfigGenerator(data=sub_data, silent=self.silent, debug=self.debug, yaml_file=self.yaml_file)
      )

    self.valid = all(rule_set.valid for rule_set in self.rule_sets)
    self.enabled = self.valid
    # What the whole block stands for, for anything reading a single set of
    # rules: the first name and template are as good an answer as any, and are
    # only ever shown, never generated from.
    if self.rule_sets:
      self.name_template = self.rule_sets[0].name_template
      self.template = self.rule_sets[0].template

  def evaluate_expression(self, expr, values_map, silent=False):
    """
    Evaluate a mathematical expression using the current values of variables.

    Args:
        expr (str): The expression to evaluate.
        values_map (dict): A dictionary containing values for referenced variables.
        silent (bool): If True, do not report a failed evaluation -- for a
            caller that reports it itself, once instead of per point.

    Returns:
        Any: The result of evaluating the expression.
    """
    try:
      return expressions.evaluate(expr, values_map)
    except expressions.ExpressionError as e:
      if not silent:
        printc.error(str(e), script_name)
      return None

  def satisfies(self, value_map):
    """
    Whether an assignment of the variables satisfies every constraint.

    A point that does not is not *hidden*, it does not exist: the constraints
    say which combinations mean something, so a rejected one is left out of the
    space the way an axis leaves out a value it does not offer. This is what
    tells them apart from the configuration blacklist, which names points that
    exist but are not run.

    An expression that cannot be evaluated is reported once and treated as
    unsatisfied, so that a typo empties the space loudly instead of quietly
    keeping every point.

    Args:
        value_map (dict): the value of each variable, derived ones included.

    Returns:
        bool: True when the point belongs to the space.
    """
    for expression, message in self.constraints:
      result = self.evaluate_expression(expression, value_map, silent=True)
      if result is None:
        if expression not in self._broken_constraints:
          self._broken_constraints.add(expression)
          printc.error(
            f'Constraint "{expression}" could not be evaluated, in "{self.yaml_file}". '
            'No configuration will be generated as long as it cannot be.',
            script_name,
          )
        return False
      if not result:
        if self.debug:
          detail = f" ({message})" if message else ""
          printc.note(f'Constraint "{expression}" rejects {value_map}{detail}', script_name)
        return False
    return True

  def generate(self):
    """
    Generate all possible parameter combinations based on the configuration.
    Includes support for union, disjunctive_union, intersection, and difference.

    Returns:
        dict: A dictionary where keys are generated names and values are formatted templates.
        dict: A dictionary where keys are variable names and values are lists of all possible values for those variables.
    """
    points, all_vars_values = self.generate_points()
    final_configs = {}
    for point in points:
      final_configs[point.name] = point.content
    return final_configs, all_vars_values

  def dimensions(self):
    """
    The axes of the space: what a point is free to choose, and what it may
    choose there.

    The cross product is not taken over the variables but over *groups* of
    them, because variables sharing a "group" move together -- their values are
    matched position by position rather than combined. An axis is therefore a
    list of rows, each row an assignment of the variables of that group::

        [
          {"variables": ["width"],           "rows": [{"width": 8}, {"width": 16}]},
          {"variables": ["mant", "exp"],     "rows": [{"mant": 23, "exp": 8}, ...]},
        ]

    Choosing one row per axis and merging them gives exactly the assignments
    :meth:`generate_points` walks through, so an exhaustive sweep is the search
    that takes every combination of the axes, and any other search is the same
    thing choosing fewer. The derived variables are left out: they are computed
    from a choice (see :meth:`derive_point`), not chosen.

    Returns:
        list: the axes, in declaration order. Empty when the rules describe no
        space at all.
    """
    if self.rule_sets:
      # The union of several spaces has no axes of its own: a choice on the
      # axes of one rule set means nothing in another. Its subspaces are the
      # spaces, and each of them has axes (see :attr:`rule_sets`).
      return []

    rows_per_group, _dimension_vars, _source_vars, valid = self._dimension_rows()
    if not valid:
      return []
    return [
      {"variables": list(rows[0].keys()) if rows else [], "rows": rows}
      for rows in rows_per_group
    ]

  def _dimension_rows(self):
    """
    The axes of the space, with what building them found out.

    Split out of :meth:`generate_points` so that a search can be handed the
    axes without walking every point of their cross product -- which is the
    whole of the difference between exploring a space and enumerating it.

    Returns:
        tuple: the rows of each axis, the values of the dimension variables,
        the values of the variables used only as sources of a set operation,
        and whether the rules could be read at all.
    """
    if not self.valid or not self.enabled:
      return [], {}, {}, False

    sources_used = set()
    for variable, config in self.variables.items():
      value_type, value_type_defined = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
      if value_type in modification_types:
        settings, settings_defined = get_from_dict("settings", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
        if not settings_defined:
          return [], {}, {}, False
        sources, sources_defined = get_from_dict("sources", settings, self.yaml_file, parent=f"{variable}[settings]", behavior=Key.MANTADORY, type=list, script_name=script_name)
        if not sources_defined:
          return [], {}, {}, False
        for source in sources:
          sources_used.add(source)
      elif value_type not in dimension_types and value_type not in combo_types:
        printc.error(f'Invalid type \"{value_type}\" for variable "{variable}", in ' + self.yaml_file + '".', script_name)
        return [], {}, {}, False

    dimension_vars = {}
    source_dim_vars = {}  # dimension variables used only as union/intersection/etc. sources:
                          # excluded from the combination cross product, but still shown in the preview
    for variable, config in self.variables.items():
      value_type, _ = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
      if value_type in dimension_types:
        if variable in sources_used:
          source_dim_vars[variable] = self.generate_values_for_dim(variable, config)
        else:
          dimension_vars[variable] = self.generate_values_for_dim(variable, config)

    result_set = set()
    for variable, config in self.variables.items():
      value_type, _ = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
      if value_type in modification_types:
        settings, settings_defined = get_from_dict("settings", config, self.yaml_file, behavior=Key.MANTADORY, script_name=script_name)
        if settings_defined:
          sources, sources_defined = get_from_dict("sources", settings, self.yaml_file, behavior=Key.MANTADORY, default_value=[], type=list, script_name=script_name)
          if sources_defined:
            sources = [source.replace("$", "").replace("{", "").replace("}", "") for source in sources]
            sets = [set(self.generate_values_for_dim(source, self.variables.get(source, {}))) for source in sources if source in self.variables]
            
            if value_type == "union":
              if sets:
                result_set = set.union(*sets)
              else:
                result_set = set()
            elif value_type == "disjunctive_union":
              if sets:
                result_set = set.union(*sets) - set.intersection(*sets)
              else:
                result_set = set()
            elif value_type == "intersection":
              if sets:
                result_set = set.intersection(*sets)
              else:
                result_set = set()
            elif value_type == "difference":
              if len(sets) == 2:
                result_set = sets[0] - sets[1]
              else:
                result_set = set()
                printc.error(f'{variable} -> The\"difference\" operation only supports \"sources\" having exactly two elements, in ' + self.yaml_file + '".', script_name)       
            else:
              result_set = set()
              printc.warning(f'Invalid operation for variable "{variable}", in ' + self.yaml_file + '".', script_name)

            dimension_vars[variable] = _safe_sorted(result_set)

    if self.debug:
      printc.note(f"dimension_vars after set operations: {dimension_vars}", script_name)

    # Group dimension variables: variables sharing the same non-empty "group"
    # are zipped together (their values matched position by position) instead of
    # being cross-combined, so a "couple" of variables stays paired. Ungrouped
    # variables each form their own singleton group and are cross-combined as
    # before. The cross product is then taken over the groups.
    grouped_var_names = self._group_dimension_vars(dimension_vars)
    group_row_lists = []
    for members in grouped_var_names:
      member_values = [dimension_vars[member] for member in members]
      if len(members) > 1:
        lengths = [len(values) for values in member_values]
        if len(set(lengths)) > 1:
          printc.warning(
            f'Paired variables {members} have different value counts {lengths}; '
            f'pairing is truncated to the shortest ({min(lengths)}), in "' + self.yaml_file + '".',
            script_name,
          )
      # zip(*member_values) yields one tuple per paired position (length 1 for
      # a singleton group), turned into a {variable: value} row.
      rows = [dict(zip(members, combo)) for combo in zip(*member_values)]
      group_row_lists.append(rows)

    return group_row_lists, dimension_vars, source_dim_vars, True

  def generate_points(self):
    """
    Every point of the space, in generation order.

    Same combinations as :meth:`generate`, but each one is kept whole: the
    values the variables were assigned, not only the name and the text they
    were rendered into. That assignment is what names a point for a search
    that picks its points one by one, instead of enumerating them all.

    Returns:
        list: the :class:`GeneratedPoint` of the space, in generation order.
        dict: the values of each variable, as :meth:`generate` returns them.
    """
    if self.rule_sets:
      return self._union_points()

    group_row_lists, dimension_vars, source_dim_vars, valid = self._dimension_rows()
    if not valid:
      return [], {}

    points = []
    computed_values = {}  # per-variable sets of values computed by function/format/conversion

    for group_combo in itertools.product(*group_row_lists):
      value_map = {}
      for row in group_combo:
        value_map.update(row)
      # Computed into a dict of its own, and merged only once the point is
      # known to exist: a value a constraint rules out is not a value the
      # variable takes, and the preview must not offer it.
      point_values = {}
      for variable, config in self.variables.items():
        value_type, _ = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
        if value_type in combo_types:
          self._apply_derived_variable(variable, config, value_map, point_values)

      if not self.satisfies(value_map):
        continue

      for variable, values in point_values.items():
        computed_values.setdefault(variable, set()).update(values)
      points.append(self.render_point(value_map))

    if self.debug:
      printc.note(f"generated {len(points)} configurations.", script_name)

    all_vars_values = {k: _safe_sorted(v) for k, v in computed_values.items()}
    all_dim_var_values = {k: _safe_sorted(set(v)) if isinstance(v, list) else [v] for k, v in dimension_vars.items()}
    all_source_dim_var_values = {k: _safe_sorted(set(v)) if isinstance(v, list) else [v] for k, v in source_dim_vars.items()}
    all_vars_values.update(all_dim_var_values)
    all_vars_values.update(all_source_dim_var_values)
    return points, all_vars_values

  def _union_points(self):
    """
    The points of every rule set, one set after the other.

    Nothing is combined across rule sets and nothing is merged: a point belongs
    to the rule set that produced it. Two rule sets naming the same
    configuration are caught the same way one rule set naming two points alike
    is -- by :func:`duplicate_point_names`, at the caller.

    Returns:
        list: the :class:`GeneratedPoint` of the union, in declaration order.
        dict: the values each variable takes, over the union.
    """
    points = []
    all_vars_values = {}
    for rule_set in self.rule_sets:
      rule_set_points, values = rule_set.generate_points()
      points.extend(rule_set_points)
      for variable, variable_values in values.items():
        merged = set(all_vars_values.get(variable, [])) | set(variable_values)
        all_vars_values[variable] = _safe_sorted(merged)
    if self.debug:
      printc.note("generated {0} configurations over {1} rule sets.".format(len(points), len(self.rule_sets)), script_name)
    return points, all_vars_values

  def _apply_derived_variable(self, variable, config, value_map, computed_values):
    """
    Compute one derived variable ("function", "format" or "conversion") into an
    assignment, from the values it already holds.

    Args:
        variable (str): name of the derived variable.
        config (dict): its declaration.
        value_map (dict): the assignment, updated in place.
        computed_values (dict): per-variable set of every computed value, for
            the preview of the values a variable takes. Updated in place.
    """
    value_type, _ = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
    settings, defined = get_from_dict("settings", config, self.yaml_file, silent=True, script_name=script_name)
    if not defined:
      return

    if value_type == "function":
      op, _ = get_from_dict("op", settings, self.yaml_file, silent=True, script_name=script_name)
      if op:
        evaluated_expr = self.evaluate_expression(op, value_map)
        if evaluated_expr is not None:
          value_map[variable] = evaluated_expr
          computed_values.setdefault(variable, set()).add(evaluated_expr)

    elif value_type == "format":
      source, source_defined = get_from_dict("source", settings, self.yaml_file, silent=True, script_name=script_name)
      if source_defined:
        formatted_values = self.format_value_map(value_map)
        source = self.substitute_variables(str(source), formatted_values)
        value_map[variable] = source
        computed_values.setdefault(variable, set()).add(source)

    elif value_type == "conversion":
      from_type, _ = get_from_dict("from", settings, self.yaml_file, silent=True, script_name=script_name)
      to_type, _ = get_from_dict("to", settings, self.yaml_file, silent=True, script_name=script_name)
      source, sources_defined = get_from_dict("source", settings, self.yaml_file, silent=True, script_name=script_name)
      if sources_defined:
        source = str(source).replace("$", "").replace("{", "").replace("}", "")
      if source in value_map:
        converted = self.apply_conversion(value_map[source], from_type, to_type)
        value_map[variable] = converted
        computed_values.setdefault(variable, set()).add(converted)
      else:
        printc.warning(f'Source "{source}" not found for conversion variable "{variable}"', script_name)

  def render_point(self, value_map):
    """
    Turn one assignment of the variables into the point it stands for: the name
    it is known by and the text it is rendered into.

    The assignment is expected to already hold the derived variables
    (``function``, ``format``, ``conversion``), which :meth:`generate_points`
    computes as it walks the combinations. :meth:`derive_point` computes them
    for an assignment that comes from somewhere else.

    Args:
        value_map (dict): the value of each variable.

    Returns:
        GeneratedPoint: the name, the values and the rendered text.
    """
    formatted_values = self.format_value_map(value_map)
    return GeneratedPoint(
      name=self.substitute_variables(self.name_template, formatted_values),
      values=dict(value_map),
      content=self.substitute_variables(self.template, formatted_values),
    )

  def derive_point(self, assignment):
    """
    Render the point of an assignment of the *dimension* variables, computing
    the derived variables (``function``, ``format``, ``conversion``) it implies.

    This is the single-point counterpart of :meth:`generate_points`, for a
    caller that chooses which point it wants instead of taking them all.

    Args:
        assignment (dict): the value of each dimension variable.

    Returns:
        GeneratedPoint: the name, the values and the rendered text, or None
        when the assignment does not satisfy the constraints -- that point is
        not part of the space.
    """
    if self.rule_sets:
      # The assignment belongs to one of the rule sets: the one whose variables
      # it assigns and whose constraints it satisfies.
      for rule_set in self.rule_sets:
        if not set(rule_set.variables) >= set(assignment):
          continue
        point = rule_set.derive_point(assignment)
        if point is not None:
          return point
      return None

    value_map = dict(assignment)
    for variable, config in self.variables.items():
      value_type = config.get("type") if isinstance(config, dict) else None
      if value_type in combo_types:
        self._apply_derived_variable(variable, config, value_map, {})
    if not self.satisfies(value_map):
      return None
    return self.render_point(value_map)

  def _variable_group(self, variable):
    """Return the non-empty "group" label of a variable, or None if ungrouped."""
    config = self.variables.get(variable, {})
    group = config.get("group", None) if isinstance(config, dict) else None
    if group is None or str(group).strip() == "":
      return None
    return str(group).strip()

  def _group_dimension_vars(self, dimension_vars):
    """
    Group dimension variable names for the combination step.

    Variables sharing the same non-empty "group" are returned together (to be
    zipped); every other variable forms its own singleton group. Order follows
    the first appearance of each variable / group.

    Returns:
        list of lists of variable names.
    """
    ordered_groups = []
    group_lists = {}
    for variable in dimension_vars:
      group = self._variable_group(variable)
      if group is None:
        ordered_groups.append([variable])
      elif group in group_lists:
        group_lists[group].append(variable)
      else:
        new_group = [variable]
        group_lists[group] = new_group
        ordered_groups.append(new_group)
    return ordered_groups

  def format_value_map(self, value_map):
    """
    Format every value of a value map with its variable's format string, if any.
    """
    formatted_values = {}
    for k, v in value_map.items():
      var_cfg = self.variables.get(k, {})
      if var_cfg.get("type") == "format":
        format_str = var_cfg.get("settings", {}).get("format", None)
      else:
        format_str = var_cfg.get("format", None)
      formatted_values[k] = self.format_value(v, format_str)
    return formatted_values

  @staticmethod
  def substitute_variables(text, values):
    """
    Replace $var and ${var} placeholders in a string. Longer variable names are
    replaced first so that a variable whose name is a prefix of another
    (e.g. $WIDTH / $WIDTH_OUT) cannot corrupt the substitution.
    """
    for name in sorted(values, key=len, reverse=True):
      value = str(values[name])
      text = text.replace(f"${{{name}}}", value).replace(f"${name}", value)
    return text

  def generate_values_for_dim(self, var_name, var_config):
    """
    Generate the list of values for a dimension variable (bool/range/list/multiples/power_of_two).
    If it's 'function' or 'union', we skip for dimension creation here.
    """
    value_type, value_type_defined = get_from_dict("type", var_config, self.yaml_file, behavior=Key.MANTADORY, script_name=script_name)
    if value_type in ("function", "union"):
      return []

    return self.generate_values(var_config, var_name)

  def generate_values(self, config, name):
    """
    Generate values for a given variable configuration.
    
    Args:
        config (dict): Configuration settings for value generation.

    Returns:
        list: A list of generated values.
    """
    values = []

    value_type, value_type_defined = get_from_dict("type", config, self.yaml_file, parent=name, behavior=Key.MANTADORY, script_name=script_name)
    
    no_settings_var = value_type == "bool"
    settings, settings_defined = get_from_dict("settings", config, self.yaml_file, parent=name, behavior=Key.MANTADORY, silent=no_settings_var, script_name=script_name)
    if not value_type_defined or (not settings_defined and value_type != "bool"):
      return values

    if no_settings_var:
      whitelist = None
      blacklist = None
    else:
      whitelist, _ = get_from_dict("whitelist", settings, self.yaml_file, parent=name + "[settings]", silent=True, default_value=None, script_name=script_name)
      blacklist, _ = get_from_dict("blacklist", settings, self.yaml_file, parent=name + "[settings]", silent=True, default_value=None, script_name=script_name)

    if value_type == "bool":
      values = [0, 1]

    elif value_type == "range":
      from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      to_value, to_defined = get_from_dict("to", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      step_value, _ = get_from_dict("step", settings, self.yaml_file, parent=name + "[settings]", default_value=1, silent=True, script_name=script_name)
      if to_defined and from_defined:
        if step_value == 0:
          printc.error('"step" must not be 0 for range "' + name + "[settings]" + '", in "' + self.yaml_file + '".', script_name)
          return []
        values = list(range(from_value, to_value + 1, step_value))
      else:
        printc.note('You can define it like this:', script_name)
        printc.magenta("type: range:")
        printc.magenta("settings:")
        printc.magenta("  from: XXX")
        printc.magenta("  to: XXX")
        printc.magenta("  step: XXX")
        return []

    elif value_type == "power_of_two":
      from_value, from_defined = get_from_dict("from_2^", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
      to_value, to_defined = get_from_dict("to_2^", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
      if to_defined and from_defined:
        values = [2**i for i in range(int(from_value), int(to_value) + 1)]
      else:
        from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
        to_value, to_defined = get_from_dict("to", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
        if to_defined and from_defined:
          if from_value <= 0 or to_value <= 0:
            printc.error('"from" and "to" must be strictly positive for power_of_two "' + name + "[settings]" + '", in "' + self.yaml_file + '".', script_name)
            return []
          # ceil on the lower bound so no generated value falls below "from"
          values = [2**i for i in range(math.ceil(math.log2(from_value)), int(math.log2(to_value)) + 1)]
        else:
          printc.error('Cannot find a valid power_of_two definition for "' + name + "[settings]" + '", in "' + self.yaml_file + '".', script_name)
          printc.note('You can define it like this:', script_name)
          printc.magenta("type: power_of_two:")
          printc.magenta("settings:")
          printc.magenta("  from_2^: XXX")
          printc.magenta("  to_2^: XXX")
          printc.cyan("or ")
          printc.magenta("type: power_of_two:")
          printc.magenta("settings:")
          printc.magenta("  from: XXX")
          printc.magenta("  to: XXX")
          return []

    elif value_type == "list":
      list_values, list_defined = get_from_dict("list", settings, self.yaml_file, parent=name + "[settings]", type=list, behavior=Key.MANTADORY, script_name=script_name)
      if list_defined:
        values = list_values
      else:
        printc.note('You can define it like this:', script_name)
        printc.magenta("type: list:")
        printc.magenta("settings:")
        printc.magenta("  list: [XXX, XXX, XXX]")
        return []
    elif value_type == "multiples":
      from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      to_value, to_defined = get_from_dict("to", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      base_value, base_defined = get_from_dict("base", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      if to_defined and from_defined and base_defined:
        values = [x for x in range(from_value, to_value + 1) if x % base_value == 0]
      else:
        printc.note('You can define it like this:', script_name)
        printc.magenta("type: multiples:")
        printc.magenta("settings:")
        printc.magenta("  from: XXX")
        printc.magenta("  to: XXX")
        printc.magenta("  base: XXX")
        return []

    # Apply whitelist/blacklist filtering
    if whitelist is not None:
      values = [v for v in values if v in whitelist]

    if blacklist is not None:
      values = [v for v in values if v not in blacklist]

    return values

  def apply_conversion(self, value, from_type, to_type):
    """
    Apply number base conversions.

    Args:
        value (str): The value to convert.
        from_type (str): What to convert from.
        to_type (str): What to convert to.

    Returns:
        str: Converted value.
    """
    try:
      if value is None:
        printc.warning(f'Cannot convert a None value from "{from_type}" to "{to_type}"', script_name)
        return value
      if from_type == "bin":
        dec_value = int(str(value), 2)
        if to_type == "dec":
          return str(dec_value)
        elif to_type == "hex":
          return hex(dec_value)[2:]
      elif from_type == "dec":
        dec_value = int(value)
        if to_type == "bin":
          return bin(dec_value)[2:]
        elif to_type == "hex":
          return hex(dec_value)[2:]
      elif from_type == "hex":
        dec_value = int(str(value), 16)
        if to_type == "bin":
          return bin(dec_value)[2:]
        elif to_type == "dec":
          return str(dec_value)
      printc.warning(f'Conversion from "{from_type}" to "{to_type}" is not supported', script_name)
    except (ValueError, TypeError):
      printc.error(f'Invalid value "{value}" for conversion from "{from_type}" to "{to_type}"', script_name)
    return value

  def format_value(self, value, format_string):
    """
    Format a value using the specified format string.

    Args:
        value (any): The value to format.
        format_string (str): The format string.

    Returns:
        str: Formatted value as a string.
    """
    if format_string is None:
      return str(value)
    if isinstance(value, list):
      value = "".join(str(v) for v in value)

    try:
      formatted_value = format_string % float(value)
      return formatted_value
    except (TypeError, ValueError):
      if format_string is not None:
        printc.warning(f'Cannot format value "{value}" with format "{format_string}".', script_name)
      return str(value)
