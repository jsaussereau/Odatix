import os
import re

bad_value = ' /   '

def get_re_group_from_file(file, pattern, group_id):
  if os.path.exists(file):
    for i, line in enumerate(open(file)):
      for match in re.finditer(pattern, line):
        parts = pattern.search(match.group())
        if group_id <= len(parts.groups()):
          return parts.group(group_id)
  return bad_value
