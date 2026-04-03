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

        commands = task.get("commands", [])
        commands = "\n".join(commands)

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
        )

    return maker
