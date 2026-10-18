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
The terminal report of an RTL analysis.

It is built from analysis results alone (see odatix.lib.analysis), whatever
tools produced them: nothing here knows any tool. It answers, in that order,
what a user wants to know after an analysis:

  1. how each design fared with each tool (a matrix, when there are several);
  2. what kinds of problems were found, and by which tool (a category table:
     the same RTL is often accepted by one tool and refused by another);
  3. what to fix first: one line per design that is not clean, saying its most
     relevant finding and where it is;
  4. what was found that is normal (the expected findings), apart, so that it
     is plain whether what remains deserves attention.
"""

import os
import re
import shutil

import odatix.lib.analysis as analysis
from odatix.lib.printc import colors

#: How each status is drawn.
STATUS_STYLE = {
  analysis.STATUS_FAILED: ("✗", colors.RED),
  analysis.STATUS_TOOL_FAILURE: ("!", colors.MAGENTA),
  analysis.STATUS_INCOMPLETE: ("?", colors.MAGENTA),
  analysis.STATUS_WARNING: ("⚠", colors.YELLOW),
  analysis.STATUS_UNSUPPORTED: ("–", colors.GREY),
  analysis.STATUS_PASSED: ("✓", colors.GREEN),
}

#: Statuses given a line per design, in that order.
DETAILED_STATUSES = (
  analysis.STATUS_FAILED, analysis.STATUS_TOOL_FAILURE,
  analysis.STATUS_INCOMPLETE, analysis.STATUS_WARNING,
)

#: Above this many designs, the matrix is left out: the totals and the lines
#: below it say the same, readably.
MAX_MATRIX_ROWS = 40

#: How many designs of a status get a line of their own.
MAX_LINES_PER_STATUS = 25

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def visible_length(text):
  return len(_ANSI.sub("", text))


def pad(text, width):
  return text + " " * max(0, width - visible_length(text))


def truncate(text, width):
  text = str(text)
  return text if len(text) <= width else text[:max(0, width - 1)] + "…"


def glyph(status):
  symbol, color = STATUS_STYLE.get(status, ("?", colors.ENDC))
  return color + symbol + colors.ENDC


def _tools(results):
  return sorted({result.tool for result in results})


def _designs(results):
  return sorted({result.name for result in results}, key=str.lower)


def _plural(count, word, plural=None):
  return "{0} {1}".format(count, word if count == 1 else (plural or word + "s"))


def _status_totals(results):
  totals = {status: 0 for status in analysis.STATUSES}
  for result in results:
    totals[result.status] = totals.get(result.status, 0) + 1
  return totals


def _totals_line(results):
  totals = _status_totals(results)
  parts = []
  for status in analysis.STATUSES:
    if totals[status]:
      parts.append(glyph(status) + " " + str(totals[status]) + " " + analysis.STATUS_LABELS[status].lower())
  return "   ".join(parts)


######################################
# Sections
######################################

def _header(results, tools):
  designs = _designs(results)
  title = "RTL ANALYSIS"
  subtitle = _plural(len(designs), "design") + ", " + _plural(len(tools), "tool") + ": " + ", ".join(tools)
  return [
    colors.CYAN + "=" * 72 + colors.ENDC,
    " " + colors.BOLD + colors.CYAN + title + colors.ENDC + "  " + subtitle,
    colors.CYAN + "=" * 72 + colors.ENDC,
  ]


def _matrix(results, tools, width):
  by_design = {}
  for result in results:
    by_design.setdefault(result.name, {})[result.tool] = result.status
  designs = _designs(results)
  column = max(9, max(len(tool) for tool in tools) + 2)
  name_width = min(max(len(name) for name in designs) + 2, max(20, width - column * len(tools) - 4))

  lines = [" " + pad(colors.BOLD + "Design" + colors.ENDC, name_width) + "".join(
    colors.BOLD + tool.center(column) + colors.ENDC for tool in tools
  )]
  for name in designs:
    cells = ""
    for tool in tools:
      status = by_design[name].get(tool)
      cell = glyph(status) if status else colors.GREY + "·" + colors.ENDC
      left = (column - 1) // 2
      cells += " " * left + cell + " " * (column - 1 - left)
    lines.append(" " + pad(truncate(name, name_width - 2), name_width) + cells)
  return lines


def _totals(results, tools):
  if len(tools) == 1:
    return [" " + _totals_line(results)]
  name_width = max(len(tool) for tool in tools) + 2
  return [
    " " + pad(tool, name_width) + _totals_line([result for result in results if result.tool == tool])
    for tool in tools
  ]


def _category_table(results, tools, categories):
  """
  How many designs each kind of finding was reported for, by each tool. Only
  what matters is counted: the findings a tool rates as info are left out.
  """
  designs = {}  # (category, tool) -> set of designs
  for result in results:
    if result.status == analysis.STATUS_UNSUPPORTED:
      continue
    for finding in result.attention:
      if finding.severity == "info":
        continue
      designs.setdefault((finding.category, result.tool), set()).add(result.name)
  if not designs:
    return []

  listed = [category for category in categories if any((category.name, tool) in designs for tool in tools)]
  label_width = max(len(category.label) for category in listed) + 4
  column = max(9, max(len(tool) for tool in tools) + 2)
  lines = [" " + pad(colors.BOLD + "Findings" + colors.ENDC, label_width) + "".join(
    colors.BOLD + tool.center(column) + colors.ENDC for tool in tools
  )]
  for category in listed:
    row = " " + pad(category.label, label_width)
    for tool in tools:
      count = len(designs.get((category.name, tool), ()))
      cell = (str(count) if count else "·").center(column)
      row += cell if count else colors.GREY + cell + colors.ENDC
    lines.append(row)
  lines.append(" " + colors.GREY + "(designs each finding was reported for)" + colors.ENDC)
  return lines


def _finding_text(result):
  finding = result.main_finding
  if finding is None:
    return result.summary or analysis.STATUS_DESCRIPTIONS[result.status], ""
  text = finding.message
  others = len(result.attention) - 1 + result.omitted
  if others > 0:
    text += colors.GREY + "  (+" + _plural(others, "other") + ")" + colors.ENDC
  return text, finding.location


def _details(results, tools, width):
  lines = []
  multi_tool = len(tools) > 1
  for status in DETAILED_STATUSES:
    selected = sorted(
      [result for result in results if result.status == status],
      key=lambda result: (result.name.lower(), result.tool),
    )
    if not selected:
      continue
    symbol, color = STATUS_STYLE[status]
    lines.append("")
    lines.append(" " + color + colors.BOLD + symbol + " " + analysis.STATUS_LABELS[status] + colors.ENDC
                 + colors.GREY + " (" + str(len(selected)) + ")" + colors.ENDC)
    name_width = min(max(len(result.name) + (len(result.tool) + 3 if multi_tool else 0) for result in selected) + 2, 40)
    for result in selected[:MAX_LINES_PER_STATUS]:
      label = result.name + (colors.GREY + " · " + result.tool + colors.ENDC if multi_tool else "")
      text, location = _finding_text(result)
      room = max(20, width - name_width - 6 - (len(location) + 2 if location else 0))
      if visible_length(text) > room:
        text = truncate(_ANSI.sub("", text), room)
      line = "   " + pad(label, name_width) + text
      if location:
        line += "  " + colors.CYAN + location + colors.ENDC
      lines.append(line)
    if len(selected) > MAX_LINES_PER_STATUS:
      lines.append("   " + colors.GREY + "… and " + str(len(selected) - MAX_LINES_PER_STATUS) + " more" + colors.ENDC)
  return lines


def _expected(results):
  """
  The expected findings, grouped by what they are and why they are normal:
  one line per group, saying how many designs it concerns.
  """
  groups = {}
  for result in results:
    for finding in result.expected:
      key = (finding.category, finding.reason or "")
      group = groups.setdefault(key, {"count": 0, "designs": set(), "tools": set()})
      group["count"] += finding.count
      group["designs"].add((result.name, result.tool))
      group["tools"].add(result.tool)
  if not groups:
    return []

  categories = {category.name: category for category in analysis.load_categories()}
  total = sum(group["count"] for group in groups.values())
  lines = ["", " " + colors.GREY + colors.BOLD + "○ Expected" + colors.ENDC
           + colors.GREY + " (" + str(total) + ", not counted)" + colors.ENDC]
  for (category, reason), group in sorted(groups.items(), key=lambda item: -item[1]["count"]):
    label = categories[category].label if category in categories else category
    line = "   " + pad(label, 24) + colors.GREY + "×" + str(group["count"]) + " in " + _plural(len(group["designs"]), "design")
    line += " (" + ", ".join(sorted(group["tools"])) + ")" + colors.ENDC
    if reason:
      line += colors.GREY + ": " + reason + colors.ENDC
    lines.append(line)
  return lines


def _unsupported(results):
  """Designs a tool does not read, grouped by why: one line per reason."""
  groups = {}
  for result in results:
    if result.status == analysis.STATUS_UNSUPPORTED:
      groups.setdefault(result.summary, []).append(result.name)
  lines = []
  for note, names in sorted(groups.items()):
    if not lines:
      lines.append("")
    lines.append(" " + glyph(analysis.STATUS_UNSUPPORTED) + " " + note + ": "
                 + colors.GREY + ", ".join(sorted(names, key=str.lower)) + colors.ENDC)
  return lines


######################################
# The report
######################################

def render(results, categories=None, width=None, hints=True):
  """
  The report of a set of analysis results, as lines (with colors).

  Args:
      results (list): AnalysisResult objects, of one or several tools.
      categories (list): the categories, in order of relevance (the shared
          ones when not given).
  """
  results = list(results)
  if not results:
    return [colors.YELLOW + "No analysis result to report." + colors.ENDC]
  width = width or shutil.get_terminal_size((100, 24)).columns
  categories = categories if categories is not None else analysis.load_categories()
  tools = _tools(results)

  lines = _header(results, tools)
  if len(tools) > 1 and len(_designs(results)) <= MAX_MATRIX_ROWS:
    lines += [""] + _matrix(results, tools, width)
  lines += [""] + _totals(results, tools)

  table = _category_table(results, tools, categories)
  if table:
    lines += [""] + table

  lines += _details(results, tools, width)
  lines += _expected(results)
  lines += _unsupported(results)

  if hints:
    lines.append("")
    lines.append(" " + colors.GREY + "Every finding of every design: odatix-explorer, RTL analysis page." + colors.ENDC)
  return lines


def print_report(results, **kwargs):
  print()
  for line in render(results, **kwargs):
    print(line)
  print()


######################################
# Collecting the results of a work directory
######################################

def _read_identity(path):
  try:
    with open(path, "r") as f:
      return f.read().strip()
  except OSError:
    return ""


def job_identity(job_dir):
  """(architecture, configuration, flow) a job directory says it holds."""
  import odatix.lib.hard_settings as hard_settings

  name = _read_identity(os.path.join(job_dir, hard_settings.arch_filename))
  architecture, _, configuration = name.partition("/")
  flow = _read_identity(os.path.join(job_dir, hard_settings.flow_filename)) or None
  return architecture, configuration, flow


def job_directories(analysis_root, tools=None):
  """
  Every analysis job directory under the analysis work directory, with the
  tool that ran it: {job directory: (tool, flow of its work sub-directory)}.
  A job directory is one holding the file naming its architecture.
  """
  import odatix.lib.eda_tools as eda_tools
  import odatix.lib.hard_settings as hard_settings

  jobs = {}
  if not os.path.isdir(analysis_root):
    return jobs
  for tool_dirname in sorted(os.listdir(analysis_root)):
    tool_root = os.path.join(analysis_root, tool_dirname)
    if not os.path.isdir(tool_root):
      continue
    tool, flow = eda_tools.split_tool_work_dirname(tool_dirname)
    if tools and tool not in tools:
      continue
    for root, dirs, files in os.walk(tool_root):
      if hard_settings.arch_filename in files:
        jobs[root] = (tool, flow)
        dirs[:] = []
  return jobs


def collect_results(jobs, expected=None):
  """
  The results of job directories ({job directory: (tool, flow)}), each read
  with the definition of its tool. ``expected`` is what the run settings say is
  normal (Expectation objects).
  """
  definitions = {}
  results = []
  for job_dir, (tool, dir_flow) in sorted(jobs.items()):
    if tool not in definitions:
      definitions[tool] = analysis.load_definition(tool)
    architecture, configuration, flow = job_identity(job_dir)
    if not (flow or dir_flow):
      # A job prepared before its flow was written down ran the default one.
      import odatix.lib.eda_tools as eda_tools

      flow = eda_tools.get_default_flow(tool, job_type="analysis")
    result = analysis.analyze_job(
      job_dir, tool,
      architecture=architecture or os.path.basename(job_dir),
      configuration=configuration,
      flow=flow or dir_flow,
      definition=definitions[tool],
      expected=expected,
    )
    if result is not None:
      results.append(result)
  return results


def run_results(run):
  """
  What the analyses a run launched found: the results of its jobs, read from
  their directories with what its settings file says is expected. The jobs it
  left alone (already done) are not in it: "analysis.read_results" reads every
  recorded analysis.

  Args:
      run: an analysis :class:`odatix.run.Run`, once started (its jobs are known).

  Returns:
      list: AnalysisResult objects.
  """
  from odatix.components.run_analysis import read_run_expectations

  job_dirs = {os.path.realpath(instance.tmp_dir) for _build_job, instance in (run.jobs or [])}
  jobs = {
    job_dir: tool_flow
    for job_dir, tool_flow in job_directories(run.work_path).items()
    if os.path.realpath(job_dir) in job_dirs
  }
  return collect_results(jobs, expected=analysis.read_expectations(read_run_expectations(run.settings_file)))
