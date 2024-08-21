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

BAD_VALUE = ' /   '

def get_re_group_from_file(file, pattern, group_id, bad_value=BAD_VALUE):
  if os.path.exists(file):
    for i, line in enumerate(open(file)):
      for match in re.finditer(pattern, line):
        parts = pattern.search(match.group())
        if group_id <= len(parts.groups()):
          return parts.group(group_id)
  return bad_value
