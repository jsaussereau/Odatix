# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #

import os
import re
import yaml
import shutil

from odatix.components.replace_params import replace_params
from odatix.components.run_common import normalize_run_settings
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.read_tool_settings import read_tool_settings
from odatix.lib.utils import read_from_list, copytree, create_dir, KeyNotInListError, BadValueInListError
from odatix.lib.get_from_dict import get_from_dict
from odatix.lib.prepare_work import edit_config_file
from odatix.lib.check_tool import check_tool
from odatix.lib.run_settings import get_synth_settings
from odatix.lib.variables import replace_variables, Variables


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
    check_cancel=None,
):
    if check_cancel is not None:
        check_cancel()

    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs, architectures = get_synth_settings(run_config_settings_filename)

    work_path = os.path.join(work_path, tool)

    if architectures is None:
        printc.error('The "architectures" section of "' + run_config_settings_filename + '" is empty.', script_name)
        printc.note('You must define your architectures in "' + run_config_settings_filename + '" before using this command.', script_name)
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

    eda_target_filename = os.path.realpath(os.path.join(target_path, "target_" + tool + ".yml"))

    if not os.path.isfile(eda_target_filename):
        printc.error(
            'Target file "' + eda_target_filename + '", for the selected eda tool "' + tool + '" does not exist',
            script_name,
        )
        raise SystemExit(-1)

    from odatix.lib.settings import OdatixSettings

    eda_tool_dir = os.path.join(OdatixSettings.odatix_eda_tools_path, tool)

    if not os.path.isdir(eda_tool_dir):
        printc.error(
            'The directory "' + eda_tool_dir + '", for the selected eda tool "' + tool + '" does not exist',
            script_name,
        )
        if tool not in hard_settings.default_supported_tools:
            printc.note(
                'The selected eda tool "'
                + tool
                + '" is not one of the supported tool. Check out Odatix\'s documentation to add support for your own eda tool',
                script_name,
            )
        raise SystemExit(-1)

    tool_settings_file = os.path.realpath(os.path.join(eda_tool_dir, hard_settings.tool_settings_filename))
    if synth_type is None:
        process_group, report_path, run_command, tool_test_command, _ = read_tool_settings(tool, tool_settings_file)
    else:
        process_group, report_path, run_command, tool_test_command, _ = read_tool_settings(tool, tool_settings_file, synth_type=synth_type)

    with open(eda_target_filename, "r") as f:
        try:
            settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
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
    )
    tool_test_command = replace_variables(tool_test_command, variables)

    if check_eda_tool:
        if check_cancel is not None:
            check_cancel()
        check_tool(
            tool,
            command=tool_test_command,
            supported_tools=hard_settings.default_supported_tools,
            tool_install_path=install_path,
            debug=debug,
        )

    if check_cancel is not None:
        check_cancel()

    return {
        "architectures": architectures,
        "work_path": work_path,
        "tool_settings_file": tool_settings_file,
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
    }


def build_prepare_synthesis_job(
    arch_handler,
    arch_path,
    tool,
    log_size_limit,
    debug,
    timestamp,
    progress_mode,
    script_name,
    check_cancel=None,
):
    from odatix.lib.settings import OdatixSettings
    from odatix.lib.architecture_handler import Architecture
    from odatix.components.run_common import replace_and_write_param_domains

    def _prepare_job(arch_instance, job_list):
        if check_cancel is not None:
            check_cancel()

        create_dir(arch_instance.tmp_dir)
        create_dir(arch_instance.tmp_log_path)

        try:
            copytree(os.path.join(OdatixSettings.odatix_eda_tools_path, hard_settings.common_script_path), arch_instance.tmp_script_path)
        except Exception:
            printc.error('"' + arch_instance.tmp_script_path + '" exists while it should not', script_name)

        copytree(
            os.path.join(OdatixSettings.odatix_eda_tools_path, tool, hard_settings.tool_tcl_path),
            arch_instance.tmp_script_path,
            dirs_exist_ok=True,
        )

        if arch_instance.design_path is not None:
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
            param_target_file = os.path.join(arch_instance.tmp_dir, arch_instance.param_target_filename)
            param_filename = os.path.join(arch_path, arch_instance.arch_name + ".txt")
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
            timestamp=timestamp,
        )

        with open(os.path.join(arch_instance.tmp_dir, hard_settings.target_filename), "w") as f:
            print(arch_instance.target, file=f)
        with open(os.path.join(arch_instance.tmp_dir, hard_settings.arch_filename), "w") as f:
            print(arch_instance.arch_name, file=f)

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

        tcl_config_file = os.path.join(arch_instance.tmp_script_path, hard_settings.tcl_config_filename)
        edit_config_file(arch_instance, tcl_config_file)

        yaml_config_file = os.path.join(arch_instance.tmp_dir, hard_settings.yaml_config_filename)
        Architecture.write_yaml(arch_instance, yaml_config_file)

        for filename in os.listdir(arch_instance.tmp_script_path):
            if filename.endswith(".tcl"):
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

        command = " ".join(map(str, arch_handler.command)) if isinstance(arch_handler.command, list) else arch_handler.command

        variables = Variables(
            work_path=os.path.realpath(arch_instance.tmp_dir),
            tool_install_path=os.path.realpath(arch_instance.install_path),
            odatix_path=OdatixSettings.odatix_path,
            odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
            script_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_script_path)),
            log_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path)),
            clock_signal=arch_instance.clock_signal,
            top_level_module=arch_instance.top_level_module,
            lib_name=arch_instance.lib_name,
        )

        command = replace_variables(command, variables)

        fmax_status_file = os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path, hard_settings.fmax_status_filename)
        synth_status_file = os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path, hard_settings.synth_status_filename)

        running_arch = ParallelJob(
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
):
    for arch_instance in architecture_instances:
        if check_cancel is not None:
            check_cancel()
        prepare_job(arch_instance, job_list)

    parallel_jobs = ParallelJobHandler(
        job_list,
        nb_jobs,
        process_group,
        auto_exit=exit_when_done,
        format_yaml=tool_settings_file,
        log_size_limit=log_size_limit,
    )
    return parallel_jobs
