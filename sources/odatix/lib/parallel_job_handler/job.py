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
import sys
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

    @staticmethod
    def _extract_int_from_pattern(content, pattern, default_group_index=1):
        if pattern is None:
            return None

        def _int_from_match(parts):
            groups = parts.groups()
            if len(groups) < 1:
                return None

            candidate_indexes = []
            if isinstance(default_group_index, int) and default_group_index >= 1:
                candidate_indexes.append(default_group_index)
            if len(groups) >= 2 and 2 not in candidate_indexes:
                candidate_indexes.append(2)
            if 1 not in candidate_indexes:
                candidate_indexes.append(1)
            for idx in range(1, len(groups) + 1):
                if idx not in candidate_indexes:
                    candidate_indexes.append(idx)

            for idx in candidate_indexes:
                try:
                    value = parts.group(idx)
                except IndexError:
                    continue
                if value in (None, ""):
                    continue
                try:
                    return int(str(value).strip())
                except (TypeError, ValueError):
                    continue
            return None

        # Parse from newest line first so long files remain cheap to process.
        for line in reversed(content.splitlines()):
            # Keep matching bounded even if user regex is overly permissive.
            line_tail = line[-4096:]
            parts = pattern.search(line_tail)
            if parts is None:
                continue
            value = _int_from_match(parts)
            if value is not None:
                return value

            # Final per-line fallback: extract last plain integer token.
            fallback_matches = re.findall(r"[0-9]+", line_tail)
            if fallback_matches:
                try:
                    return int(fallback_matches[-1])
                except (TypeError, ValueError):
                    pass

        # Backward-compatible fallback for patterns that rely on multi-line matching.
        content_tail = content[-65536:]
        parts = pattern.search(content_tail)
        if parts is None:
            # Last-resort fallback without regex match.
            fallback_matches = re.findall(r"[0-9]+", content_tail)
            if fallback_matches:
                try:
                    return int(fallback_matches[-1])
                except (TypeError, ValueError):
                    return None
            return None

        value = _int_from_match(parts)
        if value is not None:
            return value

        fallback_matches = re.findall(r"[0-9]+", content_tail)
        if fallback_matches:
            try:
                return int(fallback_matches[-1])
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _extract_fmax_status(content, pattern):
        if pattern is None:
            return None

        for line in reversed(content.splitlines()):
            line_tail = line[-4096:]
            parts = pattern.search(line_tail)
            if parts is None:
                continue
            if len(parts.groups()) < 4:
                continue
            try:
                return int(parts.group(2)), int(parts.group(3)), int(parts.group(4))
            except (TypeError, ValueError):
                continue

        content_tail = content[-65536:]
        parts = pattern.search(content_tail)
        if parts is None or len(parts.groups()) < 4:
            return None
        try:
            return int(parts.group(2)), int(parts.group(3)), int(parts.group(4))
        except (TypeError, ValueError):
            return None

    def get_progress(self):
        if self.progress_mode == "fmax":
            return self.get_progress_fmax()
        else:
            progress = 0
            if os.path.isfile(self.progress_file):
                with open(self.progress_file, "r") as f:
                    content = f.read()
                parsed_progress = ParallelJob._extract_int_from_pattern(
                    content,
                    ParallelJob.progress_file_pattern,
                    default_group_index=1,
                )
                if parsed_progress is not None:
                    progress = parsed_progress
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
            parsed_fmax_status = ParallelJob._extract_fmax_status(content, ParallelJob.status_file_pattern)
            if parsed_fmax_status is not None:
                fmax_progress, fmax_step, fmax_totalstep = parsed_fmax_status

        # Get progress from synth status file
        synth_progress = 0
        if os.path.isfile(self.progress_file):
            with open(self.progress_file, "r") as f:
                content = f.read()
            parsed_synth_progress = ParallelJob._extract_int_from_pattern(
                content,
                ParallelJob.progress_file_pattern,
                default_group_index=1,
            )
            if parsed_synth_progress is not None:
                synth_progress = parsed_synth_progress

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
            if sys.platform == "win32":
                self.log_history.append(printc.colors.YELLOW + "Pause is not supported on Windows" + printc.colors.ENDC)
                return
            os.killpg(os.getpgid(self.process.pid), signal.SIGSTOP) # Suspend process
            self.status = "paused"
            self.stop_time = time.time()
            self.log_history.append(printc.colors.BLUE + "Job paused by user" + printc.colors.ENDC)

    def resume(self):
        """Resume the job execution."""
        if self.process and self.status == "paused":
            if sys.platform == "win32":
                self.log_history.append(printc.colors.YELLOW + "Resume is not supported on Windows" + printc.colors.ENDC)
                return
            os.killpg(os.getpgid(self.process.pid), signal.SIGCONT) # Resume execution
            self.status = "running"
            self.start_time += time.time() - self.stop_time # Adjust the start time to reflect the paused duration
            self.stop_time = None
            self.log_history.append(printc.colors.GREEN + "Job resumed by user" + printc.colors.ENDC)
