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
from wosit.Maker import Maker

def _command_list(commands, key, task_name):
    if commands is None:
        return []
    if isinstance(commands, str):
        commands = [commands]
    if not isinstance(commands, list) or not all(isinstance(command, str) for command in commands):
        raise ValueError(f"\"{key}\" of task \"{task_name}\" must be a list of commands.")
    return commands


def _and_chain(commands):
    """
    Commands as one shell line running them in order, each one only when the
    previous one succeeded. A leading "@" (do not echo) is wosit's own, the
    shell has no use for it.
    """
    lines = [command.strip() for command in commands]
    lines = [line[1:] if line.startswith("@") else line for line in lines]
    return " && ".join(line for line in lines if line)


def task_command(commands, on_failure_commands=None, task_name=""):
    """
    What one task runs, as the command of a WoSIT rule.

    The fallback ("on_failure_commands") runs when one of the commands fails,
    and the task then succeeds if it does. It is folded into the command itself
    rather than handed to WoSIT, because the jobs do not run their tasks through
    WoSIT: the daemon runs each task's command line (see ParallelJobHandler).
    """
    commands = _command_list(commands, "commands", task_name)
    on_failure_commands = _command_list(on_failure_commands, "on_failure_commands", task_name)

    if not on_failure_commands or not _and_chain(commands):
        return "\n".join(commands)
    return "(" + _and_chain(commands) + ") || (" + _and_chain(on_failure_commands) + ")"


def _task_directory(task_path, base_path):
    """
    The directory a task runs in, when it has one of its own ("path"): absolute,
    or relative to the run directory (base_path, the current directory when
    None). Each task resolves its own: the "path" of a task says nothing about
    the next ones.
    """
    if task_path is None:
        return None
    task_path = str(task_path)
    if os.path.isabs(task_path) or not base_path:
        return task_path
    return os.path.join(base_path, task_path)


def _is_phony(task, task_name):
    """
    Whether a task always runs ("phony", the default), or is skipped when the
    file it is named after already exists ("phony: No").
    """
    phony = task.get("phony", True)
    if not isinstance(phony, bool):
        raise ValueError(f"\"phony\" of task \"{task_name}\" must be Yes or No.")
    return phony


def createTaskGraph(
    tasks: list,
    path = None,
    done_command = None,
) -> Maker:
    """
    Create a WoSIT task graph and return it.

    Tasks are named and depend on each other by name. A task with a "path"
    runs its commands from that directory: the jobs run every task's command
    line from the run directory (see ParallelJobHandler), so the directory
    change is part of the command.

    A task is phony, it always runs, unless it says "phony: No": it then stands
    for the file it is named after, relative to its directory, and is skipped
    when that file exists and none of its dependencies has to run.

    Args:
        tasks (list): the task entries of a settings file.
        path (str): the run directory, which relative paths are resolved
            against. The current directory when None.
        done_command (str): a command the task "main" runs last, once
            everything else succeeded.
    """
    if not isinstance(tasks, list):
        raise TypeError(f"Expected a list for 'tasks', but got {type(tasks).__name__}.")

    maker = Maker()

    # What each task stands for in the graph: its name, or the file it produces
    # in its own directory. Dependencies name tasks, they are mapped to that.
    targets = {}
    for task in tasks:
        name = task.get("name")
        if name is None:
            raise ValueError("Each task must have a 'name' key.")
        task_dir = _task_directory(task.get("path"), path)
        target = str(name)
        if not _is_phony(task, name) and task_dir is not None and not os.path.isabs(target):
            target = os.path.join(task_dir, target)
        targets[name] = target

    for task in tasks:
        name = task.get("name")
        task_dir = _task_directory(task.get("path"), path)

        sources = task.get("dependencies", [])
        if sources is None:
            sources = []
        if not isinstance(sources, list):
            sources = [sources]
        resolved_sources = []
        for source in sources:
            if source in targets:
                resolved_sources.append(targets[source])
            elif task_dir is not None and not os.path.isabs(str(source)):
                # A file the task needs, in its own directory.
                resolved_sources.append(os.path.join(task_dir, str(source)))
            else:
                resolved_sources.append(source)

        commands = _command_list(task.get("commands", []), "commands", name)
        on_failure_commands = _command_list(task.get("on_failure_commands"), "on_failure_commands", name)
        if task_dir is not None:
            change_dir = "cd \"" + task_dir + "\""
            commands = [change_dir] + commands
            if on_failure_commands:
                on_failure_commands = [change_dir] + on_failure_commands
        command = task_command(commands, on_failure_commands, task_name=name)
        if done_command and name == "main":
            command = command + "\n" + done_command if command else done_command

        maker.addRule(
            target=targets[name],
            source=resolved_sources,
            command=command,
            phony=_is_phony(task, name),
        )

    return maker
