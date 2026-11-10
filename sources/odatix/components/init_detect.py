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
"odatix init --detect [PATH]": describe an existing HDL project as an
architecture of the workspace, from what odatix.lib.project_detect finds.

What is written:
 - the workspace settings, when the current directory holds none (and the
   default tool, when it names none and a synthesis tool is installed);
 - "odatix_filelist.f" at the root of the RTL directory of the design: the
   sources in compilation order, include directories and macros, so that
   every tool reads the same thing (the RTL itself is never copied or changed);
 - the architecture (its name: the top level, unless --name gives one), and
   with --parameters one parameter domain per parameter of the top level.
"""

import json
import os
import sys

import odatix.lib.printc as printc
import odatix.lib.project_detect as project_detect
import odatix.lib.rtl_generation as rtl_generation

script_name = "init"

FILELIST_NAME = "odatix_filelist.f"
FILELIST_MARK = project_detect.GENERATED_FILELIST_MARK
#: Variable naming the project root, for files outside the RTL directory.
PROJECT_VARIABLE = "ODATIX_PROJECT_DIR"

######################################
# Report
######################################

def _rel(path, root):
    return project_detect._relative(path, root)


def _finding(label, finding, missing="not found"):
    if finding is None:
        printc.say("  {0:<14}{1}".format(label, missing), color=printc.colors.YELLOW)
        return
    text = "  {0:<14}{1}".format(label, finding.value)
    detail = finding.origin
    if finding.alternatives:
        detail += "; also possible: " + ", ".join(finding.alternatives[:4])
    printc.say(text + "  ({0})".format(detail), color=printc.colors.YELLOW if finding.confidence == "guessed" else printc.colors.ENDC)


def report(detection):
    root = detection.root
    printc.subheader("Project " + root)
    printc.say("  {0:<14}{1}".format("sources", detection.origin))
    for declared in detection.declarations[1:4]:
        printc.grey("  {0:<14}also declared by {1} ({2} files)".format("", _rel(declared.path, root), len(declared.files)))
    printc.say("  {0:<14}{1} ({2})".format("files", len(detection.files), ", ".join(detection.languages) or "none"))
    if detection.include_dirs:
        printc.say("  {0:<14}{1}".format("include dirs", ", ".join(_rel(d, root) for d in detection.include_dirs[:6])
                                         + (" ..." if len(detection.include_dirs) > 6 else "")))
    if detection.defines:
        printc.say("  {0:<14}{1}".format("macros", " ".join(detection.defines)))
    _finding("top level", detection.top)
    if detection.top_file:
        printc.say("  {0:<14}{1}".format("top file", _rel(detection.top_file, detection.generated_dir or root)))
    _finding("clock", detection.clock)
    _finding("reset", detection.reset)
    if detection.parameters:
        count = len(detection.parameters)
        printc.say("  {0:<14}{1}{2}".format("parameters", ", ".join(
            "{0}={1}".format(p.name, p.value.strip()) for p in detection.parameters[:8]),
            " ... ({0} in all, listed by --json)".format(count) if count > 8 else ""))
    if detection.optional_macros:
        printc.say("  {0:<14}{1}".format("optional", ", ".join(detection.optional_macros[:10])
                                         + "  (tested, never defined: add the ones you want with \"defines\")"))
    if detection.undefined_macros:
        printc.warning("macros used but defined nowhere: " + ", ".join(detection.undefined_macros), script_name)
    if detection.black_boxes:
        printc.warning("modules defined nowhere (black boxes): " + ", ".join(detection.black_boxes[:10]), script_name)
    if detection.duplicates:
        names = sorted(detection.duplicates)
        printc.note("{0} module(s) defined by several files, the one nearest the design used: {1}{2}".format(
            len(names), ", ".join(names[:8]), " ..." if len(names) > 8 else ""), script_name)
    generation = detection.generator
    if generation is not None:
        printc.say("  {0:<14}{1} ({2})".format("generator", generation.name, generation.file))
        printc.say("  {0:<14}{1}".format("command", generation.command))
        if detection.generated_dir:
            printc.say("  {0:<14}{1} ({2} file(s), {3:.0f} s)".format(
                "output", generation.output or ".", len(generation.generated), generation.duration))
        if generation.error:
            printc.say("  {0:<14}{1}".format("generation", generation.error), color=printc.colors.RED)
    printc.say("  {0:<14}{1}".format("tools", ", ".join(detection.tools) or "none found in PATH"))
    if detection.pdks:
        printc.say("  {0:<14}{1}".format("PDK", ", ".join(detection.pdks)))
    validation = detection.validation
    for fix in validation.fixes:
        printc.say("  {0:<14}{1}".format("fixed", fix), color=printc.colors.CYAN)
    if validation.ok is True:
        printc.say("  {0:<14}elaborates with {1}".format("check", validation.tool), color=printc.colors.GREEN)
    elif validation.ok is False:
        printc.say("  {0:<14}does not elaborate with {1}:".format("check", validation.tool), color=printc.colors.RED)
        for line in validation.errors[:8]:
            printc.say("      " + line, color=printc.colors.RED)
    for note in detection.notes:
        printc.note(note, script_name)

######################################
# Questions
######################################

def _interactive(args):
    return not args.noask and sys.stdin.isatty() and not args.json


def _choose(question, current, alternatives):
    """Ask to pick among `current` and `alternatives`; the current one on Enter."""
    choices = [current] + [a for a in alternatives if a != current][:8]
    printc.say(question)
    for number, choice in enumerate(choices, 1):
        printc.say("  {0}) {1}".format(number, choice))
    while True:
        try:
            answer = input("Choice [1]: ").strip()
        except EOFError:
            return current
        if not answer:
            return current
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        if answer in choices or answer:
            return answer


def _confirm(question):
    try:
        return input(question + " [Y/n] ").strip().lower() in ("", "y", "yes", "o", "oui")
    except EOFError:
        return False

######################################
# Writing
######################################

def rtl_layout(detection, workspace_root):
    """
    Where the RTL directory of the design is, and how the file list names the
    sources: (rtl_dir, project_dir or None). The RTL directory is copied into
    every work directory: the common directory of the sources, unless the
    workspace lies inside it (it would copy itself), then the directory of the
    top level file, the other sources being named from ${ODATIX_PROJECT_DIR}.
    """
    paths = list(detection.files) + list(detection.include_dirs)
    if detection.top_file:
        paths.append(detection.top_file)
    common = os.path.commonpath([os.path.dirname(p) if os.path.isfile(p) else p for p in paths])
    workspace_root = os.path.realpath(workspace_root)

    def holds_workspace(directory):
        directory = os.path.realpath(directory)
        return workspace_root == directory or workspace_root.startswith(directory + os.sep)

    if not holds_workspace(common):
        return common, None
    top_dir = os.path.dirname(detection.top_file) if detection.top_file else ""
    if top_dir and not holds_workspace(top_dir):
        return top_dir, detection.root
    raise ValueError(
        "the sources are spread around the workspace ({0}): run \"odatix init --detect\" from a directory "
        "next to the project, e.g. \"mkdir ../{1}_odatix && cd ../{1}_odatix && odatix init --detect {2}\"".format(
            workspace_root, os.path.basename(detection.root), os.path.relpath(detection.root, os.path.join(workspace_root, ".."))))


def filelist_text(detection, rtl_dir, project_dir=None):
    def name(path):
        inside = os.path.realpath(path).startswith(os.path.realpath(rtl_dir) + os.sep) or \
            os.path.realpath(path) == os.path.realpath(rtl_dir)
        if inside or project_dir is None:
            return os.path.relpath(path, rtl_dir).replace(os.sep, "/")
        return "${" + PROJECT_VARIABLE + "}/" + os.path.relpath(path, project_dir).replace(os.sep, "/")

    lines = [
        FILELIST_MARK + " (sources: " + detection.origin + ").",
        "# Sources in compilation order. Run it again to regenerate this file, or edit it by hand.",
    ]
    lines += ["+incdir+" + name(d) for d in detection.include_dirs]
    lines += ["+define+" + d for d in detection.defines]
    lines += [name(f) for f in detection.files]
    return "\n".join(lines) + "\n"


def write_filelist(path, text):
    if os.path.exists(path):
        with open(path, "r", errors="replace") as f:
            if not f.read().startswith(FILELIST_MARK):
                raise ValueError("{0} exists and was not written by Odatix: move it away first".format(path))
    with open(path, "w") as f:
        f.write(text)


def architecture_settings(detection, workspace_root, rtl_dir, project_dir):
    settings = {
        "rtl_path": os.path.relpath(rtl_dir, workspace_root).replace(os.sep, "/"),
        "top_level_file": os.path.relpath(detection.top_file, rtl_dir).replace(os.sep, "/") if detection.top_file else "",
        "top_level_module": detection.top.value if detection.top else "",
        "clock_signal": detection.clock.value if detection.clock else "",
        "reset_signal": detection.reset.value if detection.reset else "",
        "filelist": FILELIST_NAME,
        "use_parameters": False,
    }
    if project_dir:
        settings["filelist_variables"] = {PROJECT_VARIABLE: project_dir}
    return settings


def generated_settings(detection, workspace_root):
    """
    The settings of an architecture generating its RTL: the project is its
    design_path, copied (white and black lists) into each work directory,
    where the command writes the RTL into generate_output.
    """
    generation = detection.generator
    blacklist = list(generation.blacklist)
    workspace_root = os.path.realpath(workspace_root)
    root = os.path.realpath(detection.root)
    if workspace_root == root:
        raise ValueError("the workspace is the project itself: run the import from a directory next to the project")
    if workspace_root.startswith(root + os.sep):
        # the workspace would copy itself into its own work directories
        blacklist.append(os.path.relpath(workspace_root, root).replace(os.sep, "/"))
    return {
        "generate_rtl": True,
        "design_path": os.path.relpath(root, workspace_root).replace(os.sep, "/"),
        "design_path_whitelist": list(generation.whitelist),
        "design_path_blacklist": blacklist,
        "generate_command": generation.command,
        "generate_output": generation.output,
        "top_level_file": os.path.relpath(detection.top_file, detection.generated_dir).replace(os.sep, "/") if detection.top_file else "",
        "top_level_module": detection.top.value if detection.top else "",
        "clock_signal": detection.clock.value if detection.clock else "",
        "reset_signal": detection.reset.value if detection.reset else "",
        "use_parameters": False,
    }


def selected_parameters(detection, parameters):
    """
    The parameter domains to create, as (domain name, [parameters]) pairs:
    one per parameter of the top level for True ("*"); otherwise from a list
    whose items are a parameter name or a group ({"group": name, "names":
    [...]}, or the string "group=a+b"), or from such items comma separated.
    Names that are not parameters of the top level are returned apart.
    """
    if not parameters:
        return [], []
    if parameters is True or parameters == "*":
        return [(p.name, [p]) for p in detection.parameters], []
    if isinstance(parameters, str):
        parameters = [n.strip() for n in parameters.split(",") if n.strip()]
    known = dict((p.name, p) for p in detection.parameters)
    groups, unknown = [], []
    for item in parameters:
        if isinstance(item, dict):
            group, names = str(item.get("group") or ""), list(item.get("names") or [])
        elif isinstance(item, (list, tuple)):
            group, names = str(item[0]), list(item[1])
        elif "=" in item:
            group, names = item.split("=", 1)
            group, names = group.strip(), [n.strip() for n in names.split("+") if n.strip()]
        else:
            group, names = "", [item.strip()]
        unknown.extend(n for n in names if n not in known)
        found = [known[n] for n in names if n in known]
        if found:
            groups.append((group or found[0].name, found))
    return groups, unknown


def parameter_values(parameters):
    """{parameter: values} given with the domains: the "values" of their dict items."""
    values = {}
    if isinstance(parameters, (list, tuple)):
        for item in parameters:
            if isinstance(item, dict):
                values.update((k, v) for k, v in (item.get("values") or {}).items() if v not in (None, ""))
    return values


def _parameter_domains(arch, groups, values=None):
    import odatix.workspace.detect as workspace_detect
    values = values or {}
    created, skipped = [], []
    for name, params in groups:
        try:
            if len(params) == 1 and name == params[0].name:
                arch.domains.create_from_parameter(params[0].name, values.get(params[0].name))
            else:
                path = workspace_detect.parameter_file(arch)
                target = os.path.relpath(path, workspace_detect.design_directory(arch)).replace(os.sep, "/")
                arch.domains.create(name, **workspace_detect.parameter_group_settings(
                    path, [p.name for p in params], target_file=target, values=values))
            created.append(name)
        except Exception as exception:
            skipped.append("{0} ({1})".format(name, exception))
    return created, skipped


def describe(detection, workspace, name, parameters=False, new_workspace=False):
    """
    Write what `detection` found into `workspace`: the file list at the root
    of the RTL directory and the architecture `name` (with a parameter domain
    per parameter of the top level when `parameters` (True for all of them,
    or their names)), and the default tool
    when the workspace names none, or names one this machine does not have in
    a workspace just created. Shared by the command and the GUI.

    Returns:
        dict: "architecture", "domains" (created), "skipped" (domains not
        created, with why), "default_tool" (set, or ""), "selector" (to run it).

    Raises:
        ValueError: nothing to describe, no place for the RTL directory, the
        architecture exists, or the file list is not Odatix's.
    """
    if not detection.files or detection.top is None:
        raise ValueError("no design found to describe" + (": no top level" if detection.files else ""))
    if workspace.architectures.exists(name):
        raise ValueError('the architecture "{0}" already exists'.format(name))
    if detection.generated_dir:
        settings = generated_settings(detection, workspace.root)
    else:
        rtl_dir, project_dir = rtl_layout(detection, workspace.root)
        try:
            write_filelist(os.path.join(rtl_dir, FILELIST_NAME), filelist_text(detection, rtl_dir, project_dir))
        except (OSError, IOError) as exception:
            raise ValueError(str(exception))
        settings = architecture_settings(detection, workspace.root, rtl_dir, project_dir)
    arch = workspace.architectures.create(name, **settings)
    domains, skipped = ([], [])
    groups, unknown = selected_parameters(detection, parameters)
    skipped = ["{0} (not a parameter of {1})".format(n, detection.top.value) for n in unknown]
    if groups:
        if detection.generated_dir:
            skipped.append("the parameters of generated RTL are set in the generator: point a domain at its sources (param_target_file)")
        else:
            created, failed = _parameter_domains(arch, groups, parameter_values(parameters))
            domains, skipped = created, skipped + failed
    default_tool = ""
    current_tool = workspace.settings.get("default_tool") or ""
    # a new workspace names the default of its template, not a tool of this machine
    if detection.default_tool and (not current_tool or new_workspace and current_tool not in detection.tools):
        workspace.save_settings(default_tool=detection.default_tool)
        default_tool = detection.default_tool
    selector = "{0} + {1}/*".format(name, " + ".join(domains)) if domains else name
    return {"architecture": arch, "domains": domains, "skipped": skipped, "default_tool": default_tool, "selector": selector}

######################################
# Command
######################################

def run(args):
    """odatix init --detect. True on success."""
    path = os.path.abspath(args.detect)
    if not os.path.isdir(path):
        printc.error("no such directory: " + path, script_name)
        return False
    if not args.json:
        printc.say("Detecting the project in {0}...".format(path))
    detection = project_detect.detect_project(path, top=args.top or "", check=not args.no_check)

    if detection.generator is not None and not args.no_generate and (args.generate is not None or detection.needs_generation):
        generation = detection.generator
        command = args.generate or generation.command
        if _interactive(args) and not args.generate:
            if generation.entries:
                command = _choose("The RTL is generated by {0}: which command generates it?".format(generation.name),
                                  command, generation.entries)
            elif not _confirm('The RTL is generated by {0}: run "{1}" (in a temporary copy of the project)?'.format(
                    generation.name, command)):
                command = None
        if command:
            if not args.json:
                printc.say('Generating the RTL: "{0}" in a copy of the project...'.format(command))
            project_detect.detect_generated(detection, command=command)
    try:
        return _run_detected(args, path, detection)
    finally:
        rtl_generation.cleanup(detection.generator)


def _run_detected(args, path, detection):
    if _interactive(args) and detection.top is not None and detection.top.confidence == "guessed" and detection.top.alternatives:
        top = _choose("Several modules may be the top level:", detection.top.value, detection.top.alternatives)
        if top != detection.top.value:
            generator = detection.generator
            detection = project_detect.retarget(detection, top, check=not args.no_check)
            if detection.generator is not generator:
                rtl_generation.cleanup(generator)
    if _interactive(args):
        for attribute, label in (("clock", "clock"), ("reset", "reset")):
            finding = getattr(detection, attribute)
            if finding is not None and finding.confidence == "guessed" and finding.alternatives:
                finding.value = _choose("Several signals may be the {0}:".format(label), finding.value, finding.alternatives)

    if args.json:
        print(json.dumps(detection.to_dict(), indent=2))
    else:
        report(detection)

    if not detection.files or detection.top is None:
        printc.error("no design found to describe" + (": no top level" if detection.files else ""), script_name)
        return False
    if args.dry_run:
        return True

    workspace_root = os.getcwd()
    name = args.name or detection.top.value
    if detection.generated_dir:
        written = "its RTL generated by each job"
    else:
        try:
            rtl_dir, project_dir = rtl_layout(detection, workspace_root)
        except ValueError as exception:
            printc.error(str(exception), script_name)
            return False
        written = "writes " + os.path.join(rtl_dir, FILELIST_NAME)
    if _interactive(args) and not _confirm('Describe it as the architecture "{0}" ({1})?'.format(name, written)):
        return False

    from odatix.lib.settings import OdatixSettings
    created = not OdatixSettings.workspace_here()
    if created and not OdatixSettings.init_directory_nodialog(False, silent=True):
        return False
    import odatix.workspace as workspace_api
    workspace = workspace_api.open_workspace(workspace_root, required=True)
    try:
        result = describe(detection, workspace, name, parameters=args.parameters, new_workspace=created)
    except ValueError as exception:
        printc.error(str(exception) + (": give another name with --name" if "already exists" in str(exception) else ""), script_name)
        return False
    arch = result["architecture"]
    printc.say('Architecture "{0}" written ({1})'.format(name, os.path.relpath(arch.settings_path, workspace_root)),
               color=printc.colors.GREEN)
    if result["domains"]:
        printc.say("Parameter domains: " + ", ".join(result["domains"]) + " (one value each: their current one)")
    for item in result["skipped"]:
        printc.warning("no parameter domain for " + item, script_name)
    if result["default_tool"]:
        printc.say("Default tool: " + result["default_tool"])
    if not arch.settings.reset_signal:
        printc.warning('no reset found: set "reset_signal" in ' + os.path.relpath(arch.settings_path, workspace_root), script_name)
    printc.tip('next: odatix analyze -a "{0}", then odatix synth -a "{0}"'.format(result["selector"]), script_name)
    return True
