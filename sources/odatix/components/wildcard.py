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
import re
import itertools

from odatix.lib.architecture_handler import ArchitectureHandler
import odatix.lib.printc as printc
from odatix.lib.settings import OdatixSettings

script_name = os.path.basename(__file__)

# Handle wildcard
def configuration_wildcard(full_architectures, arch_path=OdatixSettings.DEFAULT_ARCH_PATH, target=""):
    architectures = []
    joker_archs = []
    for arch in full_architectures:
        arch, arch_param_dir, arch_config, _, _, _, requested_param_domains = ArchitectureHandler.get_basic(arch, target, False)
        if arch.endswith("/*"):
            # get param dir (arch name before '/*')
            arch_param_dir = re.sub(r'/\*', '', arch)
            arch_param = arch_path + '/' + arch_param_dir  
            # check if parameter dir exists
            if os.path.isdir(arch_param):
                files = [f[:-4] for f in os.listdir(arch_param) if os.path.isfile(os.path.join(arch_param, f)) and f.endswith(".txt")]
                joker_archs = [os.path.join(arch_param_dir, file) for file in sorted(files)]
                if len(joker_archs) == 0:
                    printc.note(f"No configuration found in \"{arch_param}\"", script_name)
            else:
                printc.error(f"The architecture directory \"{arch_param}\" does not exist", script_name)
        else:
            joker_archs = [arch]
            arch_param = arch_param_dir
            
        # Parameter domain wildcard
        joker_param_domain = {}
        if len(requested_param_domains) > 0:
            for requested_param_domain in requested_param_domains:
                if requested_param_domain.endswith("/*"):
                    param_domain = re.sub(r'/\*', '', requested_param_domain)
                    # get parameter domain dir
                    arch_param = arch_path + '/' + arch_param_dir
                    param_domain_dir = os.path.join(arch_param, param_domain)  
                    # check if parameter domain dir exists
                    if os.path.isdir(param_domain_dir):
                        files = [f[:-4] for f in os.listdir(param_domain_dir) if os.path.isfile(os.path.join(param_domain_dir, f)) and f.endswith(".txt")]
                        joker_param_domain[param_domain] = sorted(files)
                    else:
                        printc.error(f"The parameter domain directory \"{param_domain_dir}\" does not exist", script_name)
                        existing_domains = [d for d in os.listdir(arch_param) if os.path.isdir(os.path.join(arch_param, d))]
                        if len(existing_domains) == 0:
                            printc.tip(f"No parameter domains found in \"{arch_param}\"", script_name)
                        else:
                            printc.tip(f"Available parameter domains found in \"{arch_param}\": {', '.join(existing_domains)}", script_name)
                        continue
                else:
                    param_domain = re.sub(r'/.*', '', requested_param_domain)
                    value = re.sub(r'.*/', '', requested_param_domain)
                    joker_param_domain[param_domain] = [value]  
            if len(joker_param_domain) == 0:
                return None  
            # Generate combinations
            param_keys = list(joker_param_domain.keys())
            param_values = [joker_param_domain[key] if isinstance(joker_param_domain[key], list) else [joker_param_domain[key]] for key in param_keys]  
            for arch_instance in joker_archs:
                for param_combination in itertools.product(*param_values):
                    param_string = "+".join(f"{param_keys[i]}/{param_combination[i]}" for i in range(len(param_keys)))
                    architectures.append(f"{arch_instance}+{param_string}")
        else:
            architectures = architectures + joker_archs  
    # Remove duplicates
    architectures = list(dict.fromkeys(architectures))
    return architectures
