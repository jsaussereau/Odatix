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

import glob
import os
import re
import shutil
import sys
import yaml
import argparse

from odatix.components.replace_params import replace_params
from odatix.components.run_common import (
    normalize_run_settings,
    confirm_valid_jobs,
    abort_if_empty_job_list,
    replace_and_write_param_domains,
    resolve_sim_param_target_file,
    run_prepare_loop,
    start_parallel_jobs as start_parallel_jobs_common,
)
import odatix.components.export_simulation_results as exp_sim_res
import odatix.components.export_derived_metrics as exp_derived
import odatix.components.task_common as task_common
import odatix.lib.printc as printc
import odatix.run.cli as run_cli
from odatix.components.cli_options import add_options
from odatix.run.options import RunOptions
from odatix.run.planner import leave_jobs_to_sessions
import odatix.lib.hard_settings as hard_settings
import odatix.lib.virtual_param_domain as virtual_param_domain
import odatix.lib.wsl as wsl
import odatix.sim.design_info as design_info
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.simulation_handler import SimulationHandler, sim_done_file
from odatix.lib.utils import copytree, create_dir, ask_to_continue, get_timestamp_string
from odatix.lib.run_settings import get_sim_settings
from odatix.lib.wosit import createTaskGraph
from odatix.workspace.space import selected_config_file, config_set_at

script_name = os.path.basename(__file__)

sim_makefile_filename = "Makefile"
sim_rule = "sim"

SIMULATION_META_FILENAME = exp_sim_res.SIMULATION_META_FILENAME

######################################
# Parse Arguments
######################################

def add_arguments(parser):
    add_options(
        parser, "simulations", "architectures",
        "overwrite", "noask", "daemon_options", "settings_file", "arch_path", "sim_path", "work_path",
        "exit_when_done", "nb_jobs", "keep", "resume", "log_size_limit", "debug", "export_options", "config",
        architectures={"help": 'architectures to simulate, written as the architectures of a simulation in the run settings file, '
                               'e.g. "MyCPU/*" (several values, repeatable; replaces those of every simulation run)'},
        work_path={"help": "simulation work directory"},
        keep={"help": "store simulation batch with a timestamp in the configuration name"},
    )


def parse_arguments():
    parser = argparse.ArgumentParser(description='Run parallel simulations')
    add_arguments(parser)
    return parser.parse_args()


######################################
# Tasks
######################################

def default_simulation_task(sim_instance):
    """
    The historical simulation command, expressed as a single "main" task: a
    simulation that defines no "tasks" in its settings file keeps running
    through its Makefile's "sim" rule, exactly as before.
    """
    # The paths of WSL for a simulation run there
    path = wsl.linux_path if getattr(sim_instance, "wsl", False) else (lambda value: value)
    command = (
        "make {}".format(sim_rule)
        + ' RTL_DIR="{}"'.format(hard_settings.work_rtl_path)
        + ' ODATIX_DIR="{}"'.format(path(OdatixSettings.odatix_path))
        + ' LOG_DIR="{}"'.format(path(os.path.realpath(os.path.join(sim_instance.tmp_dir, hard_settings.work_log_path))))
        + ' CLOCK_SIGNAL="{}"'.format(sim_instance.architecture.clock_signal)
        + ' TOP_LEVEL_MODULE="{}"'.format(sim_instance.architecture.top_level_module)
        + " --no-print-directory"
    )
    return [{"name": "main", "commands": [command]}]


def build_simulation_command_substitutions(sim_instance):
    """
    Values a simulation task command can reference as ${name}: the architecture
    it runs on, the usual work directories, and one entry per parameter domain
    holding that domain's configuration value (like workflow commands do).
    """
    architecture = sim_instance.architecture
    substitutions = {
        "simulation": sim_instance.sim_name,
        "architecture": sim_instance.arch_param_dir,
        "configuration": sim_instance.arch_config,
        "arch_full": sim_instance.arch_full,
        "top_level_module": str(architecture.top_level_module or ""),
        "clock_signal": str(architecture.clock_signal or ""),
        "reset_signal": str(getattr(architecture, "reset_signal", "") or ""),
        "work_path": os.path.realpath(sim_instance.tmp_dir),
        "rtl_path": hard_settings.work_rtl_path,
        "log_path": hard_settings.work_log_path,
        "script_path": hard_settings.work_script_path,
        "sim_path": os.path.realpath(sim_instance.source_sim_dir),
        "design_path": str(architecture.design_path or ""),
        "odatix_path": str(OdatixSettings.odatix_path),
    }
    # The names these variables had before they were aligned on the tool ones.
    # Still substituted so existing simulation settings keep working, but no
    # longer offered by the editors (see odatix.gui.builtin_variables).
    substitutions["rtl_dir"] = substitutions["rtl_path"]
    substitutions["log_dir"] = substitutions["log_path"]
    substitutions["odatix_dir"] = substitutions["odatix_path"]

    # What Odatix found out about the design under test: its sources, its
    # testbench (see odatix.sim.design_info).
    substitutions.update(design_info.substitutions(getattr(sim_instance, "design_info", None) or {}))
    if not substitutions["reset_signal"]:
        substitutions["reset_signal"] = str(getattr(architecture, "reset_signal", "") or "")

    substitutions.update(configuration_variables(sim_instance))
    substitutions.update(domain_values(architecture))

    if getattr(sim_instance, "wsl", False):
        # The simulator runs in WSL: the paths it is given are those of WSL, and
        # ${python} is the Python of the distribution (see odatix.lib.wsl)
        for name in WSL_PATH_SUBSTITUTIONS:
            substitutions[name] = wsl.linux_path(substitutions.get(name))
        substitutions["python"] = wsl.PYTHON

    return substitutions


#: The substitutions of a simulation command holding a path of Windows
WSL_PATH_SUBSTITUTIONS = ("work_path", "sim_path", "design_path", "odatix_path", "odatix_dir")


def for_wsl(tasks):
    """
    The tasks of a simulation run in WSL: each of their commands is run there,
    through wsl.exe, while what Odatix chains around them (marking the job
    done) stays on Windows. The directory a task runs in is a path of Windows:
    WSL starts there.
    """
    wrapped = []
    for task in tasks:
        task = dict(task) if isinstance(task, dict) else task
        if isinstance(task, dict):
            for key in ("commands", "on_failure_commands"):
                if isinstance(task.get(key), list):
                    task[key] = [wsl.command(command) for command in task[key]]
        wrapped.append(task)
    return wrapped


def configuration_variables(sim_instance):
    """
    The values of the variables the configuration under test was built from:
    {"width": "8"} for a configuration "08bits" that a rule builds from the
    variable "width", whichever domain it belongs to. Computed once per job.
    """
    cached = getattr(sim_instance, "_configuration_variables", None)
    if cached is not None:
        return cached

    architecture = sim_instance.architecture
    values = {}
    arch_path = getattr(architecture, "arch_path", None)
    if arch_path:
        selections = [(os.path.join(arch_path, sim_instance.arch_param_dir), sim_instance.arch_config)]
        for param_domain in getattr(architecture, "param_domains", []) or []:
            selections.append((
                os.path.join(arch_path, sim_instance.arch_param_dir, param_domain.domain), param_domain.domain_value,
            ))
        for path, name in selections:
            if not os.path.isdir(path):
                continue
            try:
                resolved = next((config for config in config_set_at(path).resolve() if config.name == str(name)), None)
            except Exception:
                resolved = None
            if resolved is not None:
                values.update({str(key): str(value) for key, value in resolved.values.items()})
    # Variables an architecture substitutes into its commands, one job per value
    for key, value in (getattr(architecture, "virtual_param_domains", None) or {}).items():
        values[str(key)] = str(value)

    sim_instance._configuration_variables = values
    return values


def domain_values(architecture):
    """{domain: value} of the configuration run, for every parameter domain."""
    values = {}
    for param_domain in getattr(architecture, "param_domains", []) or []:
        value = virtual_param_domain.read_command_parameter_value(param_domain.param_file)
        if value is not None:
            values[param_domain.domain] = value
    return values


def write_design_info(sim_instance, parallel_jobs=None):
    """
    Tell the simulation about the design under test: write "odatix_sim.yml" and
    "odatix_sim.f" into its work directory (see odatix.sim.design_info), and
    keep what they say for the placeholders of its commands. `parallel_jobs`,
    how many jobs run at once, lets a template share the cores among them.
    """
    architecture = sim_instance.architecture
    # The values of the testbench parameters may use the placeholders of the
    # commands: ${width} gives the testbench the width of the configuration.
    testbench = select_testbench(sim_instance)
    if isinstance(testbench.get("parameters"), dict):
        values = build_simulation_command_substitutions(sim_instance)
        testbench["parameters"] = {
            str(name): virtual_param_domain.replace_command_vars(str(value), values)
            for name, value in testbench["parameters"].items()
        }
    try:
        info = design_info.build_info(
            sim_instance.tmp_dir,
            simulation=sim_instance.sim_name,
            architecture=sim_instance.arch_param_dir,
            configuration=sim_instance.arch_config,
            arch_full=sim_instance.arch_full,
            top=architecture.top_level_module,
            clock=architecture.clock_signal,
            reset=getattr(architecture, "reset_signal", ""),
            param_domains=domain_values(architecture),
            testbench=testbench,
            rtl_generated=bool(architecture.generate_rtl),
            rtl_dir=hard_settings.work_rtl_path,
            reset_active_low=reset_active_low(architecture),
            parallel_jobs=parallel_jobs,
        )
        design_info.write_info(sim_instance.tmp_dir, info)
    except Exception as e:
        printc.warning(
            "Could not write \"" + design_info.SIM_INFO_FILENAME + "\" for \"" + sim_instance.sim_display_name + "\": " + str(e),
            script_name,
        )
        info = {}
    sim_instance.design_info = info
    return info


# Where the testbench of an architecture is copied, in a job's work directory.
ARCHITECTURE_TESTBENCH_DIR = "testbench"


def select_testbench(sim_instance):
    """
    The testbench a job runs, by priority:

      1. the files the simulation names ("testbench: files" in its settings);
      2. the testbench of the architecture, copied into "testbench/" in the
         work directory;
      3. the HDL files of the simulation's "tb" directory.

    Returns:
        dict: the "testbench" setting the information file is built from.
    """
    own = dict(sim_instance.testbench or {})
    if own.get("files"):
        return own
    arch_testbench = getattr(sim_instance.architecture, "testbench", None) or {}
    if not arch_testbench.get("files"):
        # The "tb" directory, or else the testbench Odatix generates: with what
        # the architecture says of it, unless the simulation says otherwise.
        generated = {
            key: value for key, value in arch_testbench.items()
            if key in design_info.GENERATED_TESTBENCH_DEFAULTS and value not in (None, "")
        }
        generated.update(own)
        return generated

    patterns = arch_testbench["files"]
    patterns = [patterns] if isinstance(patterns, str) else patterns
    sources = []
    for pattern in patterns:
        sources.extend(path for path in sorted(glob.glob(str(pattern))) if os.path.isfile(path))
    sources = list(dict.fromkeys(os.path.abspath(path) for path in sources))
    if not sources:
        return own

    # Keep the layout of the files (a header next to the file including it),
    # from the deepest directory holding them all.
    common = os.path.commonpath([os.path.dirname(path) for path in sources])
    files = []
    for path in sources:
        relpath = os.path.relpath(path, common)
        destination = os.path.join(sim_instance.tmp_dir, ARCHITECTURE_TESTBENCH_DIR, relpath)
        if not os.path.isdir(os.path.dirname(destination)):
            os.makedirs(os.path.dirname(destination))
        shutil.copy2(path, destination)
        if design_info.language_of(path) is not None:
            files.append((ARCHITECTURE_TESTBENCH_DIR + "/" + relpath).replace(os.sep, "/"))
    return {
        "top": arch_testbench.get("top") or "",
        "files": files,
        "parameters": dict(arch_testbench.get("parameters") or {}),
    }


def reset_active_low(architecture):
    """The polarity the architecture gives its reset, or None to guess it from its name."""
    value = getattr(architecture, "reset_active_low", None)
    if value in (None, ""):
        return None
    from odatix.workspace.yaml_io import parse_bool

    return parse_bool(value, False)


def generate_command(sim_instance):
    """
    The RTL generation command of the job, if any. A generated RTL only exists
    once it has run, so the information file is written again right after.
    """
    architecture = sim_instance.architecture
    if not architecture.generate_rtl:
        return architecture.generate_command
    return "(" + str(architecture.generate_command) + ") && " + design_info.refresh_command(".")


def resolve_simulation_tasks(tasks, substitutions):
    """Substitute ${name} placeholders in every task command and path."""
    resolved_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            resolved_tasks.append(task)
            continue

        resolved_task = dict(task)

        for key in ("commands", "on_failure_commands"):
            commands = resolved_task.get(key)
            if isinstance(commands, list):
                resolved_task[key] = [
                    virtual_param_domain.replace_command_vars(command, substitutions) for command in commands
                ]

        task_path = resolved_task.get("path")
        if isinstance(task_path, str):
            resolved_task["path"] = virtual_param_domain.replace_command_vars(task_path, substitutions)

        resolved_tasks.append(resolved_task)

    return resolved_tasks


######################################
# Run Simulations
######################################

def run_simulations(
    run_config_settings_filename,
    arch_path,
    sim_path,
    work_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    debug=False,
    keep=False,
    resume=False,
    output_dir=None,
    output_filename=exp_sim_res.DEFAULT_OUTPUT_FILENAME,
    detach=False,
    daemon_session=None,
):
    # See run_fmax_synthesis.run_synthesis: every run goes through odatix.run.
    run_cli.execute(run_cli.command_run(
        "simulation",
        settings_file=run_config_settings_filename,
        arch_path=arch_path,
        sim_path=sim_path,
        work_path=work_path,
        result_path=output_dir,
        output_filename=output_filename,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        debug=debug,
        keep=keep,
        resume=resume,
        detach=detach,
        session=daemon_session,
    ))


def select_simulations(simulations, names=None, architectures=None):
    """
    What a run simulates, out of the "simulations" of its settings file.

    Args:
        simulations (list): the "simulations" of the file, as written: a list
            of {simulation: [architecture selectors]}. None when it is empty.
        names (list): the simulations to run ("--sim"). All of the file's when
            empty.
        architectures (list): architecture selectors replacing those of every
            simulation run ("--architecture").

    Returns:
        list: the same shape, or None when there is nothing to run.

    Raises:
        ValueError: a simulation is named that the file does not give
            architectures to, and no architectures are named either.
    """
    file_lists = {}
    for entry in simulations or []:
        if isinstance(entry, dict):
            for sim, arch_list in entry.items():
                file_lists.setdefault(str(sim), []).extend(arch_list or [])

    if not names:
        if not architectures:
            return simulations
        if not file_lists:
            raise ValueError("no simulation to run them with: name one with -s/--sim")
        return [{sim: list(architectures)} for sim in file_lists]

    selected = []
    for sim in dict.fromkeys(str(name) for name in names):
        if architectures:
            selected.append({sim: list(architectures)})
        elif file_lists.get(sim):
            selected.append({sim: list(file_lists[sim])})
        else:
            raise ValueError(
                'the run settings file gives no architecture to the simulation "' + sim
                + '": name them with -a/--architecture'
            )
    return selected


def check_settings(
    run_config_settings_filename,
    arch_path,
    sim_path,
    work_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    debug=False,
    keep=False,
    selected_simulations=None,
    selected_architectures=None,
    resume=False,
):
    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs, simulations = get_sim_settings(run_config_settings_filename)
    # Simulations and architectures named by the run ("--sim", "--architecture")
    # take precedence over the list of the file.
    try:
        simulations = select_simulations(simulations, selected_simulations, selected_architectures)
    except ValueError as error:
        printc.error(str(error)[0].upper() + str(error)[1:] + ".", script_name)
        sys.exit(-1)

    if simulations is None:
        printc.error('The "simulations" section of "' + run_config_settings_filename + '" is empty.', script_name)
        printc.note('You must define your simulations in "' + run_config_settings_filename + '" before using this command.', script_name)
        printc.note("See the Odatix documentation for more information.", script_name)
        sys.exit(-1)

    overwrite, ask_continue, exit_when_done, log_size_limit, nb_jobs = normalize_run_settings(
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        defaults=(_overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs),
    )

    sim_handler = SimulationHandler(
        work_path = work_path,
        arch_path = arch_path,
        sim_path = sim_path,
        work_rtl_path = hard_settings.work_rtl_path,
        work_script_path = hard_settings.work_script_path,
        work_log_path = hard_settings.work_log_path,
        log_path = hard_settings.work_log_path,
        overwrite = overwrite,
        resume = resume,
        param_settings_filename = hard_settings.param_settings_filename,
        sim_settings_filename = hard_settings.sim_settings_filename,
        sim_makefile_filename = sim_makefile_filename
    )

    timestamp = get_timestamp_string()

    try:
        simulation_instances = sim_handler.get_simulations(simulations, keep=keep, timestamp=timestamp)
    except yaml.YAMLError as e:
        printc.error("Could not get list \"simulations\" from \"" + run_config_settings_filename + "\".", script_name=script_name)
        printc.note("Is the YAML file valid? Are you missing a ':'? Is the indentation correct?", script_name=script_name)
        printc.cyan("error details: ", end="", script_name=script_name)
        print(str(e))
        sys.exit(-1)

    # The monitor parses every job's progress with a single pattern, so the
    # first simulation's regex wins (same rule as workflows).
    first_progress_regex = None
    for sim_instance in simulation_instances:
        regex = sim_instance.progress_regex or hard_settings.sim_status_pattern.pattern
        if first_progress_regex is None:
            first_progress_regex = regex
        elif first_progress_regex != regex:
            printc.note(
                "Multiple progress.regex values detected. Using the first one for monitor parsing: \"" + first_progress_regex + "\"",
                script_name,
            )
            break
    if first_progress_regex is None:
        first_progress_regex = hard_settings.sim_status_pattern.pattern
    ParallelJob.set_patterns(re.compile(first_progress_regex))

    # A simulation a session is already running is left to it: two sessions
    # running one work directory write into each other's files.
    selected_count = len(simulation_instances)
    simulation_instances = leave_jobs_to_sessions(
        simulation_instances, sim_handler.plan,
        tmp_dir=lambda sim_instance: sim_instance.tmp_dir,
        name=lambda sim_instance: sim_instance.sim_display_name,
        overwrite=overwrite, script_name=script_name,
    )
    valid_count = sim_handler.get_valid_sim_count() - (selected_count - len(simulation_instances))

    # print checklist summary
    sim_handler.print_summary()

    confirm_valid_jobs(valid_count, ask_continue, ask_to_continue, script_name=script_name, plan=sim_handler.plan,
        overview=dict(nb_jobs=nb_jobs))

    print()

    job_list = []

    def prepare_job(sim_instance, resume=False):

        # create directory
        if not (resume and os.path.isdir(sim_instance.tmp_dir)):
            create_dir(sim_instance.tmp_dir)
        elif os.path.isfile(sim_done_file(sim_instance.tmp_dir)):
            # Running again in place: done only once it succeeds again.
            os.remove(sim_done_file(sim_instance.tmp_dir))

        # The directory ${log_path} names, which the commands write their logs in
        log_dir = os.path.join(sim_instance.tmp_dir, hard_settings.work_log_path)
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)

        # write run metadata to make post-processing/export robust
        write_simulation_meta(sim_instance)

        # copy simulation sources: the template it starts from first, then its own
        for definition_dir in sim_instance.definition_dirs:
            copytree(definition_dir, sim_instance.tmp_dir, dirs_exist_ok = True)

        # copy design
        if sim_instance.architecture.design_path is not None:
            if not os.path.isdir(sim_instance.architecture.design_path):
                printc.error('The design directory "' + sim_instance.architecture.design_path + '" does not exist', script_name)
                return
            try:
                copytree(
                    src=sim_instance.architecture.design_path,
                    dst=sim_instance.tmp_dir,
                    whitelist=sim_instance.architecture.design_path_whitelist,
                    blacklist=sim_instance.architecture.design_path_blacklist,
                    dirs_exist_ok=True
                )
            except:
                printc.error("Could not copy \"" + sim_instance.architecture.design_path + "\" into work directory \"" + sim_instance.tmp_dir + "\"", script_name)
                printc.note("make sure there are no file or folder named identically in the two directories", script_name)
                return

        # copy rtl (if exists)
        if not sim_instance.architecture.generate_rtl:
            copytree(sim_instance.architecture.rtl_path, os.path.join(sim_instance.tmp_dir, 'rtl'), dirs_exist_ok = True)

        # replace parameters
        if sim_instance.architecture.use_parameters:
            if debug:
                printc.subheader("Replace main parameters")
            param_target_file = resolve_sim_param_target_file(
                sim_instance.tmp_dir, sim_instance.architecture.param_target_filename
            )
            param_filename = selected_config_file(arch_path, sim_instance.architecture.arch_name)
            replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_filename,
                output_file=param_target_file,
                start_delimiter=sim_instance.architecture.start_delimiter,
                stop_delimiter=sim_instance.architecture.stop_delimiter,
                replace_all_occurrences=False,
                silent=True
            )
            if debug:
                print()

        replace_and_write_param_domains(
            tmp_dir=sim_instance.tmp_dir,
            arch_name=sim_instance.architecture.arch_name,
            param_domains=sim_instance.architecture.param_domains,
            default_target_filename=sim_instance.architecture.param_target_filename,
            target_filename_getter=lambda param_domain: param_domain.param_target_file,
            debug=debug,
            target_resolver=resolve_sim_param_target_file,
            timestamp=None,
            virtual_domains=getattr(sim_instance.architecture, "virtual_param_domains", None),
            arch_path=getattr(sim_instance.architecture, "arch_path", None),
        )

        # replace parameters again (override)
        if sim_instance.override_parameters:
            param_target_file = resolve_sim_param_target_file(
                sim_instance.tmp_dir, sim_instance.override_param_target_filename
            )
            param_file = os.path.join(sim_instance.tmp_dir, sim_instance.override_param_filename)
            replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_file,
                output_file=param_target_file,
                start_delimiter=sim_instance.override_start_delimiter,
                stop_delimiter=sim_instance.override_stop_delimiter,
                replace_all_occurrences=False,
                silent=True
            )

        # what the simulation is told about the design under test
        write_design_info(sim_instance, parallel_jobs=nb_jobs)

        command = build_simulation_command(sim_instance)
        if command is None:
            return

        sim_progress_file = os.path.join(
            sim_instance.tmp_dir,
            sim_instance.progress_file or hard_settings.sim_progress_file,
        )

        running_sim = ParallelJob(
            process=None,
            command=command,
            directory=sim_instance.tmp_dir,
            generate_rtl=sim_instance.architecture.generate_rtl,
            generate_command=generate_command(sim_instance),
            target="",
            arch="",
            display_name=sim_instance.sim_display_name,
            status_file="",
            progress_file=sim_progress_file,
            tmp_dir=sim_instance.tmp_dir,
            log_size_limit=log_size_limit,
            status="idle",
        )

        job_list.append(running_sim)

    return simulation_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs, sim_handler.plan


def write_simulation_meta(sim_instance):
    """
    Write the run metadata file the result exporter reads back, so a work
    directory always says which simulation and which architecture configuration
    produced it (see odatix.components.export_simulation_results).
    """
    meta_file = os.path.join(sim_instance.tmp_dir, SIMULATION_META_FILENAME)
    try:
        with open(meta_file, "w", encoding="utf-8") as f:
            yaml.dump(
                {
                    "simulation": sim_instance.sim_name,
                    "simulation_display_name": sim_instance.sim_display_name,
                    "simulation_definition_dir": sim_instance.source_sim_dir,
                    "architecture": sim_instance.arch_param_dir,
                    "configuration": sim_instance.arch_config,
                    "arch_full": sim_instance.arch_full,
                    # Which domains the run is invariant to is what the record
                    # must leave out to match every value of them, so it travels
                    # with the run rather than being looked up again at export.
                    "invariant_domains": sorted(sim_instance.invariant_domains),
                    # What to extract: the "_metrics.yml" of the template the
                    # simulation starts from, then its own, merged.
                    "metrics_files": list(sim_instance.metrics_files),
                },
                f,
                default_flow_style=False,
                sort_keys=False,
            )
    except Exception as e:
        printc.warning(
            "Could not write simulation metadata file \"" + meta_file + "\": " + str(e),
            script_name,
        )


def _done_command(tmp_dir):
    """What a job runs last: the same line for sh and cmd.exe."""
    return "echo done> \"" + os.path.realpath(sim_done_file(tmp_dir)) + "\""


def with_done_mark(command, tmp_dir):
    """
    The command of a job, followed by what marks the simulation as done (see
    simulation_handler.job_category), which only runs when everything before it
    succeeded: a single command line is chained to it, and a task graph gets a
    last stage, the stages running one after the other until one fails.
    """
    done = _done_command(tmp_dir)
    if isinstance(command, str):
        # The line break ends a comment the command may finish with.
        return "(" + command + ("" if os.name == "nt" else "\n") + ") && " + done
    stages = dict(command)
    levels = [int(level) for level in stages if str(level).lstrip("-").isdigit()]
    stages[(max(levels) + 1) if levels else len(stages)] = [{"name": "done", "command": done}]
    return stages


def build_simulation_command(sim_instance):
    """
    Build what the job actually runs: the execution stages of the simulation's
    task graph, or the legacy single "make sim" command when it defines no task,
    then what marks the simulation as done.

    Returns:
        The command (a string or execution stages), or None when the task graph
        could not be built (the job is then skipped).
    """
    tasks = sim_instance.tasks if sim_instance.tasks else default_simulation_task(sim_instance)
    in_wsl = getattr(sim_instance, "wsl", False)
    # A simulation run in WSL runs the implementation of its tasks for Linux
    platform = "linux" if in_wsl else sys.platform

    try:
        selected_tasks = task_common.select_platform_task_implementations(tasks, platform)
        substitutions = build_simulation_command_substitutions(sim_instance)
        resolved_tasks = resolve_simulation_tasks(selected_tasks, substitutions)
        task_common.validate_selected_tasks(resolved_tasks, platform)
        if in_wsl:
            resolved_tasks = for_wsl(resolved_tasks)
    except ValueError as e:
        printc.error(
            "Invalid tasks for simulation \"" + sim_instance.sim_display_name + "\": " + str(e),
            script_name,
        )
        return None

    # A single-command "main" task with no dependency is the historical case:
    # run it directly instead of paying for a task graph.
    if (
        len(resolved_tasks) == 1
        and not resolved_tasks[0].get("dependencies")
        and not resolved_tasks[0].get("path")
        and not resolved_tasks[0].get("on_failure_commands")
    ):
        commands = resolved_tasks[0].get("commands", [])
        if len(commands) == 1:
            return with_done_mark(commands[0], sim_instance.tmp_dir)

    try:
        maker = createTaskGraph(resolved_tasks)
        old_cwd = os.getcwd()
        try:
            os.chdir(sim_instance.tmp_dir)
            execution_stages = maker.getStages(name="main", max_process=1)
        finally:
            os.chdir(old_cwd)
    except Exception as e:
        printc.error(
            "Error while creating task graph for simulation \"" + sim_instance.sim_display_name + "\". "
            "Please check your simulation settings file and task definitions.",
            script_name,
        )
        printc.cyan("error details: ", end="", script_name=script_name)
        print(str(e))
        return None

    if execution_stages is None or len(execution_stages) == 0:
        printc.error(
            "Failed to generate execution stages for simulation \"" + sim_instance.sim_display_name + "\".",
            script_name,
        )
        return None

    return with_done_mark(execution_stages, sim_instance.tmp_dir)


def prepare_simulations(
    simulation_instances,
    prepare_job,
    job_list,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    resume=False,
    export_output_dir=None,
    export_work_root=None,
    export_sim_path=None,
    export_output_filename=exp_sim_res.DEFAULT_OUTPUT_FILENAME,
):
    run_prepare_loop(
        instances=simulation_instances,
        build_job=lambda sim_instance: prepare_job(sim_instance, resume=resume),
        job_list=job_list,
    )

    # A simulation can pass the initial checklist but still fail while its job
    # is being built (e.g. a missing design_path): do not launch the
    # monitor/daemon session with zero jobs if every one of them failed.
    abort_if_empty_job_list(job_list, script_name=script_name)

    parallel_jobs = ParallelJobHandler(
        job_list=job_list,
        nb_jobs=nb_jobs,
        process_group=True,
        auto_exit=exit_when_done,
        log_size_limit=log_size_limit,
    )

    # Per-job result export (au fil de l'eau): tag every job so the handler
    # exports its result as soon as it finishes, for both the CLI and the
    # GUI/daemon (which both call this prepare function).
    if export_output_dir and export_work_root and export_sim_path:
        exp_sim_res.configure_simulation_job_exports(
            parallel_jobs=parallel_jobs,
            work_root=export_work_root,
            sim_path=export_sim_path,
            output_dir=export_output_dir,
            output_filename=export_output_filename,
        )

    # Whole-batch derivation: a derived metric reads records other jobs produce,
    # so it can only be computed once every job of the batch is done.
    if export_output_dir:
        exp_derived.configure_post_batch_derivation(parallel_jobs, export_output_dir)

    return parallel_jobs


def start_parallel_jobs(
    parallel_jobs,
    use_api=True,
    start_headless_on_startup=False,
    detach=False,
    session=None,
    configure=True,
):
    start_parallel_jobs_common(
        parallel_jobs=parallel_jobs,
        use_api=use_api,
        start_headless_on_startup=start_headless_on_startup,
        detach=detach,
        session=session,
        configure=configure,
    )

######################################
# Main
######################################

def main(args):
    run_cli.execute(run_cli.command_run(
        "simulation",
        workspace=run_cli.command_workspace(args.config, script_name),
        options=RunOptions.from_namespace(args),
    ))


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
