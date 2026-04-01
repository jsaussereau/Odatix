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
import time
import signal

import odatix.lib.printc as printc

class ParallelJob:
    status_file_pattern = re.compile(r"(.*)")
    progress_file_pattern = re.compile(r"(.*)")

    def __init__(
        self,
        process,
        command,
        directory,
        generate_rtl,
        generate_command,
        target,
        arch,
        display_name,
        status_file,
        progress_file,
        tmp_dir,
        log_size_limit,
        progress_mode="default",
        status="not started",
    ):
        self.process = process
        self.command = command
        self.directory = directory
        self.generate_rtl = generate_rtl
        self.generate_command = generate_command
        self.target = target
        self.arch = arch
        self.display_name = display_name
        self.status_file = status_file
        self.progress_file = progress_file
        self.tmp_dir = tmp_dir
        self.log_size_limit = log_size_limit
        self.progress_mode = progress_mode
        self.status = status

        self.log_history = []
        self.log_position = 0
        self.log_changed = False
        self.autoscroll = True

        self.start_time = None
        self.stop_time = None

    @staticmethod
    def set_patterns(progress_file_pattern, status_file_pattern=None):
        ParallelJob.status_file_pattern = status_file_pattern
        ParallelJob.progress_file_pattern = progress_file_pattern

    def get_progress(self):
        if self.progress_mode == "fmax":
            return self.get_progress_fmax()
        else:
            progress = 0
            if os.path.isfile(self.progress_file):
                with open(self.progress_file, "r") as f:
                    content = f.read()
                for match in re.finditer(ParallelJob.progress_file_pattern, content):
                    parts = ParallelJob.progress_file_pattern.search(match.group())
                    if len(parts.groups()) >= 2:
                        progress = int(parts.group(2))
            if progress > 100:
                progress = 100
            return progress

    def get_progress_fmax(self):
        # Get progress from status file
        fmax_progress = 0
        fmax_step = 1
        fmax_totalstep = 1
        if os.path.isfile(self.status_file):
            with open(self.status_file, "r") as f:
                content = f.read()
            for match in re.finditer(ParallelJob.status_file_pattern, content):
                parts = ParallelJob.status_file_pattern.search(match.group())
                if len(parts.groups()) >= 4:
                    fmax_progress = int(parts.group(2))
                    fmax_step = int(parts.group(3))
                    fmax_totalstep = int(parts.group(4))

        # Get progress from synth status file
        synth_progress = 0
        if os.path.isfile(self.progress_file):
            with open(self.progress_file, "r") as f:
                content = f.read()
            for match in re.finditer(ParallelJob.progress_file_pattern, content):
                parts = ParallelJob.progress_file_pattern.search(match.group())
                if len(parts.groups()) >= 2:
                    synth_progress = int(parts.group(2))

        # Compute total progress
        if fmax_totalstep != 0:
            progress = fmax_progress + synth_progress / fmax_totalstep
        else:
            progress = synth_progress

        if progress > 100:
            progress = 100
        return progress

    def pause(self):
        """Suspend the job execution."""
        if self.process and self.status == "running":
            os.killpg(os.getpgid(self.process.pid), signal.SIGSTOP) # Suspend process
            self.status = "paused"
            self.stop_time = time.time()
            self.log_history.append(printc.colors.BLUE + "Job paused by user" + printc.colors.ENDC)

    def resume(self):
        """Resume the job execution."""
        if self.process and self.status == "paused":
            os.killpg(os.getpgid(self.process.pid), signal.SIGCONT) # Resume execution
            self.status = "running"
            self.start_time += time.time() - self.stop_time # Adjust the start time to reflect the paused duration
            self.stop_time = None
            self.log_history.append(printc.colors.GREEN + "Job resumed by user" + printc.colors.ENDC)
