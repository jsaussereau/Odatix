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
        targ = task.get("name")
        if targ is None:
            raise ValueError("Each task must have a 'name' key.")
        srcs = task.get("dependencies", [])

        tmp_cmds = task["commands"]
        cmds = "\n".join(tmp_cmds)

        maker.addRule(
            target=targ,
            source=srcs,
            command=cmds
        )

    return maker
