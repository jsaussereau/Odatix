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

    def _read_status_file(self, path):
        """
        Content of a status file the running step has written, or None.

        A flow split into steps runs one process per step, and they all report
        into the same files: what a previous step left there says nothing about
        the one running now, and would be read as "this step is already done"
        for as long as the tool takes to start up. A file older than the step
        reading it is therefore treated as empty.
        """
        if not path or not os.path.isfile(path):
            return None
        step_started_at = getattr(self, "current_step_started_at", None)
        if step_started_at is not None:
            try:
                if os.path.getmtime(path) < step_started_at:
                    return None
            except OSError:
                return None
        with open(path, "r") as f:
            return f.read()

    def _step_position(self):
        """
        Where the running step sits in the run, as (steps done before it, number
        of steps the run covers), or None when there is nothing to scale: a job
        that is not split into steps, or one whose run is a single step.

        The run is not the whole flow: it goes from the step it resumes at (the
        earlier ones are already done, see odatix.lib.job_steps) to the last one
        it was asked for ("--until" already truncated the list).
        """
        step_names = getattr(self, "step_names", None) or []
        total = len(step_names)
        current = getattr(self, "current_step_index", None)
        if total < 2 or current is None:
            return None

        first = max(0, min(int(getattr(self, "resume_step_index", 0) or 0), total - 1))
        span = total - first
        if span < 2:
            return None

        current = max(first, min(int(current) + self._task_step_offset(), total - 1))
        return current - first, span

    def _task_step_offset(self):
        """
        How many steps of the running task it has already finished.

        A task can run several steps in a single process (a flow declaring a
        session), and the status files then report 0-100 once per step. Odatix
        records the steps of a task only when its process exits, but each such
        step records itself as it ends ("odatix_step_done"), so the state file
        is what tells the steps of a still running task apart.
        """
        task_steps = getattr(self, "_current_task_steps", None) or []
        if len(task_steps) < 2:
            return 0
        recorded_before = getattr(self, "_task_steps_recorded_before", None)
        tracking = getattr(self, "step_tracking", None)
        tmp_dir = tracking.get("tmp_dir") if isinstance(tracking, dict) else None
        if recorded_before is None or not tmp_dir:
            return 0
        try:
            import odatix.lib.job_steps as job_steps

            recorded_now = len(job_steps.completed_step_names(tmp_dir))
        except Exception:
            return 0
        return max(0, min(recorded_now - int(recorded_before), len(task_steps) - 1))

    def _scale_to_run(self, progress):
        """Map the progress of the running step (0-100) onto the whole run."""
        position = self._step_position()
        if position is None:
            return progress
        done, span = position
        return (done * 100 + progress) / span

    def get_progress(self):
        if self.progress_mode == "fmax":
            return self.get_progress_fmax()

        progress = 0
        content = self._read_status_file(self.progress_file)
        if content is not None:
            parsed_progress = ParallelJob._extract_int_from_pattern(
                content,
                ParallelJob.progress_file_pattern,
                default_group_index=1,
            )
            if parsed_progress is not None:
                progress = parsed_progress
        if progress > 100:
            progress = 100
        return self._scale_to_run(progress)

    def get_progress_fmax(self):
        # Get progress from status file
        fmax_progress = 0
        fmax_step = 1
        fmax_totalstep = 1
        content = self._read_status_file(self.status_file)
        if content is not None:
            parsed_fmax_status = ParallelJob._extract_fmax_status(content, ParallelJob.status_file_pattern)
            if parsed_fmax_status is not None:
                fmax_progress, fmax_step, fmax_totalstep = parsed_fmax_status

        # Get progress from synth status file
        synth_progress = 0
        content = self._read_status_file(self.progress_file)
        if content is not None:
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
        return self._scale_to_run(progress)

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
