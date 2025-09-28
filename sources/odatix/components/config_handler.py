
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
import yaml

import odatix.lib.hard_settings as hard_settings
from odatix.lib.utils import copytree

def get_arch_domain_path(arch_path, arch_name, domain) -> str:
    """
    Get the path of a specific parameter domain.
    """
    if domain == hard_settings.main_parameter_domain:
        return os.path.join(arch_path, arch_name)
    else:
        return os.path.join(arch_path, arch_name, domain)


def get_param_domains(arch_path, arch_name) -> list:
    """
    Get the list of parameter domains for a specific architecture.
    """
    folder = os.path.join(arch_path, arch_name)
    if not os.path.isdir(folder):
        return []
    return [
        d for d in os.listdir(folder)
        if os.path.isdir(os.path.join(folder, d)) and not d.startswith("_")
    ]

def get_config_files(arch_path, arch_name, domain) -> list:
    """
    Get the list of configuration files for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    if not os.path.isdir(path):
        return []
    return sorted([
        f for f in os.listdir(path)
        if f.endswith(".txt") and os.path.isfile(os.path.join(path, f))
    ])

def load_config_file(arch_path, arch_name, domain, filename) -> str:
    """
    Load the content of a specific configuration file for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()

def save_config_file(arch_path, arch_name, domain, filename, content) -> None:
    """
    Save the content of a specific configuration file for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, filename)
    with open(path, "w") as f:
        f.write(content)

def delete_config_file(arch_path, arch_name, domain, filename) -> None:
    """
    Delete a specific configuration file for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, filename)
    if os.path.exists(path):
        os.remove(path)

def load_settings(arch_path, arch_name, domain) -> dict:
    """
    Load the settings of a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def save_settings(arch_path, arch_name, domain, settings) -> None:
    """
    Save the settings of a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(settings, f, sort_keys=False)

def create_parameter_domain(arch_path, arch_name, domain) -> None:
    """
    Create a new parameter domain for a specific architecture.
    """
    path = os.path.join(arch_path, arch_name, domain)
    os.makedirs(path, exist_ok=True)

def duplicate_parameter_domain(arch_path, source_arch_name, target_arch_name, source_domain, target_domain) -> None:
    """
    Duplicate a parameter domain for a specific architecture.
    """
    if source_domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot duplicate the main parameter domain.")
    if target_domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot duplicate to the main parameter domain.")
    source_path = os.path.join(arch_path, source_arch_name, source_domain)
    target_path = os.path.join(arch_path, target_arch_name, target_domain)
    if not os.path.isdir(source_path):
        return
    if os.path.exists(target_path):
        return
    copytree(source_path, target_path)

def delete_parameter_domain(arch_path, arch_name, domain) -> None:
    """
    Delete a specific parameter domain for a specific architecture.
    """
    if domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot delete the main parameter domain.")
    path = os.path.join(arch_path, arch_name, domain)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(path)

def rename_parameter_domain(arch_path, arch_name, old_domain, new_domain) -> None:
    """
    Rename a specific parameter domain for a specific architecture.
    """
    if old_domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot rename the main parameter domain.")
    old_path = os.path.join(arch_path, arch_name, old_domain)
    new_path = os.path.join(arch_path, arch_name, new_domain)
    if not os.path.isdir(old_path):
        return
    if os.path.exists(new_path):
        return
    os.rename(old_path, new_path)