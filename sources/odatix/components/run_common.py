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
import yaml

from odatix.components.replace_params import replace_params
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import ParallelJobHandler
from odatix.lib.parallel_job_handler.daemon_control import enqueue_parallel_jobs, attach_monitor


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


def start_parallel_jobs(parallel_jobs: ParallelJobHandler, use_api=True, start_headless_on_startup=False, detach=False):
    """Enqueue jobs into the background daemon, then optionally attach monitor.

    The `use_api` and `start_headless_on_startup` arguments are kept for
    backward compatibility with older call sites.
    """
    _state, _response = enqueue_parallel_jobs(parallel_jobs)
    if not detach:
        attach_monitor(
            host=_state.get("host", "127.0.0.1"),
            port=int(_state.get("port", 8000)),
            auto_exit=bool(getattr(parallel_jobs, "auto_exit", False)),
        )
