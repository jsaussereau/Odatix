# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #

import os
import re
import yaml
import shutil

from odatix.components.replace_params import replace_params
from odatix.components.run_common import normalize_run_settings, abort_if_empty_job_list, run_prepare_loop, resolve_param_target_file
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.read_tool_settings import read_tool_settings
from odatix.lib.utils import read_from_list, copytree, create_dir, create_dir_if_missing, KeyNotInListError, BadValueInListError
from odatix.lib.get_from_dict import get_from_dict
from odatix.lib.prepare_work import edit_config_file
from odatix.lib.check_tool import start_tool_check
from odatix.workspace.space import selected_config_file
from odatix.lib.run_settings import get_synth_settings
from odatix.lib.variables import replace_variables, Variables
import odatix.lib.job_steps as job_steps
import odatix.lib.constraint_files as constraint_files
import odatix.lib.yaml_loader as yaml_loader


def restrict_targets(targets, selected, tool, eda_target_filename, script_name=""):
    """
    The targets a run works on, once it has been told which ones it wants.

    A target file is where targets are turned on and off, and a run has always
    taken every target it enables. Being told a subset is what lets something
    else choose the target of a job without editing that file underneath the
    other runs sharing it -- an exploration searching the targets, typically,
    which runs one target at a time and must not have the file mean different
    things at different moments.

    Args:
        targets (list): what the target file enables.
        selected (list): the targets the run was told to keep, empty or None to
            keep all of them.

    Returns:
        list: the targets to run on, in the order the target file names them.
    """
    wanted = [str(name).strip() for name in (selected or []) if str(name).strip()]
    if not wanted:
        return targets

    kept = [target for target in targets if str(target) in wanted]
    missing = [name for name in wanted if name not in [str(target) for target in targets]]
    if missing:
        printc.error(
            'Target(s) "' + '", "'.join(missing) + '" are not enabled for the eda tool "' + tool + '"',
            script_name,
        )
        printc.note('Enabled targets in "' + eda_target_filename + '" are: ' + ", ".join(str(t) for t in targets), script_name)
        raise SystemExit(-1)
    return kept


def load_synthesis_context(
    run_config_settings_filename,
    arch_path,
    tool,
    work_path,
    target_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    check_eda_tool,
    debug=False,
    script_name="",
    synth_type=None,
    flow=None,
    check_cancel=None,
    settings_reader=None,
    selection_key="architectures",
    selection_noun="architectures",
    selected_targets=None,
):
    if check_cancel is not None:
        check_cancel()

    # What a run selects depends on the job type: architectures for a synthesis,
    # completed synthesis jobs for a place & route (see run_settings). Whatever
    # it is, it rides in context["architectures"] from here on, since that is
    # what the handler of the job type is handed.
    read_settings = settings_reader if settings_reader is not None else get_synth_settings
    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs, architectures = read_settings(run_config_settings_filename)

    if architectures is None:
        printc.error('The "' + selection_key + '" section of "' + run_config_settings_filename + '" is empty.', script_name)
        printc.note('You must define your ' + selection_noun + ' in "' + run_config_settings_filename + '" before using this command.', script_name)
        printc.note("Check out examples Odatix's documentation for more information.", script_name)
        raise SystemExit(-1)

    if check_cancel is not None:
        check_cancel()

    overwrite, ask_continue, exit_when_done, log_size_limit, nb_jobs = normalize_run_settings(
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        defaults=(_overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs),
    )

    from odatix.lib.settings import OdatixSettings
    import odatix.lib.eda_tools as eda_tools

    eda_target_filename = eda_tools.resolve_target_file(tool, target_path)

    if not os.path.isfile(eda_target_filename):
        printc.error(
            'Target file "' + eda_target_filename + '", for the selected eda tool "' + tool + '" does not exist',
            script_name,
        )
        raise SystemExit(-1)

    eda_tool_dir = eda_tools.get_tool_dir(tool)

    if eda_tool_dir is None:
        printc.error(
            'No directory found for the selected eda tool "' + tool + '"',
            script_name,
        )
        printc.note(
            'The selected eda tool "'
            + tool
            + '" is not one of the available tools. Check out Odatix\'s documentation to add support for your own eda tool',
            script_name,
        )
        printc.note("Available tools are: " + ", ".join(eda_tools.get_supported_tools()), script_name)
        raise SystemExit(-1)

    tool_settings_file = os.path.realpath(os.path.join(eda_tool_dir, hard_settings.tool_settings_filename))
    if synth_type is None:
        process_group, report_path, run_command, tool_test_command, _, flow_name, flow_steps = read_tool_settings(tool, tool_settings_file, flow=flow)
    else:
        process_group, report_path, run_command, tool_test_command, _, flow_name, flow_steps = read_tool_settings(
            tool, tool_settings_file, synth_type=synth_type, flow=flow
        )

    # Two flows of the same tool are alternatives to compare: they each get
    # their own work sub-directory ("vivado@power_opt"), the default flow
    # keeping the bare tool name.
    work_path = os.path.join(work_path, eda_tools.tool_work_dirname(tool, flow_name, job_type=synth_type))

    with open(eda_target_filename, "r") as f:
        try:
            settings_data = yaml.load(f, Loader=yaml_loader.SafeLoader)
        except Exception as e:
            printc.error('Settings file "' + eda_target_filename + '" is not a valid YAML file', script_name)
            printc.cyan("error details: ", end="", script_name=script_name)
            print(str(e))
            raise SystemExit(-1)

        try:
            targets = read_from_list("targets", settings_data, eda_target_filename, script_name=script_name)
            constraint_file = read_from_list("constraint_file", settings_data, eda_target_filename, script_name=script_name)
        except (KeyNotInListError, BadValueInListError):
            raise SystemExit(-1)

        targets = restrict_targets(targets, selected_targets, tool, eda_target_filename, script_name=script_name)

        try:
            install_path = read_from_list(
                "tool_install_path", settings_data, eda_target_filename, print_error=False, script_name=script_name
            )
            install_path = os.path.realpath(os.path.expanduser(str(install_path)))
            if not os.path.isdir(install_path):
                printc.error(
                    'The installation path "'
                    + install_path
                    + '" defined for tool "'
                    + tool
                    + '" in "'
                    + eda_target_filename
                    + '" does not exist',
                    script_name,
                )
                printc.note('Please update the path in "' + eda_target_filename + '"', script_name=script_name)
                printc.note(
                    'if no installation path is needed by ' + tool + '\'s Makefile, simply remove "install_path" from "' + eda_target_filename + '"',
                    script_name=script_name,
                )
                raise SystemExit(-1)

        except (KeyNotInListError, BadValueInListError):
            printc.note('No tool_install_path specified for "' + tool + '"', script_name=script_name)
            install_path = "/"

        force_single_thread, _ = get_from_dict(
            "force_single_thread", settings_data, eda_target_filename, default_value=False, script_name=script_name
        )

    if isinstance(tool_test_command, list):
        tool_test_command = " ".join(map(str, tool_test_command))

    from odatix.lib.settings import OdatixSettings

    variables = Variables(
        tool_install_path=os.path.realpath(install_path),
        odatix_path=OdatixSettings.odatix_path,
        odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
        tool_path=eda_tool_dir,
    )
    tool_test_command = replace_variables(tool_test_command, variables)

    # The tool check runs in the background: the caller keeps building its
    # architecture list while the tool starts up, and waits for the outcome
    # right before asking the user to continue (see context["tool_check"]).
    tool_check = None
    if check_eda_tool:
        if check_cancel is not None:
            check_cancel()
        tool_check = start_tool_check(
            tool,
            command=tool_test_command,
            supported_tools=eda_tools.get_supported_tools(),
            tool_install_path=install_path,
            debug=debug,
        )

    if check_cancel is not None:
        check_cancel()

    return {
        "architectures": architectures,
        "work_path": work_path,
        "tool_settings_file": tool_settings_file,
        # tool.yml the log formatter reads: the highest precedence one declaring
        # a "format" section, which is not necessarily the tool.yml above when a
        # user tool.yml only adds flows to a built-in tool.
        "format_settings_file": eda_tools.get_format_settings_file(tool) or tool_settings_file,
        "flow": flow_name,
        "flow_steps": flow_steps,
        "process_group": process_group,
        "run_command": run_command,
        "install_path": install_path,
        "force_single_thread": force_single_thread,
        "targets": targets,
        "constraint_file": constraint_file,
        "exit_when_done": exit_when_done,
        "log_size_limit": log_size_limit,
        "nb_jobs": nb_jobs,
        "overwrite": overwrite,
        "ask_continue": ask_continue,
        "tool_check": tool_check,
    }


######################################
# Shared job preparation steps
######################################
# Every job Odatix runs in a work directory is built the same way: the tool's
# scripts are copied in, a few files say what the job is, the tcl settings are
# patched and a ParallelJob is built from the flow's command or steps. Only what
# happens in between differs (a synthesis brings its rtl and its parameters, a
# place & route brings a netlist from another job), so those steps live here and
# are shared by every job builder.


def prepare_job_directory(arch_instance, resuming):
    """
    Create (or keep) the directory of a job. A resuming job must keep what the
    completed steps produced — their checkpoints, reports and the step state
    itself — so only a job starting from scratch wipes its directory.
    """
    if resuming:
        create_dir_if_missing(arch_instance.tmp_dir)
        create_dir_if_missing(arch_instance.tmp_log_path)
    else:
        create_dir(arch_instance.tmp_dir)
        create_dir(arch_instance.tmp_log_path)


def copy_job_scripts(arch_instance, tool, resuming, script_name=""):
    """
    Copy into the job's script directory the scripts shared by every tool, then
    those of the tool itself. Returns False when the tool cannot be resolved.
    """
    import odatix.lib.eda_tools as eda_tools
    from odatix.lib.settings import OdatixSettings

    try:
        copytree(
            os.path.join(OdatixSettings.odatix_eda_tools_path, hard_settings.common_script_path),
            arch_instance.tmp_script_path,
            dirs_exist_ok=resuming,
        )
    except FileExistsError:
        printc.error('"' + arch_instance.tmp_script_path + '" exists while it should not', script_name)

    tool_dirs = eda_tools.get_tool_dirs(tool)
    if not tool_dirs:
        printc.error('No directory found for the selected eda tool "' + tool + '"', script_name)
        return False

    # A tool can be defined in both the built-in and the user directory (a
    # user adding flows to a built-in tool): copy the scripts of every
    # location, the user ones last so they win.
    for tool_dir in tool_dirs:
        tcl_dir = os.path.join(tool_dir, hard_settings.tool_tcl_path)
        if os.path.isdir(tcl_dir):
            copytree(tcl_dir, arch_instance.tmp_script_path, dirs_exist_ok=True)
    return True


def write_job_identity_files(arch_instance, flow=None):
    """
    Write the files naming what a job directory holds: its target, its
    architecture, and the flow it ran with (so a later full re-export can tag
    the results with it).
    """
    with open(os.path.join(arch_instance.tmp_dir, hard_settings.target_filename), "w") as f:
        print(arch_instance.target, file=f)
    with open(os.path.join(arch_instance.tmp_dir, hard_settings.arch_filename), "w") as f:
        print(arch_instance.arch_name, file=f)
    if flow:
        with open(os.path.join(arch_instance.tmp_dir, hard_settings.flow_filename), "w") as f:
            print(flow, file=f)


def rewrite_tcl_source_paths(arch_instance, check_cancel=None):
    """
    Rewrite the "source scripts/<x>.tcl" lines of every tcl script of a job into
    absolute paths, so a script keeps sourcing its siblings whatever directory
    the tool runs from.
    """
    for filename in os.listdir(arch_instance.tmp_script_path):
        if not filename.endswith(".tcl"):
            continue
        if check_cancel is not None:
            check_cancel()
        with open(os.path.join(arch_instance.tmp_script_path, filename), "r") as f:
            tcl_content = f.read()
        pattern = re.escape(hard_settings.source_tcl) + r"(.+?\.tcl)"

        def replace_path(match):
            return "source " + os.path.join(os.path.realpath(arch_instance.tmp_script_path), match.group(1)).replace('\\', '/')

        tcl_content = re.sub(pattern, replace_path, tcl_content)
        with open(os.path.join(arch_instance.tmp_script_path, filename), "w") as f:
            f.write(tcl_content)


def build_job_variables(arch_instance, tool, **extra):
    """
    The variables a tool.yml command of this job can use ($work_path,
    $script_path, ...). `extra` adds job-type specific ones (a place & route job
    passes the directory of the synthesis it starts from).
    """
    import odatix.lib.eda_tools as eda_tools
    from odatix.lib.settings import OdatixSettings

    return Variables(
        work_path=os.path.realpath(arch_instance.tmp_dir),
        tool_install_path=os.path.realpath(arch_instance.install_path),
        odatix_path=OdatixSettings.odatix_path,
        odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
        tool_path=eda_tools.get_tool_dir(tool),
        script_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_script_path)),
        log_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path)),
        rtl_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_rtl_path)),
        report_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_report_path)),
        result_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_result_path)),
        clock_signal=arch_instance.clock_signal,
        top_level_module=arch_instance.top_level_module,
        lib_name=arch_instance.lib_name,
        architecture=arch_instance.arch_display_name,
        target=arch_instance.target,
        tool=tool,
        **extra,
    )


def group_steps(steps):
    """
    Group the steps of a run into the processes that will run them.

    Consecutive steps sharing a session of the tool are run by a single process:
    the tool is opened once, sources what each of them adds, and exits. A step
    declaring its whole command, or one whose session differs from its
    neighbour's, starts a group of its own.

    Returns a list of lists of steps, in order.
    """
    groups = []
    for step in steps:
        session = step.get("session")
        if groups and session is not None and groups[-1][0].get("session") == session:
            groups[-1].append(step)
        else:
            groups.append([step])
    return groups


def group_command(group):
    """
    The command running a group of steps: the step's own when it runs alone,
    otherwise one session of the tool sourcing what each step of the group adds.
    """
    if len(group) == 1:
        return group[0]["command"]
    session = group[0]["session"]
    command = list(session["command"]) + list(session.get("begin") or [])
    for step in group:
        command += list(step["args"])
    return command + list(session.get("end") or [])


def build_job_command(command, steps, variables, start_index=0):
    """
    Resolve what a job runs: a single command, or the ordered pipeline of a flow
    split into steps. Integer stage keys keep the declared order (see
    ParallelJobHandler._build_task_pipeline).

    Only the steps left to do are built: `start_index` is where the job resumes
    (see odatix.lib.job_steps), so the pipeline holds exactly what this run has
    to execute, and a session covers exactly those steps.

    Each task names the steps it covers ("steps"), since a task running a whole
    session stands for several of them.

    On top of the usual variables, a step (or the session running it) can use
    $first_step, $last_step and $steps, which name the steps the process about to
    run covers. A session writing its log to "$log_path/$first_step.log" gives
    one log per run rather than one shared file a resuming run would overwrite.
    """
    def _flatten(value):
        return " ".join(map(str, value)) if isinstance(value, list) else value

    def _replace_step_variables(text, names):
        for key, value in (("$first_step", names[0]), ("$last_step", names[-1]), ("$steps", "-".join(names))):
            text = text.replace(key, value)
        return text

    if steps:
        remaining = steps[max(0, int(start_index or 0)):]
        pipeline = {}
        for index, group in enumerate(group_steps(remaining)):
            names = [step["name"] for step in group]
            pipeline[index] = [{
                "name": " + ".join(names),
                "steps": names,
                "command": _replace_step_variables(replace_variables(_flatten(group_command(group)), variables), names),
            }]
        return pipeline
    return replace_variables(_flatten(command), variables)


def build_parallel_job(
    arch_instance,
    command,
    steps,
    resume_index,
    flow,
    log_size_limit,
    progress_mode,
):
    """Build the ParallelJob the handler runs for one job directory."""
    fmax_status_file = os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path, hard_settings.fmax_status_filename)
    synth_status_file = os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path, hard_settings.synth_status_filename)

    job = ParallelJob(
        process=None,
        command=command,
        directory=".",
        generate_rtl=arch_instance.generate_rtl,
        generate_command=arch_instance.generate_command,
        target=arch_instance.target,
        arch=arch_instance.arch_name,
        display_name=arch_instance.arch_display_name,
        status_file=fmax_status_file,
        progress_file=synth_status_file,
        tmp_dir=arch_instance.tmp_dir,
        log_size_limit=log_size_limit,
        progress_mode=progress_mode,
        status="idle",
    )

    if steps:
        # The pipeline holds only what is left to do (see build_job_command);
        # the full list of steps the run covers and where it resumes are what
        # the progress of the run is scaled on.
        job.step_names = [step["name"] for step in steps]
        job.resume_step_index = resume_index
        job.step_tracking = {"tmp_dir": os.path.realpath(arch_instance.tmp_dir), "flow": flow}

    return job


def build_prepare_synthesis_job(
    arch_handler,
    arch_path,
    tool,
    log_size_limit,
    debug,
    timestamp,
    progress_mode,
    script_name,
    flow=None,
    steps=None,
    rerun_index=None,
    check_cancel=None,
):
    from odatix.lib.settings import OdatixSettings
    from odatix.lib.architecture_handler import Architecture
    from odatix.components.run_common import replace_and_write_param_domains

    def _prepare_job(arch_instance, job_list):
        if check_cancel is not None:
            check_cancel()

        # What this directory has already done has to be read *before* it is
        # refreshed, and a resuming job must keep what the completed steps
        # produced: their checkpoints, reports and the step state itself. Only a
        # job starting from scratch wipes its directory. An overwrite always
        # counts as starting from scratch, even if leftover step state would
        # otherwise look resumable.
        # An overwrite always restarts from scratch: neither the leftover step
        # state nor the directory content is carried over.
        if arch_handler.overwrite:
            resume_index = 0
        else:
            resume_index = job_steps.start_index(arch_instance.tmp_dir, steps, rerun_index) if steps else 0
        resuming = resume_index > 0

        prepare_job_directory(arch_instance, resuming)

        if not copy_job_scripts(arch_instance, tool, resuming, script_name):
            return

        if arch_instance.design_path is not None:
            if not os.path.isdir(arch_instance.design_path):
                printc.error('The design directory "' + arch_instance.design_path + '" does not exist', script_name)
                return
            copytree(
                src=arch_instance.design_path,
                dst=arch_instance.tmp_dir,
                whitelist=arch_instance.design_path_whitelist,
                blacklist=arch_instance.design_path_blacklist,
                dirs_exist_ok=True,
            )

        if not arch_instance.generate_rtl:
            copytree(arch_instance.rtl_path, os.path.join(arch_instance.tmp_dir, hard_settings.work_rtl_path), dirs_exist_ok=True)

        if arch_instance.use_parameters:
            if debug:
                printc.subheader("Replace main parameters")
            param_target_file = resolve_param_target_file(
                arch_instance.tmp_dir, arch_instance.param_target_filename, arch_instance.generate_rtl
            )
            param_filename = selected_config_file(arch_path, arch_instance.arch_name)
            replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_filename,
                output_file=param_target_file,
                start_delimiter=arch_instance.start_delimiter,
                stop_delimiter=arch_instance.stop_delimiter,
                replace_all_occurrences=False,
                silent=False if debug else True,
            )
            if debug:
                print()

        replace_and_write_param_domains(
            tmp_dir=arch_instance.tmp_dir,
            arch_name=arch_instance.arch_name,
            param_domains=arch_instance.param_domains,
            default_target_filename=arch_instance.param_target_filename,
            target_filename_getter=lambda param_domain: param_domain.param_target_file,
            debug=debug,
            generate_rtl=arch_instance.generate_rtl,
            timestamp=timestamp,
            virtual_domains=getattr(arch_instance, "virtual_param_domains", None),
            arch_path=arch_path,
        )

        write_job_identity_files(arch_instance, flow)

        if arch_instance.file_copy_enable:
            file_copy_dest = os.path.join(arch_instance.tmp_dir, arch_instance.file_copy_dest)
            try:
                shutil.copy2(arch_instance.file_copy_source, file_copy_dest)
            except Exception as e:
                printc.error(
                    'Could not copy "' + arch_instance.script_copy_source + '" to "' + os.path.realpath(file_copy_dest) + '"',
                    script_name,
                )
                printc.cyan("error details: ", end="", script_name=script_name)
                print(str(e))
                return

        if arch_instance.script_copy_enable:
            try:
                shutil.copy2(arch_instance.script_copy_source, arch_instance.tmp_script_path)
            except Exception as e:
                printc.error(
                    'Could not copy "'
                    + arch_instance.script_copy_source
                    + '" to "'
                    + os.path.realpath(arch_instance.tmp_script_path)
                    + '"',
                    script_name,
                )
                printc.cyan("error details: ", end="", script_name=script_name)
                print(str(e))
                return

        if not constraint_files.copy_constraint_files(arch_instance):
            return

        tcl_config_file = os.path.join(arch_instance.tmp_script_path, hard_settings.tcl_config_filename)
        edit_config_file(arch_instance, tcl_config_file)

        yaml_config_file = os.path.join(arch_instance.tmp_dir, hard_settings.yaml_config_filename)
        Architecture.write_yaml(arch_instance, yaml_config_file)

        rewrite_tcl_source_paths(arch_instance, check_cancel)

        variables = build_job_variables(arch_instance, tool)
        command = build_job_command(arch_handler.command, steps, variables, start_index=resume_index)

        running_arch = build_parallel_job(
            arch_instance,
            command=command,
            steps=steps,
            resume_index=resume_index,
            flow=flow,
            log_size_limit=log_size_limit,
            progress_mode=progress_mode,
        )

        job_list.append(running_arch)

    return _prepare_job


def prepare_synthesis_jobs(
    architecture_instances,
    prepare_job,
    job_list,
    process_group,
    tool_settings_file,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    check_cancel=None,
    script_name=None,
):
    run_prepare_loop(
        instances=architecture_instances,
        build_job=lambda arch_instance: prepare_job(arch_instance, job_list),
        job_list=job_list,
        check_cancel=check_cancel,
    )

    # An architecture can pass the initial checklist but still fail while its
    # job is being built (e.g. a missing design_path): do not launch the
    # monitor/daemon session with zero jobs if every one of them failed.
    abort_if_empty_job_list(job_list, script_name=script_name)

    parallel_jobs = ParallelJobHandler(
        job_list,
        nb_jobs,
        process_group,
        auto_exit=exit_when_done,
        format_yaml=tool_settings_file,
        log_size_limit=log_size_limit,
    )
    return parallel_jobs
