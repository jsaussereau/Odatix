#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

class bcolors:
  BLINK = '\033[5m'
  WARNING = '\033[93m'
  FAIL = '\033[91m'
  OKBLUE = '\033[94m'
  OKCYAN = '\033[96m'
  ENDC = '\033[0m'
  BOLD = '\033[1m'

print(bcolors.BOLD, end="")
print("********************************************************************")
print("*                             Asterism                             *")
print("********************************************************************")
print(bcolors.ENDC)
