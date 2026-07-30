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
Virtual parameter domains.

A *physical* parameter domain is a subdirectory of an instance (architecture or
workflow) holding one ``.txt`` configuration file per value. A *virtual*
parameter domain is a variable declared in
``generate_configurations_settings.variables``: it has no directory on disk, but
every combination of its values still expands into its own job, and its value
can be referenced as ``${variable}`` inside commands.

Virtual domains are only expanded when ``generate_configurations`` is disabled,
so the original meaning of ``generate_configurations`` (generating ``.txt``
configuration files) is preserved.

This module is shared by workflows (task commands) and architectures
(``generate_command``).
"""

import os
import re
import yaml

import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.config_generator import ConfigGenerator

script_name = os.path.basename(__file__)

# Both ${name} (group 1) and bare $name (group 2) command placeholders.
COMMAND_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
SAFE_VALUE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


def sanitize_value(value):
    """
    Turn a generated value into something usable as a directory/display name.
    """
    value = str(value).strip()
    if value == "":
        return "_"
    sanitized = SAFE_VALUE_PATTERN.sub("_", value)
    if sanitized == "":
        return "_"
    return sanitized


def read_command_parameter_value(param_file):
    """
    Read the value a parameter domain contributes to a command, or None if the
    parameter file does not exist.
    """
    if param_file is None or not os.path.isfile(param_file):
        return None

    with open(param_file, "r") as f:
        content = f.read().strip()

    if content == "":
        return ""

    # Commands are single-line shell entries, so multi-line values are folded.
    if "\n" in content:
        return " ".join(line.strip() for line in content.splitlines() if line.strip() != "")

    return content


def get_virtual_domain_names(settings):
    """
    Names of the variables of an instance, which act as virtual parameter domains.
    """
    if not isinstance(settings, dict):
        return set()
    generate_settings = settings.get("generate_configurations_settings")
    if not isinstance(generate_settings, dict):
        return set()
    variables = generate_settings.get("variables")
    if not isinstance(variables, dict):
        return set()
    return set(name for name in variables.keys() if isinstance(name, str) and name.strip() != "")


def referenced_variable_names(*values):
    """
    Names referenced as ${name} or $name in the given command strings.
    """
    names = set()
    for value in values:
        if not isinstance(value, str):
            continue
        for match in COMMAND_VAR_PATTERN.finditer(value):
            names.add(match.group(1) if match.group(1) is not None else match.group(2))
    return names


def replace_command_vars(value, substitutions):
    """
    Replace ${name}/$name in a command by its substitution, leaving unknown
    names untouched (they may be environment variables).
    """
    if not isinstance(value, str) or len(substitutions) == 0:
        return value

    def _replace_var(match):
        var_name = match.group(1) if match.group(1) is not None else match.group(2)
        return substitutions.get(var_name, match.group(0))

    return COMMAND_VAR_PATTERN.sub(_replace_var, value)


def split_requested_param_domains(requested_param_domains, virtual_domain_names):
    """
    Split requested "domain/value" selectors into physical and virtual ones.
    """
    physical = []
    virtual = []
    for requested_param_domain in requested_param_domains:
        domain = re.sub("/.*", "", requested_param_domain)
        if domain in virtual_domain_names:
            virtual.append(requested_param_domain)
        else:
            physical.append(requested_param_domain)
    return physical, virtual


def load_instance_settings(base_path, param_dir, param_settings_filename=hard_settings.param_settings_filename):
    """
    Load the settings file of an instance, or None if it is missing/invalid.
    """
    settings_file = os.path.join(base_path, param_dir, param_settings_filename)
    if not os.path.isfile(settings_file):
        return None
    try:
        with open(settings_file, "r") as f:
            settings = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception:
        return None
    return settings if isinstance(settings, dict) else None


def build_variants(settings, settings_file, debug=False, script_name=script_name):
    """
    Build the variants of an instance from generate_configurations_settings.variables.

    Returns a list of {"requested_param_domains": [...], "substitutions": {...}},
    an empty list when there is nothing to generate, or None on error.
    """
    generate_enabled = bool(settings.get("generate_configurations", False))
    if generate_enabled:
        return []

    generate_settings = settings.get("generate_configurations_settings")
    if not isinstance(generate_settings, dict):
        return []

    variables = generate_settings.get("variables")
    if not isinstance(variables, dict) or len(variables) == 0:
        return []

    variable_names = [name for name in variables.keys() if isinstance(name, str) and name.strip() != ""]
    if len(variable_names) == 0:
        printc.error(
            "Invalid variable settings in \""
            + settings_file
            + "\": no valid variable names found in \"generate_configurations_settings.variables\".",
            script_name,
        )
        return None

    synthetic_template = "\n".join([f"{variable_name}: ${{{variable_name}}}" for variable_name in variable_names])
    synthetic_name = "__virtual__" + "__".join([f"${{{variable_name}}}" for variable_name in variable_names])

    generator_data = {
        "generate_configurations": True,
        "generate_configurations_settings": {
            "template": synthetic_template,
            "name": synthetic_name,
            "variables": variables,
        },
    }

    generator = ConfigGenerator(data=generator_data, silent=True, debug=debug)
    if not generator.valid:
        printc.error(
            "Invalid \"generate_configurations_settings.variables\" in settings file \"" + settings_file + "\".",
            script_name,
        )
        return None

    generated = generator.generate()
    if not isinstance(generated, tuple) or len(generated) != 2:
        printc.error(
            "Could not generate variable combinations from \"" + settings_file + "\".",
            script_name,
        )
        return None

    generated_params, _all_values = generated
    if not isinstance(generated_params, dict):
        printc.error(
            "Could not generate variable combinations from \"" + settings_file + "\".",
            script_name,
        )
        return None

    variants = []
    for rendered_values in generated_params.values():
        try:
            parsed_values = yaml.load(rendered_values, Loader=yaml.loader.BaseLoader)
        except yaml.YAMLError as e:
            printc.error(
                "Could not parse generated variables from \"" + settings_file + "\": " + str(e),
                script_name,
            )
            return None

        if not isinstance(parsed_values, dict):
            printc.error(
                "Could not parse generated variables from \""
                + settings_file
                + "\": generated values are not a mapping.",
                script_name,
            )
            return None

        substitutions = {}
        requested_param_domains = []

        for variable_name in variable_names:
            raw_value = parsed_values.get(variable_name, "")
            value = str(raw_value).strip() if raw_value is not None else ""
            substitutions[variable_name] = value

            variable_cfg = variables.get(variable_name, {})
            unit = ""
            if isinstance(variable_cfg, dict):
                unit_value = variable_cfg.get("unit", "")
                if unit_value is not None:
                    unit = str(unit_value)

            display_value = value + unit if unit != "" else value
            requested_param_domains.append(variable_name + "/" + sanitize_value(display_value))

        variants.append(
            {
                "requested_param_domains": requested_param_domains,
                "substitutions": substitutions,
            }
        )

    if debug and len(variants) > 0:
        printc.note(
            "Generated "
            + str(len(variants))
            + " variants from \"generate_configurations_settings.variables\" in \""
            + settings_file
            + "\".",
            script_name,
        )

    return variants


def filter_variants(variants, requested_virtual_param_domains):
    """
    Keep only the variants matching every explicitly requested "domain/value"
    selector. A "domain/*" selector matches every value.
    """
    filtered = []
    for variant in variants:
        variant_domains = set(variant.get("requested_param_domains", []))
        keep = True
        for requested_virtual_domain in requested_virtual_param_domains:
            domain = re.sub("/.*", "", requested_virtual_domain)
            value = re.sub(".*/", "", requested_virtual_domain)
            if value == "*":
                continue
            if (domain + "/" + value) not in variant_domains:
                keep = False
                break
        if keep:
            filtered.append(variant)
    return filtered


def normalize_requests_for_wildcards(
    requests,
    base_path,
    get_basic,
    param_settings_filename=hard_settings.param_settings_filename,
    debug=False,
    script_name=script_name,
):
    """
    Normalize instance requests before wildcard expansion.

    If a request uses only virtual-domain wildcards (for example
    ``instance + var/* + other/*``), strip these selectors so the generic
    wildcard resolver does not expect physical parameter-domain directories.

    ``get_basic`` is ``ArchitectureHandler.get_basic`` (passed in to avoid a
    circular import).
    """
    normalized_requests = []
    for request in requests:
        (
            instance,
            param_dir,
            _config,
            _display_name,
            _param_dir_work,
            _config_dir_work,
            requested_param_domains,
        ) = get_basic(request)

        if len(requested_param_domains) == 0:
            normalized_requests.append(request)
            continue

        settings = load_instance_settings(base_path, param_dir, param_settings_filename)
        if settings is None:
            normalized_requests.append(request)
            continue

        virtual_domain_names = get_virtual_domain_names(settings)
        if len(virtual_domain_names) == 0:
            normalized_requests.append(request)
            continue

        dropped_virtual_wildcards = False
        kept_param_domains = []
        for requested_param_domain in requested_param_domains:
            domain = re.sub("/.*", "", requested_param_domain)
            value = re.sub(".*/", "", requested_param_domain)
            if domain in virtual_domain_names and value == "*":
                dropped_virtual_wildcards = True
                continue
            kept_param_domains.append(requested_param_domain)

        if dropped_virtual_wildcards:
            normalized_request = instance
            if len(kept_param_domains) > 0:
                normalized_request = instance + "+" + "+".join(kept_param_domains)
            if debug:
                printc.note(
                    "Using generated variables for wildcard selector(s) in request \"" + request + "\".",
                    script_name,
                )
            normalized_requests.append(normalized_request)
        else:
            normalized_requests.append(request)

    return normalized_requests
