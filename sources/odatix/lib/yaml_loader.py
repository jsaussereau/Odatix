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
Kept here for the code that imports it from Odatix: the module itself now lives
in the job handler (odatix.lib.parallel_job_handler._vendor.yaml_loader), which carries
its own copy so as to depend on nothing of Odatix. Both names are one module.
"""

import sys

from odatix.lib.parallel_job_handler._vendor import yaml_loader as _module

sys.modules[__name__] = _module
