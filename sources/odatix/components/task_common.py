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

"""
Task-list handling shared by every job type that runs a task graph (workflows
and simulations).

A task list is what the "tasks" key of a workflow's or a simulation's settings
file holds: a list of mappings with a "name", a list of "commands", optional
"dependencies", an optional working "path", and optional "platforms". Several
implementations of the same task name may coexist, each declaring the platforms
it applies to; the one matching the current platform wins, falling back to the
implementation that declares no platform at all.
"""


def parse_task_platforms(platforms_value, task_name):
    """
    Normalize the "platforms" value of a task into a non-empty list of platform
    names.

    Raises:
        ValueError: If the value is neither a string nor a list of strings, or
            if it holds no platform at all.
    """
    if isinstance(platforms_value, str):
        platforms = [platforms_value.strip()]
    elif isinstance(platforms_value, (list, tuple, set)):
        platforms = []
        for value in platforms_value:
            if not isinstance(value, str):
                raise ValueError(
                    "Task \"{}\" has an invalid \"platforms\" entry. "
                    "Expected strings, got {}.".format(task_name, type(value).__name__)
                )
            stripped = value.strip()
            if stripped != "":
                platforms.append(stripped)
    else:
        raise ValueError(
            "Task \"{}\" has an invalid \"platforms\" value of type {}. "
            "Expected a string or a list of strings.".format(task_name, type(platforms_value).__name__)
        )

    platforms = [platform for platform in platforms if platform != ""]
    if len(platforms) == 0:
        raise ValueError("Task \"{}\" has an empty \"platforms\" value.".format(task_name))

    return platforms


def select_platform_task_implementations(tasks, current_platform):
    """
    Keep exactly one implementation per task name: the one matching
    current_platform, or the platform-less default when none matches.

    Returns:
        list: The selected tasks, in declaration order, with their "platforms"
        key stripped.

    Raises:
        ValueError: If a task is not a mapping, has no name, declares both
            "platform" and "platforms", or has several implementations
            competing for the same slot.
    """
    grouped_tasks = {}
    ordered_task_names = []

    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each task must be a mapping/object in \"tasks\".")

        task_name = task.get("name")
        if not isinstance(task_name, str) or task_name.strip() == "":
            raise ValueError("Each task must have a non-empty \"name\" key.")
        task_name = task_name.strip()

        if task_name not in grouped_tasks:
            grouped_tasks[task_name] = []
            ordered_task_names.append(task_name)

        grouped_tasks[task_name].append(task)

    selected_tasks = []
    for task_name in ordered_task_names:
        candidates = grouped_tasks[task_name]
        default_implementations = []
        matching_platform_implementations = []

        for candidate in candidates:
            has_platforms_key = "platforms" in candidate and candidate.get("platforms") not in (None, False, "")
            has_legacy_platform_key = "platform" in candidate and candidate.get("platform") not in (None, False, "")

            if has_platforms_key and has_legacy_platform_key:
                raise ValueError(
                    "Task \"{}\" defines both \"platform\" and \"platforms\". "
                    "Please keep only \"platforms\".".format(task_name)
                )

            if not has_platforms_key and not has_legacy_platform_key:
                default_implementations.append(candidate)
                continue

            platforms_value = candidate.get("platforms") if has_platforms_key else candidate.get("platform")
            platforms = parse_task_platforms(platforms_value, task_name)
            if current_platform in platforms:
                matching_platform_implementations.append(candidate)

        if len(default_implementations) > 1:
            raise ValueError(
                "Task \"{}\" has more than one default implementation "
                "(without \"platforms\").".format(task_name)
            )

        if len(matching_platform_implementations) > 1:
            raise ValueError(
                "Task \"{}\" has more than one implementation matching platform \"{}\".".format(
                    task_name, current_platform
                )
            )

        selected_task = None
        if len(matching_platform_implementations) == 1:
            selected_task = matching_platform_implementations[0]
        elif len(default_implementations) == 1:
            selected_task = default_implementations[0]

        if selected_task is None:
            continue

        selected_task = dict(selected_task)
        selected_task.pop("platforms", None)
        selected_task.pop("platform", None)
        selected_tasks.append(selected_task)

    return selected_tasks


def validate_selected_tasks(tasks, current_platform):
    """
    Check that the selected task list is runnable: it has a "main" entry point
    and every dependency it references is part of the selection.

    Raises:
        ValueError: If "main" is missing or a dependency is unresolved.
    """
    task_names = set()
    for task in tasks:
        task_name = task.get("name")
        if isinstance(task_name, str) and task_name.strip() != "":
            task_names.add(task_name.strip())

    if "main" not in task_names:
        raise ValueError(
            "No implementation selected for task \"main\" on platform \"{}\". "
            "Define matching \"platforms\" values or a default implementation without \"platforms\".".format(
                current_platform
            )
        )

    missing_dependencies = []
    for task in tasks:
        task_name = task.get("name", "<unknown>")
        dependencies = task.get("dependencies", [])

        if isinstance(dependencies, str):
            dependencies = [dependencies]

        if not isinstance(dependencies, list):
            continue

        for dependency in dependencies:
            if isinstance(dependency, str) and dependency not in task_names:
                missing_dependencies.append((task_name, dependency))

    if len(missing_dependencies) > 0:
        missing_dependencies = sorted(set(missing_dependencies))
        formatted_missing_dependencies = ", ".join(
            ["\"{}\" -> \"{}\"".format(task_name, dependency) for task_name, dependency in missing_dependencies]
        )
        raise ValueError(
            "Some dependencies reference tasks that are not selected for platform \"{}\": {}".format(
                current_platform, formatted_missing_dependencies
            )
        )
