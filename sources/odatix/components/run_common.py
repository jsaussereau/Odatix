# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #

import os
import re
import yaml

from odatix.components.replace_params import replace_params
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import ParallelJobHandler


def normalize_run_settings(overwrite, noask, exit_when_done, log_size_limit, nb_jobs, defaults):
    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs = defaults

    overwrite = True if overwrite else _overwrite
    exit_when_done = True if exit_when_done else _exit_when_done
    log_size_limit = int(log_size_limit) if log_size_limit is not None else _log_size_limit
    nb_jobs = int(nb_jobs) if nb_jobs is not None else _nb_jobs

    if noask:
        ask_continue = False

    return overwrite, ask_continue, exit_when_done, log_size_limit, nb_jobs


def confirm_valid_jobs(valid_count, ask_continue, ask_to_continue_callback, script_name=None):
    if valid_count > 0:
        if ask_continue:
            from odatix.lib import printc

            printc.bold("\nTotal: " + str(valid_count))
            ask_to_continue_callback()
    else:
        raise SystemExit(-1)


def replace_and_write_param_domains(
    tmp_dir,
    arch_name,
    param_domains,
    default_target_filename,
    target_filename_getter,
    debug,
    timestamp=None,
):
    domain_dict = {}
    arch_config = re.sub('.*/', '', arch_name)
    domain_dict["__main__"] = arch_config
    if timestamp is not None:
        domain_dict["__timestamp__"] = timestamp

    for param_domain in param_domains:
        if param_domain.use_parameters:
            target_filename = target_filename_getter(param_domain) or default_target_filename
            param_target_file = os.path.join(tmp_dir, target_filename)
            success = replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_domain.param_file,
                output_file=param_target_file,
                start_delimiter=param_domain.start_delimiter,
                stop_delimiter=param_domain.stop_delimiter,
                replace_all_occurrences=False,
                silent=False if debug else True,
            )
            if success:
                domain_dict[param_domain.domain] = param_domain.domain_value

    with open(os.path.join(tmp_dir, hard_settings.param_domains_filename), "w") as param_domains_file:
        yaml.dump(domain_dict, param_domains_file, default_flow_style=False, sort_keys=False)


def start_parallel_jobs(parallel_jobs: ParallelJobHandler, use_api=True, start_headless_on_startup=False):
    if use_api:
        parallel_jobs.start_api_background(
            host="127.0.0.1",
            port=8000,
            start_headless_on_startup=start_headless_on_startup,
            quiet=True,
        )
    if not start_headless_on_startup:
        parallel_jobs.run()
