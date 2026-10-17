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


def createTaskGraph(
    tasks: list,
    path = None,
) -> Maker:
    """
    Create a WoSIT task graph and return it.
    """
    if not isinstance(tasks, list):
        raise TypeError(f"Expected a list for 'tasks', but got {type(tasks).__name__}.")

    maker = Maker()

    for task in tasks:
        target = task.get("name")
        if target is None:
            raise ValueError("Each task must have a 'name' key.")
        sources = task.get("dependencies", [])

        commands = task_command(
            task.get("commands", []),
            task.get("on_failure_commands"),
            task_name=target,
        )

        # Optional task path. It can be absolute or relative to work directory.
        task_path = task.get("path", None) 
        if task_path is not None:
            if os.path.isabs(task_path):
                path = task_path
            else:
                path = os.path.join(path, task_path) if path else task_path
        
        maker.addRule(
            target=target,
            source=sources,
            command=commands,
            path=path,
            phony=True,
        )

    return maker
