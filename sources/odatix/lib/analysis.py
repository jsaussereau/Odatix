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
What an RTL analysis found, read from what the tool reported.

An analysis runs a tool on a design and reads its logs. Every tool reports in
its own words, so what those words mean is not written here: it is the analysis
definition of the tool ("<tool>/analysis.yml"), read on top of the one every
tool shares ("_common/analysis.yml"). Each message a definition recognizes
becomes a :class:`Finding` -- a severity, a category of a shared vocabulary
(a missing module is the same finding whatever tool reports it), what it is
about, and where -- and the findings of a job make its :class:`AnalysisResult`.

Definitions are resolved like the metrics of a tool (see odatix.lib.metrics):

  1. "_common/analysis.yml", shipped with Odatix;
  2. the "analysis.yml" of every directory defining the tool, those of the tool
     it extends first (a tool extending another one reads its messages alike);
  3. "<tools_path>/<tool>/analysis.yml" in the workspace, which needs no
     tool.yml next to it.

A later file adds to an earlier one: a message rule or a category of the same
name replaces the earlier one, one mapped to nothing removes it, and the
``codes`` table is merged code by code.
"""

import fnmatch
import glob
import os
import re

import odatix.lib.hard_settings as hard_settings
import odatix.lib.printc as printc
import odatix.lib.yaml_loader as yaml_loader

script_name = os.path.basename(__file__)

#: Name of the analysis definition of a tool, in its directory.
ANALYSIS_FILENAME = "analysis.yml"

#: Severities, the most severe first.
SEVERITIES = ("error", "critical", "warning", "info")

#: What an analysis concluded about a design, the most severe first.
STATUS_FAILED = "failed"
STATUS_TOOL_FAILURE = "tool_failure"
STATUS_UNSUPPORTED = "unsupported"
STATUS_INCOMPLETE = "incomplete"
STATUS_WARNING = "warning"
STATUS_PASSED = "passed"
STATUSES = (
  STATUS_FAILED, STATUS_TOOL_FAILURE, STATUS_INCOMPLETE,
  STATUS_WARNING, STATUS_UNSUPPORTED, STATUS_PASSED,
)

#: How each status is named, and what it means.
STATUS_LABELS = {
  STATUS_FAILED: "Failed",
  STATUS_TOOL_FAILURE: "Tool failure",
  STATUS_UNSUPPORTED: "Not supported",
  STATUS_INCOMPLETE: "Incomplete",
  STATUS_WARNING: "Warnings",
  STATUS_PASSED: "Passed",
}
STATUS_DESCRIPTIONS = {
  STATUS_FAILED: "The tool found errors in the design.",
  STATUS_TOOL_FAILURE: "The tool could not analyze the design: the errors are about the tool, not the design.",
  STATUS_UNSUPPORTED: "The design is written in a language the tool does not read.",
  STATUS_INCOMPLETE: "The analysis did not finish: its verdict cannot be trusted.",
  STATUS_WARNING: "The design was analyzed, with warnings.",
  STATUS_PASSED: "The design was analyzed, and the tool reported nothing.",
}

# How the statuses of records written before this module existed are read.
#: The statuses of an analysis whose tool ran to a verdict about the design.
#: Its job succeeded, whatever the verdict: an error in the RTL is a result, not
#: a job that failed (see tool_ran).
VERDICT_STATUSES = (STATUS_FAILED, STATUS_WARNING, STATUS_UNSUPPORTED, STATUS_PASSED)


def tool_ran(status):
  """
  Whether an analysis of this status ran: the tool concluded something about the
  design. False when it could not run or did not finish ("tool_failure",
  "incomplete"), which is what makes its job fail, the same way for every tool.
  """
  return status in VERDICT_STATUSES


_LEGACY_STATUSES = {
  "FAILED": STATUS_FAILED,
  "WARNING": STATUS_WARNING,
  "WARNINGS": STATUS_WARNING,
  "INCOMPLETE": STATUS_INCOMPLETE,
  "PASSED": STATUS_PASSED,
}

#: How many distinct findings a result keeps. Every occurrence is counted, but a
#: design reporting a thousand warnings needs the first of them, not all.
MAX_FINDINGS = 100

#: How many lines following a message are kept with it: the source excerpt a
#: tool prints under an error, and what it says next (where it looked for a
#: missing module...). A longer detail ends with a line saying how many more
#: the log holds.
MAX_DETAIL_LINES = 16

# The markup the Odatix scripts write around their messages ("<bold><red>"),
# which the logs keep, and terminal escape sequences.
_MARKUP = re.compile(
  r"</?(?:bold|end|black|red|green|yellow|blue|magenta|cyan|grey|white|"
  r"l(?:grey|red|green|yellow|blue|magenta|cyan)|error|warning|crit_warning|note|trace)>"
)
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def clean_line(line):
  """A log line without the markup and escape sequences around its text."""
  return _ANSI.sub("", _MARKUP.sub("", line)).rstrip("\r\n")


######################################
# Definitions
######################################

class Category(object):
  """What a finding is about (see "_common/analysis.yml")."""

  def __init__(self, name, label="", description="", scope="design", rank=0):
    self.name = name
    self.label = label or name.replace("_", " ").capitalize()
    self.description = description or ""
    self.scope = scope if scope in ("design", "tool") else "design"
    self.rank = rank

  def to_dict(self):
    return {"label": self.label, "description": self.description, "scope": self.scope}

  def __repr__(self):
    return "<Category {0}>".format(self.name)


class MessageRule(object):
  """
  How one kind of message of a tool is recognized, and what it means.

  The pattern is a regular expression searched in every line of the logs. Its
  named groups say what the finding is about: ``message`` (the text worth
  showing, the whole line otherwise), ``subject`` (the module, signal or file it
  is about), ``file`` and ``line`` (where), ``code`` (the message id of the
  tool, looked up in the ``codes`` table of the definition) and ``severity``
  (the word the tool says it with, looked up in its ``severities`` table), which
  then wins over the severity of the rule. A rule may also say its ``message``
  itself, naming the groups in braces ("Latch inferred for '{subject}'"): a
  message read from a table reads better that way.
  """

  def __init__(self, name, pattern, severity="error", category="other", files=None,
               fallback=False, after=None, subject=None, secondary=False, message=None, heading=None):
    self.name = name
    self.pattern = re.compile(pattern)
    self.severity = severity if severity in SEVERITIES else "error"
    self.category = category or "other"
    self.files = list(files or [])
    self.fallback = bool(fallback)
    #: A consequence of other messages ("failed synthesizing module 'top'"),
    #: only kept when nothing at least as severe explains it.
    self.secondary = bool(secondary)
    self.message = str(message) if message else None
    # The rows of a list under a heading ("design 'top' has the following
    # unloaded port(s)" then "port:top/clk"): the pattern is only tried on the
    # lines right below the heading, until one is not a row.
    self.heading = re.compile(heading) if heading else None
    # Where the subject is in the message, when the pattern does not say it:
    # regular expressions tried in order, the first group of the first one
    # matching.
    self.subject_patterns = [re.compile(pattern) for pattern in _pattern_list(subject)]
    # A message saying where it is, or what about, on the lines below its first
    # one (Genus): the patterns searched in the "within" lines that follow, each
    # filling the fields it captures that the message did not say. A captured
    # "message" completes the message ("Parsing error: Expecting token ';'").
    self.after = None
    if isinstance(after, dict):
      patterns = _pattern_list(after.get("patterns", after.get("pattern")))
      if patterns:
        self.after = ([re.compile(pattern) for pattern in patterns], int(after.get("within", 3)))

  def applies_to(self, relative_path):
    return not self.files or any(fnmatch.fnmatch(relative_path, pattern) for pattern in self.files)

  def __repr__(self):
    return "<MessageRule {0}>".format(self.name)


class Expectation(object):
  """
  A finding that is normal, and needs no attention.

  It is still reported, apart from the others, but it does not count: a design
  whose warnings are all expected passes. Every condition given must hold:

      category, severity, code   equal to the finding's
      subject, file              shell patterns ("u_*", "rtl/legacy/*")
      message                    a regular expression searched in the message
      tools, architectures       shell patterns the tool, or the design
                                 ("Arch/config" or "Arch"), must match one of

  ``reason`` says why it is normal, and is shown with it.
  """

  CONDITIONS = ("category", "severity", "code", "subject", "file", "message", "tools", "architectures")

  def __init__(self, name="", reason="", **conditions):
    self.name = name
    self.reason = str(reason or "")
    self.category = conditions.get("category")
    self.severity = conditions.get("severity")
    self.code = str(conditions["code"]) if conditions.get("code") is not None else None
    self.subject = conditions.get("subject")
    self.file = conditions.get("file")
    message = conditions.get("message")
    self.message = re.compile(message) if message else None
    self.tools = _pattern_list(conditions.get("tools"))
    self.architectures = _pattern_list(conditions.get("architectures"))

  @classmethod
  def from_settings(cls, name, settings):
    settings = settings if isinstance(settings, dict) else {}
    unknown = [key for key in settings if key not in cls.CONDITIONS and key != "reason"]
    if unknown:
      printc.warning('Unknown key(s) in the expected finding "' + str(name) + '": ' + ", ".join(unknown), script_name)
    return cls(name=name, reason=settings.get("reason", ""), **{key: settings.get(key) for key in cls.CONDITIONS})

  def matches(self, finding, tool="", design=""):
    if self.category is not None and finding.category != self.category:
      return False
    if self.severity is not None and finding.severity != self.severity:
      return False
    if self.code is not None and finding.code != self.code:
      return False
    if self.subject is not None and not fnmatch.fnmatchcase(finding.subject or "", str(self.subject)):
      return False
    if self.file is not None and not fnmatch.fnmatchcase(finding.file or "", str(self.file)):
      return False
    if self.message is not None and not self.message.search(finding.message):
      return False
    if self.tools and not any(fnmatch.fnmatchcase(tool or "", pattern) for pattern in self.tools):
      return False
    if self.architectures:
      architecture = (design or "").partition("/")[0]
      if not any(fnmatch.fnmatchcase(design or "", pattern) or fnmatch.fnmatchcase(architecture, pattern)
                 for pattern in self.architectures):
        return False
    return True

  def __repr__(self):
    return "<Expectation {0}>".format(self.name)


def _pattern_list(value):
  if value is None:
    return []
  if isinstance(value, (list, tuple)):
    return [str(item) for item in value]
  return [str(value)]


def read_expectations(value):
  """
  Expected findings, as a settings file gives them: a mapping of named ones,
  or a list (named after their position).
  """
  if isinstance(value, list):
    value = {"expected_" + str(index + 1): settings for index, settings in enumerate(value)}
  if not isinstance(value, dict):
    return []
  expectations = []
  for name, settings in value.items():
    if settings is None:
      continue
    try:
      expectations.append(Expectation.from_settings(name, settings))
    except re.error as e:
      printc.error('Invalid message pattern for the expected finding "' + str(name) + '": ' + str(e), script_name)
  return expectations


class AnalysisDefinition(object):
  """
  How the reports of one tool are read: where, which lines mean what, and in
  which languages the designs it can analyze are written.
  """

  def __init__(self, tool="", data=None, sources=None):
    data = data if isinstance(data, dict) else {}
    self.tool = tool
    #: The files the definition was read from, lowest precedence first.
    self.sources = list(sources or [])

    self.categories = {}
    for rank, (name, settings) in enumerate((data.get("categories") or {}).items()):
      settings = settings if isinstance(settings, dict) else {}
      self.categories[name] = Category(
        name,
        label=settings.get("label", ""),
        description=settings.get("description", ""),
        scope=settings.get("scope", "design"),
        rank=rank,
      )
    if "other" not in self.categories:
      self.categories["other"] = Category("other", rank=len(self.categories))

    languages = data.get("languages")
    #: The languages the tool reads, or None when it reads any.
    self.languages = [str(language) for language in languages] if isinstance(languages, list) else None
    self.language_extensions = {
      str(language): [str(extension).lower() for extension in (extensions or [])]
      for language, extensions in (data.get("language_extensions") or {}).items()
    }

    logs = data.get("logs")
    #: The files its messages are read from, relative to the job directory
    #: (glob patterns).
    self.logs = [str(path) for path in logs] if isinstance(logs, list) and logs else ["log/analysis.log"]

    self.ignore = [re.compile(pattern) for pattern in (data.get("ignore") or []) if pattern]
    continuation = data.get("continuation")
    #: Lines continuing the previous message (its source excerpt, its context).
    self.continuation = re.compile(continuation) if continuation else None

    #: How the tool says each severity ("CRITICAL WARNING": critical), for the
    #: rules capturing it. Compared without case.
    self.severities = {
      str(word).strip().lower(): severity
      for word, severity in (data.get("severities") or {}).items()
      if severity in SEVERITIES
    }

    self.codes = {}
    for code, settings in (data.get("codes") or {}).items():
      if isinstance(settings, str):
        settings = {"category": settings}
      if isinstance(settings, dict):
        self.codes[str(code)] = settings

    rules = []
    for name, settings in (data.get("messages") or {}).items():
      if not isinstance(settings, dict) or not settings.get("pattern"):
        continue
      try:
        rules.append(MessageRule(
          name,
          settings["pattern"],
          severity=settings.get("severity", "error"),
          category=settings.get("category", "other"),
          files=settings.get("files"),
          fallback=settings.get("fallback", False),
          after=settings.get("after"),
          subject=settings.get("subject"),
          secondary=settings.get("secondary", False),
          message=settings.get("message"),
          heading=settings.get("heading"),
        ))
      except re.error as e:
        printc.error('Invalid pattern for the message "' + name + '" of the analysis of "' + str(tool) + '": ' + str(e), script_name)
    # The rules recognizing anything of a kind come after every specific one,
    # whatever file declared them.
    self.rules = [rule for rule in rules if not rule.fallback] + [rule for rule in rules if rule.fallback]

    #: What this tool reports that is normal (see Expectation).
    self.expected = read_expectations(data.get("expected"))

  def category(self, name):
    return self.categories.get(name) or self.categories["other"]

  def ordered_categories(self):
    return sorted(self.categories.values(), key=lambda category: category.rank)

  def __repr__(self):
    return "<AnalysisDefinition {0!r}>".format(self.tool)


#: The keys of a definition holding {name: settings} entries merged one by one.
_NAMED_SECTIONS = ("categories", "messages", "codes", "severities", "language_extensions", "expected")


def merge_definitions(base, override):
  """Merge an analysis definition file over another, and return a new dict."""
  merged = dict(base) if isinstance(base, dict) else {}
  if not isinstance(override, dict):
    return merged
  for key, value in override.items():
    if key in _NAMED_SECTIONS and isinstance(value, dict):
      section = dict(merged.get(key) or {})
      for name, settings in value.items():
        if settings is None:
          section.pop(name, None)
        else:
          section[name] = settings
      merged[key] = section
    elif key == "ignore" and isinstance(value, list):
      merged[key] = list(merged.get(key) or []) + [pattern for pattern in value if pattern not in (merged.get(key) or [])]
    else:
      merged[key] = value
  return merged


def common_definition_file():
  from odatix.lib.settings import OdatixSettings

  return os.path.join(OdatixSettings.odatix_eda_tools_path, hard_settings.common_script_path, ANALYSIS_FILENAME)


def definition_files(tool, tools_path=None):
  """Every file the analysis definition of a tool is read from, lowest precedence first."""
  import odatix.lib.eda_tools as eda_tools
  from odatix.lib.metrics import user_tools_path

  files = []

  def add(path):
    if os.path.isfile(path) and os.path.realpath(path) not in [os.path.realpath(f) for f in files]:
      files.append(path)

  add(common_definition_file())
  for tool_dir in eda_tools.get_tool_dirs(tool) if tool else []:
    add(os.path.join(tool_dir, ANALYSIS_FILENAME))
  for name in eda_tools.tool_lineage(tool) if tool else []:
    add(os.path.join(user_tools_path(tools_path), name, ANALYSIS_FILENAME))
  return files


def _read_definition_file(path):
  try:
    with open(path, "r", encoding="utf-8") as f:
      data = yaml_loader.safe_load(f)
  except Exception as e:
    printc.error('Analysis definition file "' + path + '" is not a valid YAML file: ' + str(e), script_name)
    return {}
  if data is None:
    return {}
  if not isinstance(data, dict):
    printc.error('Analysis definition file "' + path + '" must contain a YAML mapping', script_name)
    return {}
  return data


def load_definition(tool, tools_path=None):
  """
  The analysis definition of a tool, every file defining it merged.

  A file saying ``extends: <tool>`` reads like that tool's definition, on top of
  which it is merged: a tool printing the messages of another one (LibreLane
  running Verilator) says only what differs.
  """
  files = []
  data = {}

  def merge(paths, seen):
    nonlocal data
    for path in paths:
      if os.path.realpath(path) in [os.path.realpath(f) for f in files]:
        continue
      content = _read_definition_file(path)
      base = content.pop("extends", None)
      if base and base not in seen:
        merge([f for f in definition_files(base, tools_path=tools_path) if f != common_definition_file()], seen | {base})
      files.append(path)
      data = merge_definitions(data, content)

  merge(definition_files(tool, tools_path=tools_path), {tool})
  return AnalysisDefinition(tool, data, sources=files)


def load_categories():
  """The shared categories, for whoever shows findings of any tool."""
  return load_definition(None).ordered_categories()


######################################
# Findings
######################################

class Finding(object):
  """One thing the tool reported about a design, however many times it did."""

  FIELDS = ("severity", "category", "message", "subject", "file", "line", "code", "count", "detail",
            "expected", "reason")

  def __init__(self, severity, category, message, subject=None, file=None, line=None, code=None,
               count=1, detail=None, expected=False, reason=None):
    self.severity = severity if severity in SEVERITIES else "error"
    self.category = category or "other"
    self.message = str(message or "").strip()
    # What a finding is about is a signal, not one of its bits.
    self.subject = _BIT_INDEX.sub("", str(subject)) or None if subject not in (None, "") else None
    self.file = str(file) if file not in (None, "") else None
    try:
      self.line = int(line) if line not in (None, "") else None
    except (TypeError, ValueError):
      self.line = None
    self.code = str(code) if code not in (None, "") else None
    self.count = int(count or 1)
    self.detail = list(detail or [])
    #: Whether it is normal (see Expectation), and why.
    self.expected = bool(expected)
    self.reason = str(reason) if reason else None
    #: Whether it only follows from other messages (see MessageRule.secondary).
    self.secondary = False
    #: Detail lines left out while the log is read (see MAX_DETAIL_LINES).
    self.detail_omitted = 0

  @property
  def location(self):
    """"file:line", or what is known of it."""
    if self.file and self.line is not None:
      return "{0}:{1}".format(self.file, self.line)
    return self.file or ""

  def key(self):
    """
    What makes two reports of the same message the same finding. Tools report
    a bus bit by bit ("Port d[7] ...", "Port d[6] ..."): the bits of a signal
    are one finding.
    """
    return (
      self.severity, self.category, self.code, _without_bits(self.subject), self.file, self.line,
      _without_bits(self.message),
    )

  def to_dict(self):
    data = {"severity": self.severity, "category": self.category, "message": self.message}
    for name in ("subject", "file", "line", "code"):
      value = getattr(self, name)
      if value is not None:
        data[name] = value
    if self.count > 1:
      data["count"] = self.count
    if self.detail:
      data["detail"] = list(self.detail)
    if self.expected:
      data["expected"] = True
      if self.reason:
        data["reason"] = self.reason
    return data

  @classmethod
  def from_dict(cls, data):
    data = data if isinstance(data, dict) else {"message": str(data)}
    return cls(**{name: data.get(name) for name in cls.FIELDS if name in data})

  def __repr__(self):
    return "<Finding {0} {1}: {2}>".format(self.severity, self.category, self.message)


def omitted_detail_line(count):
  """The last line of a detail cut short: how many more lines the log holds."""
  return "[{0} more line{1} in the log]".format(count, "" if count == 1 else "s")


_BIT_INDEX = re.compile(r"\[\d+(?:(?::|\.\.)\d+)?\]")


def _without_bits(text):
  return _BIT_INDEX.sub("[*]", text) if text else text


_MESSAGE_FIELD = re.compile(r"\{(\w+)\}")
_FIRST_BIT = re.compile(r"\[(\d+)\]")


def _bit_range(indices):
  """How bits are said: "[15:8]" when they follow each other, "[0,2,5]" otherwise."""
  indices = sorted(indices)
  if indices[-1] - indices[0] + 1 == len(indices):
    return "[{0}:{1}]".format(indices[-1], indices[0])
  shown = ",".join(str(index) for index in indices[:8])
  return "[" + shown + (",…" if len(indices) > 8 else "") + "]"


def _severity_rank(severity):
  return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES)


def sort_findings(findings, definition):
  """The most relevant first: the expected ones last, then by severity, by category, by place."""
  return sorted(
    findings,
    key=lambda finding: (
      finding.expected,
      _severity_rank(finding.severity),
      definition.category(finding.category).rank,
      finding.file or "",
      finding.line if finding.line is not None else 0,
    ),
  )


def _render_message(template, groups):
  return _MESSAGE_FIELD.sub(lambda field: groups.get(field.group(1), ""), template)


def _complete_finding(finding, rule, groups, match):
  """
  Fill what a finding did not say with what a line below it says
  (MessageRule.after). ``groups`` are those of its message, completed.
  """
  found = {name: value for name, value in match.groupdict().items() if value not in (None, "")}
  if finding.subject is None and found.get("subject"):
    finding.subject = Finding("info", None, "", subject=found["subject"]).subject
  if finding.file is None and found.get("file"):
    finding.file = found["file"]
    try:
      finding.line = int(found["line"]) if found.get("line") else finding.line
    except ValueError:
      pass
  for name, value in found.items():
    groups.setdefault(name, value)
  if groups.get("_template"):
    finding.message = _render_message(groups["_template"], groups).strip()
  elif found.get("message"):
    finding.message = finding.message.rstrip(". ") + ": " + found["message"].strip()


class LogReader(object):
  """Reads the logs of one job with a definition, message by message."""

  def __init__(self, definition):
    self.definition = definition
    self.raw = []

  def _finding_from_match(self, rule, match, line):
    groups = {name: value for name, value in match.groupdict().items() if value not in (None, "")}
    severity = self.definition.severities.get(str(groups.get("severity", "")).strip().lower(), rule.severity)
    category = rule.category
    code = groups.get("code")
    if code is not None:
      code = code.strip()
      known = self.definition.codes.get(code)
      if known:
        category = known.get("category", category)
        severity = known.get("severity", severity)
    secondary = rule.secondary
    template = rule.message
    if code is not None and self.definition.codes.get(code):
      secondary = bool(self.definition.codes[code].get("secondary", secondary))
      template = self.definition.codes[code].get("message", template)
    groups["_template"] = template
    if template:
      message = _render_message(template, groups)
    else:
      message = groups.get("message", line.strip())
    subject = groups.get("subject")
    if subject is None:
      for pattern in rule.subject_patterns:
        found = pattern.search(message)
        if found and found.groups() and found.group(1):
          subject = found.group(1)
          break
    finding = Finding(
      severity, category, message,
      subject=subject, file=groups.get("file"), line=groups.get("line"), code=code,
    )
    finding.secondary = secondary
    return finding, groups

  def read(self, path, relative_path):
    rules = [rule for rule in self.definition.rules if rule.applies_to(relative_path)]
    try:
      with open(path, "r", errors="ignore", encoding="utf-8") as f:
        lines = [clean_line(line) for line in f]
    except OSError:
      return

    current = None   # the finding the next continuation lines belong to
    pending = None   # [finding, rule, groups, patterns still to find, lines left] (MessageRule.after)
    listing = set()  # the rules whose heading the lines are below (MessageRule.heading)
    for line in lines:
      if not line.strip():
        continue

      if pending is not None:
        finding, rule, groups, patterns, left = pending
        for pattern in list(patterns):
          match = pattern.search(line)
          if match:
            _complete_finding(finding, rule, groups, match)
            patterns.remove(pattern)
        if not patterns or left <= 1:
          pending = None
        else:
          pending[4] = left - 1

      if any(pattern.search(line) for pattern in self.definition.ignore):
        current = None
        continue

      continuation = self.definition.continuation
      if current is not None and continuation is not None and continuation.search(line):
        if len(current.detail) < MAX_DETAIL_LINES:
          current.detail.append(line.rstrip())
        else:
          current.detail_omitted += 1
        continue

      current = None
      headings = set(rule for rule in rules if rule.heading is not None and rule.heading.search(line))
      if headings:
        listing = headings
        continue
      # A list ends at its first line that is not one of its rows.
      listing = set(rule for rule in listing if rule.pattern.search(line))
      for rule in rules:
        if rule.heading is not None and rule not in listing:
          continue
        match = rule.pattern.search(line)
        if match is None:
          continue
        current, groups = self._finding_from_match(rule, match, line)
        self.raw.append(current)
        pending = [current, rule, groups, list(rule.after[0]), rule.after[1]] if rule.after is not None else None
        break

  def results(self):
    """The distinct findings, in the order they were first reported."""
    for finding in self.raw:
      if finding.detail_omitted:
        finding.detail.append(omitted_detail_line(finding.detail_omitted))
        finding.detail_omitted = 0
    merged = {}
    bits = {}
    findings = []
    for finding in self.raw:
      key = finding.key()
      bit = _FIRST_BIT.search(finding.message)
      if bit:
        bits.setdefault(key, set()).add(int(bit.group(1)))
      if key in merged:
        merged[key].count += finding.count
        continue
      merged[key] = finding
      findings.append(finding)
    # Several bits of a signal are one finding, about these bits: "d[15:8]".
    for key, indices in bits.items():
      if len(indices) > 1:
        merged[key].message = _FIRST_BIT.sub(_bit_range(indices), merged[key].message, count=1)
    return findings


######################################
# Results
######################################

#: How each language is named in a report.
LANGUAGE_LABELS = {"verilog": "Verilog", "systemverilog": "SystemVerilog", "vhdl": "VHDL"}


def detect_languages(rtl_dir, definition):
  """The languages the sources of a design are written in."""
  extensions = {}
  for language, language_extensions in definition.language_extensions.items():
    for extension in language_extensions:
      extensions[extension] = language
  languages = set()
  for root, _dirs, files in os.walk(rtl_dir):
    for filename in files:
      language = extensions.get(os.path.splitext(filename)[1].lower())
      if language is not None:
        languages.add(language)
  return sorted(languages)


def _job_settings(job_dir):
  """The settings a job directory was prepared with (its settings.yml)."""
  path = os.path.join(job_dir, hard_settings.yaml_config_filename)
  try:
    with open(path, "r", encoding="utf-8") as f:
      data = yaml_loader.safe_load(f)
  except Exception:
    return {}
  return data if isinstance(data, dict) else {}


def _relative_to(path, job_dir):
  """
  A path the tool printed, relative to the job directory when it is in it,
  with "/" separators whatever the system, like a path the tool printed
  relative to it.
  """
  if not path or not os.path.isabs(path):
    return path
  job_dir = os.path.realpath(job_dir)
  real = os.path.realpath(path)
  if real == job_dir or real.startswith(job_dir + os.sep):
    return os.path.relpath(real, job_dir).replace(os.sep, "/")
  return path


def is_complete(job_dir):
  """
  Whether the analysis of a job reached its completion marker: the tool scripts
  write "Done: 100%" to the status file at the very end of their flow. Without
  it (the job was stopped, the tool died) its verdict cannot be trusted.
  """
  status_file = os.path.join(job_dir, hard_settings.work_log_path, hard_settings.synth_status_filename)
  try:
    with open(status_file, "r", errors="ignore", encoding="utf-8") as f:
      return hard_settings.valid_status in f.read()
  except OSError:
    return False


class AnalysisResult(object):
  """What the analysis of one design with one tool concluded."""

  def __init__(self, tool, architecture, configuration="", flow=None, status=STATUS_PASSED,
               findings=None, counts=None, omitted=0, languages=None, logs=None, note=""):
    self.tool = str(tool or "")
    self.architecture = str(architecture or "")
    self.configuration = str(configuration or "")
    self.flow = flow or None
    self.status = status
    self.findings = list(findings or [])
    #: Occurrences by severity of what needs attention, every one of them, the
    #: omitted ones included; and, under "expected", those that are normal.
    self.counts = dict(counts) if counts else self._count(self.findings)
    #: Distinct findings left out (see MAX_FINDINGS).
    self.omitted = int(omitted or 0)
    self.languages = list(languages or [])
    self.logs = list(logs or [])
    #: Why the status is what it is, when the findings do not say it.
    self.note = note or ""

  @staticmethod
  def _count(findings):
    counts = {severity: 0 for severity in SEVERITIES}
    counts["expected"] = 0
    for finding in findings:
      key = "expected" if finding.expected else finding.severity
      counts[key] = counts.get(key, 0) + finding.count
    return counts

  @property
  def attention(self):
    """The findings that need attention: those that are not expected."""
    return [finding for finding in self.findings if not finding.expected]

  @property
  def expected(self):
    """The findings that are normal (see Expectation)."""
    return [finding for finding in self.findings if finding.expected]

  @property
  def name(self):
    """
    "Architecture/configuration", or the architecture alone for one without
    configurations (which Odatix runs as its own configuration).
    """
    if not self.configuration or self.configuration == self.architecture:
      return self.architecture
    return self.architecture + "/" + self.configuration

  @property
  def summary(self):
    """The one line saying what matters most about this design."""
    finding = self.main_finding
    return finding.message if finding is not None else self.note

  @property
  def main_finding(self):
    """The most relevant finding that needs attention, if any."""
    if self.status in (STATUS_UNSUPPORTED, STATUS_INCOMPLETE):
      return None
    attention = self.attention
    return attention[0] if attention else None

  def count(self, severity):
    return int(self.counts.get(severity, 0) or 0)

  def categories(self):
    """{category: occurrences}, for the findings it kept."""
    counts = {}
    for finding in self.findings:
      counts[finding.category] = counts.get(finding.category, 0) + finding.count
    return counts

  ######################################
  # As a record of a results file
  ######################################

  def to_record(self, results_schema):
    meta = {
      results_schema.META_TYPE: TYPE_ANALYSIS,
      results_schema.META_TOOL: self.tool,
      results_schema.META_ARCHITECTURE: self.architecture,
      results_schema.META_CONFIGURATION: self.configuration,
      # Informational: neither dimensions nor part of the record identity, so a
      # design analyzed again replaces its record whatever it concluded.
      "_status": self.status,
    }
    if self.flow:
      meta[results_schema.META_FLOW] = str(self.flow)
    if self.summary:
      meta["_summary"] = self.summary
    if self.note:
      meta["_note"] = self.note
    if self.findings:
      meta["_findings"] = [finding.to_dict() for finding in self.findings]
    if self.omitted:
      meta["_findings_omitted"] = self.omitted
    if self.languages:
      meta["_languages"] = list(self.languages)
    if self.logs:
      meta["_logs"] = list(self.logs)

    metrics = {
      "error_count": self.count("error"),
      "critical_warning_count": self.count("critical"),
      "warning_count": self.count("warning"),
      "info_count": self.count("info"),
      "expected_count": self.count("expected"),
    }
    return results_schema.make_record(meta, metrics)

  @classmethod
  def from_record(cls, record):
    """A result from its record, the records written by earlier versions included."""
    meta = record.get("meta", {}) if isinstance(record, dict) else {}
    metrics = record.get("metrics", {}) if isinstance(record, dict) else {}
    status = str(meta.get("_status", "") or "")
    status = _LEGACY_STATUSES.get(status, status.lower())
    if status not in STATUSES:
      status = STATUS_INCOMPLETE

    if "_findings" in meta:
      findings = [Finding.from_dict(data) for data in meta.get("_findings") or []]
      counts = {severity: int(metrics.get(severity_metric(severity), 0) or 0) for severity in SEVERITIES}
      counts["expected"] = int(metrics.get("expected_count", 0) or 0)
      logs = meta.get("_logs") or []
    else:
      # Written before findings had a severity and a category: what they said
      # is kept as it was.
      findings = [Finding("error", "other", message) for message in meta.get("_errors") or []]
      if not findings and meta.get("_error_message"):
        findings = [Finding("error", "other", meta["_error_message"])]
      findings += [Finding("critical", "missing_module", message) for message in meta.get("_critical_warnings") or []]
      counts = {
        "error": int(metrics.get("error_count", 0) or 0),
        "critical": int(metrics.get("critical_warning_count", 0) or 0),
        "warning": int(metrics.get("standard_warning_count", 0) or 0),
        "info": 0,
        "expected": 0,
      }
      logs = [meta["_log_file"]] if meta.get("_log_file") else []

    return cls(
      tool=meta.get("tool", ""),
      architecture=meta.get("architecture", ""),
      configuration=meta.get("configuration", ""),
      flow=meta.get("flow"),
      status=status,
      findings=findings,
      counts=counts,
      omitted=meta.get("_findings_omitted", 0),
      languages=meta.get("_languages") or [],
      logs=logs,
      note=meta.get("_note", ""),
    )

  def __repr__(self):
    return "<AnalysisResult {0} {1}: {2}>".format(self.tool, self.name, self.status)


#: Result type of analysis records in a results file.
TYPE_ANALYSIS = "analysis"

#: The results file of the analyses of a tool is "results_analysis_<tool>.yml".
RESULTS_FILE_PREFIX = "results_analysis_"


def results_filename(tool):
  """The results file of the analyses of a tool, in the result directory of a workspace."""
  return RESULTS_FILE_PREFIX + str(tool) + ".yml"


def read_results(result_path, tools=None, designs=None):
  """
  The analyses recorded in the result directory of a workspace: what
  "odatix results analysis" and the RTL analysis page of Odatix Explorer show.

  Args:
      result_path (str): the result directory ("result_path" of odatix.yml,
          ``workspace.paths.result_path``).
      tools (list): only the analyses of these tools (default: every tool).
      designs (list): only these designs, as "Architecture" or
          "Architecture/configuration", shell-style wildcards allowed
          ("Counter/*").

  Returns:
      list: :class:`AnalysisResult` objects, by tool then design. Each has a
      ``status`` (see STATUSES and STATUS_LABELS), a one-line ``summary``, its
      ``findings`` and ``counts`` by severity.

  Example::

      import odatix.lib.analysis as analysis
      for result in analysis.read_results(ws.paths.result_path):
          print(result.tool, result.name, result.status, result.summary)
  """
  import odatix.lib.results_cache as results_cache

  if not result_path or not os.path.isdir(str(result_path)):
    return []
  if tools is not None:
    tools = [tools] if isinstance(tools, str) else list(tools)
  patterns = None
  if designs is not None:
    patterns = [designs] if isinstance(designs, str) else [str(design) for design in designs]

  results = []
  for path in sorted(glob.glob(os.path.join(str(result_path), RESULTS_FILE_PREFIX + "*.yml"))):
    tool = os.path.basename(path)[len(RESULTS_FILE_PREFIX):-len(".yml")]
    if tools is not None and tool not in tools:
      continue
    _units, records = results_cache.load(path)
    for record in records:
      meta = record.get("meta", {}) if isinstance(record, dict) else {}
      if str(meta.get("type", "")).lower() != TYPE_ANALYSIS:
        continue
      result = AnalysisResult.from_record(record)
      if patterns is not None and not any(
        fnmatch.fnmatchcase(result.name, pattern)
        or fnmatch.fnmatchcase(result.architecture + "/" + result.configuration, pattern)
        or fnmatch.fnmatchcase(result.architecture, pattern)
        for pattern in patterns
      ):
        continue
      results.append(result)
  results.sort(key=lambda result: (result.tool, result.name.lower(), result.flow or ""))
  return results


def count_by_status(results):
  """{status: how many results have it}, every status included."""
  counts = {status: 0 for status in STATUSES}
  for result in results:
    counts[result.status] = counts.get(result.status, 0) + 1
  return counts


def severity_metric(severity):
  """The metric counting the findings of a severity."""
  return {
    "error": "error_count",
    "critical": "critical_warning_count",
    "warning": "warning_count",
    "info": "info_count",
  }.get(severity, severity + "_count")


def conclude(findings, definition, complete, unsupported_languages=None):
  """
  The status of a design, from what was found about it. The expected findings
  do not count: a design whose findings are all normal passes.
  """
  if unsupported_languages:
    return STATUS_UNSUPPORTED
  findings = [finding for finding in findings if not finding.expected]
  errors = [finding for finding in findings if finding.severity == "error"]
  if any(definition.category(finding.category).scope == "design" for finding in errors):
    return STATUS_FAILED
  if errors:
    return STATUS_TOOL_FAILURE
  if not complete:
    return STATUS_INCOMPLETE
  if any(finding.severity in ("critical", "warning") for finding in findings):
    return STATUS_WARNING
  return STATUS_PASSED


def mark_expected(findings, expectations, tool="", design=""):
  """Mark the findings the first matching expectation says are normal."""
  for finding in findings:
    for expectation in expectations:
      if expectation.matches(finding, tool=tool, design=design):
        finding.expected = True
        finding.reason = expectation.reason or None
        break
  return findings


def analyze_job(job_dir, tool, architecture="", configuration="", flow=None, definition=None, expected=None):
  """
  What the analysis of one job found, read from its directory.

  Args:
      expected (list): Expectation objects on top of those of the tool's
          definition: what the run settings say is normal for these designs.

  Returns:
      AnalysisResult, or None when the directory is not there.
  """
  if not os.path.isdir(job_dir):
    return None
  definition = definition if definition is not None else load_definition(tool)

  logs = []
  reader = LogReader(definition)
  for pattern in definition.logs:
    for path in sorted(glob.glob(os.path.join(job_dir, pattern))):
      if os.path.isfile(path):
        logs.append(os.path.realpath(path))
        reader.read(path, os.path.relpath(path, job_dir))
  # A tool that could not even start (no license, not installed) wrote no log
  # of its own: why it failed is only in what the job printed.
  if not logs:
    console = os.path.join(job_dir, hard_settings.work_log_path, hard_settings.console_log_filename)
    if os.path.isfile(console):
      logs.append(os.path.realpath(console))
      reader.read(console, os.path.relpath(console, job_dir))

  design = architecture + ("/" + configuration if configuration else "")
  findings = reader.results()
  # What only follows from other messages is left out when one at least as
  # severe is there: it says nothing more.
  ranks = [_severity_rank(finding.severity) for finding in findings if not finding.secondary]
  if ranks:
    findings = [finding for finding in findings if not (finding.secondary and _severity_rank(finding.severity) >= min(ranks))]
  top_level_module = _job_settings(job_dir).get("top_level_module")
  job_prefix = os.path.realpath(job_dir) + os.sep
  for finding in findings:
    finding.file = _relative_to(finding.file, job_dir)
    finding.message = finding.message.replace(job_prefix, "")
    if finding.subject:
      finding.subject = finding.subject.replace(job_prefix, "")
    # A missing module that is the top level is a top level the sources do
    # not hold, which few tools tell apart.
    if finding.category == "missing_module" and top_level_module and finding.subject == top_level_module:
      finding.category = "missing_top"
  findings = mark_expected(findings, list(expected or []) + definition.expected, tool=tool, design=design)
  findings = sort_findings(findings, definition)
  counts = AnalysisResult._count(findings)
  omitted = max(0, len(findings) - MAX_FINDINGS)
  findings = findings[:MAX_FINDINGS]

  languages = detect_languages(os.path.join(job_dir, hard_settings.work_rtl_path), definition)
  unsupported = []
  if definition.languages is not None:
    unsupported = [language for language in languages if language not in definition.languages]

  complete = is_complete(job_dir)
  status = conclude(findings, definition, complete, unsupported)
  if status == STATUS_UNSUPPORTED:
    # What the tool said about a language it does not read is no finding.
    findings, counts, omitted = [], AnalysisResult._count([]), 0

  note = ""
  if status == STATUS_UNSUPPORTED:
    note = "{0} does not read {1}".format(tool, " or ".join(LANGUAGE_LABELS.get(language, language) for language in unsupported))
  elif status == STATUS_INCOMPLETE:
    note = "The analysis did not finish" + ("" if logs else " (no log written)")
  elif not logs and status == STATUS_PASSED:
    status = STATUS_INCOMPLETE
    note = "No analysis log found"

  return AnalysisResult(
    tool=tool,
    architecture=architecture,
    configuration=configuration,
    flow=flow,
    status=status,
    findings=findings,
    counts=counts,
    omitted=omitted,
    languages=languages,
    logs=logs,
    note=note,
  )
