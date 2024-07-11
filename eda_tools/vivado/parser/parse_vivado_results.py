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

import sys
sys.path.append('scripts/lib/')
import re_helper as rh
import re

format_mode = 'fpga'

frequency_search_log = 'log/frequency_search.log'
utilization_report = 'report/utilization.rep'
area_report = 'report/area.rep'
cell_count_report = 'report/cell_count.rep'
power_report = 'report/power.rep'

fmax_pattern = re.compile("(.*)Highest frequency with timing constraints being met: ([0-9_]+) MHz")
slice_lut_pattern = re.compile("\\| Slice LUTs (\\s*)\\|(\\s*)([0-9]+)(.*)")
slice_reg_pattern = re.compile("\\| Slice Registers (\\s*)\\|(\\s*)([0-9]+)(.*)")
bram_pattern = re.compile("\\| Block RAM Tile (\\s*)\\|(\\s*)([0-9]+)(.*)")
dsp_pattern = re.compile("\\| DSPs (\\s*)\\|(\\s*)([0-9]+)(.*)")
dynamic_pow_pattern = re.compile("\\| Dynamic \\(W\\) (\\s*)\\|(\\s*)([0-9.]+)(.*)")
static_pow_pattern = re.compile("\\| Device Static \\(W\\) (\\s*)\\|(\\s*)([0-9.]+)(.*)")

######################################
# Parsing functions
######################################

def get_fmax(path):
  file = path+'/'+frequency_search_log
  return rh.get_re_group_from_file(file, fmax_pattern, group_id=2)

def get_slice_lut(path):
  file = path+'/'+utilization_report
  return rh.get_re_group_from_file(file, slice_lut_pattern, group_id=3)

def get_slice_reg(path):
  file = path+'/'+utilization_report
  return rh.get_re_group_from_file(file, slice_reg_pattern, group_id=3)

def get_bram(path):
  file = path+'/'+utilization_report
  return rh.get_re_group_from_file(file, bram_pattern, group_id=3)

def get_dsp(path):
  file = path+'/'+utilization_report
  return rh.get_re_group_from_file(file, dsp_pattern, group_id=3)

def get_dynamic_pow(path):
  file = path+'/'+power_report
  return rh.get_re_group_from_file(file, dynamic_pow_pattern, group_id=3)

def get_static_pow(path):
  file = path+'/'+power_report
  return rh.get_re_group_from_file(file, static_pow_pattern, group_id=3)
