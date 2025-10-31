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
import shutil
import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from datetime import datetime

import odatix.components.motd as motd
import odatix.lib.hard_settings as hard_settings
from odatix.lib.utils import copytree
from typing import Optional


######################################
# Architectures and Simulations
######################################

def get_instances(path: str) -> list:
    """
    Get the list of architectures or simulations.
    """
    if not os.path.exists(path):
        return []
    return sorted([
        d for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d))
    ])

def get_simulations(path: str) -> list:
    """
    Get the list of simulations.
    """
    return get_instances(path)

def get_architectures(path: str) -> list:
    """
    Get the list of architectures.
    """
    return get_instances(path)

def instance_exists(path, name) -> bool:
    """
    Check if a specific architecture or simulation exists.
    """
    path = os.path.join(path, name)
    return os.path.isdir(path)

def architecture_exists(path, name) -> bool:
    """
    Check if a specific architecture exists.
    """
    return instance_exists(path, name)

def simulation_exists(path, name) -> bool:
    """
    Check if a specific simulation exists.
    """
    return instance_exists(path, name)

def duplicate_instance(path, source_name, target_name) -> None:
    """
    Duplicate an architecture or simulation.
    """
    source_path = os.path.join(path, source_name)
    target_path = os.path.join(path, target_name)
    if not os.path.isdir(source_path):
        raise ValueError(f"Source instance '{source_name}' does not exist.")
    if os.path.exists(target_path):
        raise ValueError(f"Target instance '{target_name}' already exists.")
    copytree(source_path, target_path)

def delete_instance(path, name) -> None:
    """
    Delete an architecture or simulation.
    """
    path = os.path.join(path, name)
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)

def rename_instance(path, old_name, new_name) -> None:
    """
    Rename an architecture or simulation.
    """
    old_path = os.path.join(path, old_name)
    new_path = os.path.join(path, new_name)
    if not os.path.isdir(old_path):
        return
    if os.path.exists(new_path):
        return
    shutil.move(old_path, new_path)

def rename_architecture(path, old_name, new_name) -> None:
    """
    Rename an architecture.
    """
    rename_instance(path, old_name, new_name)

def rename_simulation(path, old_name, new_name) -> None:
    """
    Rename a simulation.
    """
    rename_instance(path, old_name, new_name)

def create_instance(path, name) -> None:
    """
    Create a new architecture or simulation.
    """
    instance_path = os.path.join(path, name)
    os.makedirs(instance_path, exist_ok=True)

def create_architecture(path, name) -> None:
    """
    Create a new architecture.
    """
    create_instance(path, name)

def create_simulation(path, name) -> None:
    """
    Create a new simulation.
    """
    create_instance(path, name)

######################################
# Architecture Settings
######################################
 
def load_architecture_settings(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> dict:
    """
    Load the settings of a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def save_architecture_settings(arch_path, arch_name, settings) -> None:
    """
    Save the settings of a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, hard_settings.main_parameter_domain)
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, hard_settings.param_settings_filename)

    yaml_obj = YAML()

    data = CommentedMap()

    data.yaml_set_start_comment(
f"""##############################################
# Settings for {arch_name}
##############################################

# This file was generated by Odatix GUI {motd.read_version()} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
# You can still modify manually this file as needed.
"""
    )

    generate_rtl = settings.get('generate_rtl', False)
    data['generate_rtl'] = generate_rtl
    data.yaml_set_comment_before_after_key('generate_rtl', before="\nRTL generation")
    
    if generate_rtl:
        data['design_path'] = settings.get('design_path', [])
        data['design_path_whitelist'] = settings.get('design_path_whitelist', [])
        data['design_path_blacklist'] = settings.get('design_path_blacklist', [])
        data['generate_command'] = settings.get('generate_command', "")
        data['generate_output'] = settings.get('generate_output', "")
    else:
        data['rtl_path'] = settings.get('rtl_path', "")
    data['top_level_file'] = settings.get('top_level_file', "")
    data['top_level_module'] = settings.get('top_level_module', "")
    if generate_rtl:
        data.yaml_set_comment_before_after_key('top_level_file', before="\nSource files")
    else:
        data.yaml_set_comment_before_after_key('rtl_path', before="\nSource files")

    data['clock_signal'] = settings.get('clock_signal', "")
    data['reset_signal'] = settings.get('reset_signal', "")
    data.yaml_set_comment_before_after_key('clock_signal', before="\nSignals")

    data['use_parameters'] = settings.get('use_parameters', False)
    data['start_delimiter'] = settings.get('start_delimiter', "")
    data['stop_delimiter'] = settings.get('stop_delimiter', "")
    data.yaml_set_comment_before_after_key('use_parameters', before="\nDelimiters for parameter files")

    fmax = CommentedMap()
    settings_fmax = settings.get('fmax_synthesis', {})
    fmax['lower_bound'] = settings_fmax.get('lower_bound', hard_settings.default_fmax_lower_bound)
    fmax['upper_bound'] = settings_fmax.get('upper_bound', hard_settings.default_fmax_upper_bound)
    data['fmax_synthesis'] = fmax
    data.yaml_set_comment_before_after_key('fmax_synthesis', before="\nDefault frequencies (in MHz)")

    custom = CommentedMap()
    settings_custom = settings.get('custom_freq_synthesis', {})
    custom_list = CommentedSeq(settings_custom.get('list', []))
    custom_list.fa.set_flow_style()
    custom['list'] = custom_list    
    data['custom_freq_synthesis'] = custom

    generate_configurations = settings.get('generate_configurations', False)
    data['generate_configurations'] = generate_configurations
    settings_gen = settings.get('generate_configurations_settings', {})
    if settings_gen:
        data['generate_configurations_settings'] = settings_gen
    data.yaml_set_comment_before_after_key('generate_configurations', before="\nConfiguration generation")

    with open(path, "w") as f:
        yaml_obj.dump(data, f)


######################################
# Parameter Domains
######################################

def get_arch_domain_path(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> str:
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
    domain_list = [
        d for d in os.listdir(folder)
        if os.path.isdir(os.path.join(folder, d)) and not d.startswith("_")
    ]
    return sorted(domain_list)

def create_parameter_domain(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> None:
    """
    Create a new parameter domain for a specific architecture.
    """
    path = os.path.join(arch_path, arch_name, domain)
    os.makedirs(path, exist_ok=True)

def duplicate_parameter_domain(arch_path, source_arch_name, target_arch_name, source_domain, target_domain) -> None:
    """
    Duplicate a parameter domain for a specific architecture.
    """
    if target_domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot duplicate to the main parameter domain.")
    if target_domain == source_domain and source_arch_name == target_arch_name:
        raise ValueError("Source and target domain cannot be the same.")
    
    source_path = get_arch_domain_path(arch_path, source_arch_name, source_domain)
    target_path = get_arch_domain_path(arch_path, target_arch_name, target_domain)
    if not os.path.isdir(source_path):
        return
    if os.path.exists(target_path):
        return
    
    if source_domain == hard_settings.main_parameter_domain:
        # copy only the files in the main domain folder, not the folders
        for item in os.listdir(source_path):
            s = os.path.join(source_path, item)
            d = os.path.join(target_path, item)
            if os.path.isdir(s):
                continue
            os.makedirs(target_path, exist_ok=True)
            with open(s, "rb") as fsrc:
                with open(d, "wb") as fdst:
                    fdst.write(fsrc.read())
            # overwrite the settings file to remove unwanted keys
            settings = load_architecture_settings(arch_path, source_arch_name, source_domain)
            save_domain_settings(arch_path, target_arch_name, target_domain, settings)
    else:
        # copy the entire folder
        copytree(source_path, target_path)

def delete_parameter_domain(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> None:
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

def parameter_domain_exists(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> bool:
    """
    Check if a specific parameter domain exists.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    return os.path.isdir(path)

#######################################
# Parameter Domain Settings
#######################################

def save_domain_settings(arch_path, arch_name, domain, settings) -> None:
    """
    Save the settings of a specific parameter domain of an architecture.
    """
    if domain == hard_settings.main_parameter_domain:
        settings = update_raw_settings(arch_path, arch_name, domain, settings)
        save_architecture_settings(arch_path, arch_name, settings)
        return
    
    path = get_arch_domain_path(arch_path, arch_name, domain)
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, hard_settings.param_settings_filename)

    yaml_obj = YAML()

    data = CommentedMap()

    data.yaml_set_start_comment(
f"""##############################################
# Settings for {arch_name} - {domain}
##############################################

# This file was generated by Odatix GUI {motd.read_version()} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
# You can still modify manually this file as needed.
"""
    )

    data['use_parameters'] = settings.get('use_parameters', True)
    data['param_target_file'] = settings.get('param_target_file', "")
    data['start_delimiter'] = settings.get('start_delimiter', "")
    data['stop_delimiter'] = settings.get('stop_delimiter', "")
    data.yaml_set_comment_before_after_key('param_target_file', before="\nDelimiters for parameter files")

    data['generate_configurations'] = settings.get('generate_configurations', False)
    settings_gen = settings.get('generate_configurations_settings', {})
    data['generate_configurations_settings'] = settings_gen
    data.yaml_set_comment_before_after_key('generate_configurations', before="\nConfiguration generation settings")

    with open(path, "w") as f:
        yaml_obj.dump(data, f)

def update_domain_settings(arch_path, arch_name, domain, settings_to_update) -> None:
    """
    Update only the provided settings in the YAML file, preserving comments and other keys.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)

    if not os.path.exists(path):
        save_domain_settings(arch_path, arch_name, domain, settings_to_update)
        return

    yaml_obj = YAML()

    # Load current settings with comments
    if os.path.exists(path):
        with open(path, "r") as f:
            settings = yaml_obj.load(f)
            if settings is None:
                settings = CommentedMap()
    else:
        settings = CommentedMap()

    # Update only the provided keys
    for k, v in settings_to_update.items():
        # Special handling for 'generate_configurations_settings' to preserve list formatting
        if k == "generate_configurations_settings" and isinstance(v, dict):
            _compact_list_variables_in_config_settings(v)
        settings[k] = v

    # Save back, preserving comments and formatting
    with open(path, "w") as f:
        yaml_obj.dump(settings, f)


######################################
# Configuration Files
######################################

def get_config_files(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> list:
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
    os.makedirs(path, exist_ok=True)
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

def delete_all_config_files(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> None:
    """
    Delete all configuration files for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    if not os.path.isdir(path):
        return
    for f in os.listdir(path):
        if f.endswith(".txt"):
            os.remove(os.path.join(path, f))


#######################################
# Configuration Generation
#######################################

def create_config_gen_dict(name: str, template: str, variables: dict) -> dict:
    """
    Create a configuration generation dictionary.

    Args:
        name (str): Name of the configuration.
        template (str): Template string for the configuration name.
        variables (dict): Dictionary of variables and their values.

    Returns:
        dict: Configuration generation dictionary.
    """
    return {
        'generate_configurations': True,
        'generate_configurations_settings': {
            'name': name,
            'template': template,
            'variables': variables,
        }
    }

def create_config_gen_variable_dict(name: str, type: str, settings: dict, format: Optional[str]=None) -> dict:
    """
    Create a configuration generation variable dictionary.

    Args:
        name (str): Name of the variable.
        type (str): Type of the variable (e.g., 'range', 'list', 'function').
        settings (dict): Settings specific to the variable type.

    Returns:
        dict: Configuration generation variable dictionary.
    """
    var_dict = {
        name: {
            'type': type,
            'settings': settings,
        }
    }
    if format:
        var_dict[name]['format'] = format
    return var_dict


#######################################
# Helpers
#######################################

def _compact_list_variables_in_config_settings(config_settings: dict):
    """
    Edit the 'variables' in 'generate_configurations_settings' to ensure lists are compact in YAML.
    Args:
        config_settings (dict): The configuration settings dictionary.    
    """
    variables = config_settings.get("variables", {})
    for var_name, var_cfg in variables.items():
        if (
            isinstance(var_cfg, dict)
            and var_cfg.get("type") == "list"
            and "settings" in var_cfg
            and isinstance(var_cfg["settings"], dict)
            and "list" in var_cfg["settings"]
        ):
            compact_list = CommentedSeq(var_cfg["settings"]["list"])
            compact_list.fa.set_flow_style()
            var_cfg["settings"]["list"] = compact_list

def update_raw_settings(arch_path, arch_name, domain, settings_to_update) -> dict:
    """
    Update only the provided keys from a yaml file, without any formatting.
    Args:
        arch_path (str): Path to the architectures folder.
        arch_name (str): Name of the architecture.
        domain (str): Name of the parameter domain.
        settings_to_update (dict): Dictionary of settings to update.
    Returns:
        dict: Updated settings.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)

    # Load current settings if the file exists
    if os.path.exists(path):
        with open(path, "r") as f:
            settings = yaml.safe_load(f) or {}
    else:
        settings = {}

    # Update only the provided keys
    for k, v in settings_to_update.items():
        settings[k] = v
    
    return settings
