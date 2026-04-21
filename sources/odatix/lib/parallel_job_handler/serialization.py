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

"""Serialization helpers for transporting ParallelJob objects over JSON."""

from odatix.lib.parallel_job_handler.job import ParallelJob


def _task_name(task):
    if isinstance(task, dict):
        name = task.get("name", None)
    else:
        name = getattr(task, "name", None)
    if name is None and hasattr(task, "getName"):
        name = task.getName()
    if name is None:
        name = str(task)
    return str(name)


def _task_command(task):
    if isinstance(task, dict):
        command = task.get("command", None)
    else:
        command = getattr(task, "command", None)
    if command is None and hasattr(task, "getCommand"):
        command = task.getCommand()
    if command is None:
        command = ""
    if isinstance(command, list):
        command = "\n".join(map(str, command))
    return str(command)


def _stage_sort_key(stage):
    if isinstance(stage, int):
        return (0, stage)
    stage_str = str(stage)
    if stage_str.lstrip("-").isdigit():
        return (0, int(stage_str))
    return (1, stage_str)


def serialize_command(command):
    if isinstance(command, str):
        return {"type": "shell", "value": command}

    if isinstance(command, dict):
        stages = []
        for stage, tasks in sorted(command.items(), key=lambda item: _stage_sort_key(item[0])):
            stage_tasks = []
            for task in tasks:
                stage_tasks.append(
                    {
                        "name": _task_name(task),
                        "command": _task_command(task),
                    }
                )
            stages.append(
                {
                    "stage": stage,
                    "tasks": stage_tasks,
                }
            )
        return {"type": "pipeline", "stages": stages}

    raise TypeError("Unsupported command type: {}".format(type(command).__name__))


def deserialize_command(payload):
    if not isinstance(payload, dict):
        raise ValueError("command payload must be an object")

    kind = payload.get("type")
    if kind == "shell":
        value = payload.get("value", "")
        return str(value)

    if kind == "pipeline":
        stages = payload.get("stages")
        if not isinstance(stages, list):
            raise ValueError("pipeline command must contain a 'stages' list")

        command = {}
        for stage_entry in stages:
            if not isinstance(stage_entry, dict):
                raise ValueError("invalid stage entry in pipeline command")

            stage = stage_entry.get("stage")
            stage_key = stage
            if isinstance(stage, str) and stage.lstrip("-").isdigit():
                stage_key = int(stage)

            tasks = stage_entry.get("tasks")
            if not isinstance(tasks, list):
                raise ValueError("pipeline stage must contain a 'tasks' list")

            normalized_tasks = []
            for task in tasks:
                if not isinstance(task, dict):
                    raise ValueError("invalid task entry in pipeline command")
                normalized_tasks.append(
                    {
                        "name": str(task.get("name", "task")),
                        "command": str(task.get("command", "")),
                    }
                )

            command[stage_key] = normalized_tasks
        return command

    raise ValueError("Unknown command type '{}'".format(kind))


def job_to_payload(job):
    return {
        "command": serialize_command(job.command),
        "directory": str(job.directory),
        "generate_rtl": bool(job.generate_rtl),
        "generate_command": str(job.generate_command or ""),
        "target": str(job.target or ""),
        "arch": str(job.arch or ""),
        "display_name": str(job.display_name or "job"),
        "status_file": str(job.status_file or ""),
        "progress_file": str(job.progress_file or ""),
        "tmp_dir": str(job.tmp_dir or "."),
        "log_size_limit": int(getattr(job, "log_size_limit", 200)),
        "progress_mode": str(getattr(job, "progress_mode", "default")),
    }


def payload_to_job(payload, default_log_size_limit=200):
    if not isinstance(payload, dict):
        raise ValueError("job payload must be an object")

    command_payload = payload.get("command")
    command = deserialize_command(command_payload)

    log_size_limit = payload.get("log_size_limit", default_log_size_limit)

    return ParallelJob(
        process=None,
        command=command,
        directory=str(payload.get("directory", ".")),
        generate_rtl=bool(payload.get("generate_rtl", False)),
        generate_command=str(payload.get("generate_command", "")),
        target=str(payload.get("target", "")),
        arch=str(payload.get("arch", "")),
        display_name=str(payload.get("display_name", "job")),
        status_file=str(payload.get("status_file", "")),
        progress_file=str(payload.get("progress_file", "")),
        tmp_dir=str(payload.get("tmp_dir", ".")),
        log_size_limit=int(log_size_limit),
        progress_mode=str(payload.get("progress_mode", "default")),
        status="idle",
    )
