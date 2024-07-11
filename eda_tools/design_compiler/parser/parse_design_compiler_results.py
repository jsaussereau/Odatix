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

format_mode = 'asic'

frequency_search_log = 'log/frequency_search.log'
area_report = 'report/area.rep'
cell_count_report = 'report/utilization.rep'
power_report = 'report/power.rep'

fmax_pattern = re.compile("(.*)Highest frequency with timing constraints being met: ([0-9_]+) MHz")
comb_area_pattern = re.compile("Combinational area:(\\s*)([0-9,.]+)(.*)")
noncomb_area_pattern = re.compile("Noncombinational area:(\\s*)([0-9,.]+)(.*)")
buf_inv_area_pattern = re.compile("Buf/Inv area:(\\s*)([0-9,.]+)(.*)")
macro_area_pattern = re.compile("Macro/Black Box area:(\\s*)([0-9,.]+)(.*)")
net_area_pattern = re.compile("Net Interconnect area:(\\s*)([0-9,.]+)(.*)")
cell_area_pattern = re.compile("Total cell area:(\\s*)([0-9,.]+)(.*)")
total_area_pattern = re.compile("Total area:(\\s*)([0-9,.]+)(.*)")
cell_count_pattern = re.compile("Cell count:(\\s*)([0-9,.]+)(.*)")
dynamic_pow_pattern = re.compile("\\| Dynamic \\(W\\) (\\s*)\\|(\\s*)([0-9.]+)(.*)")
static_pow_pattern = re.compile("\\| Device Static \\(W\\) (\\s*)\\|(\\s*)([0-9.]+)(.*)")

######################################
# Parsing functions
######################################

def get_fmax(path):
  file = path+'/'+frequency_search_log
  return rh.get_re_group_from_file(file, fmax_pattern, 2)

def get_cell_area(path):
  file = path+'/'+area_report
  return rh.get_re_group_from_file(file, cell_area_pattern, 2)

def get_total_area(path):
  file = path+'/'+area_report
  return rh.get_re_group_from_file(file, total_area_pattern, 2)

def get_comb_area(path):
  file = path+'/'+area_report
  return rh.get_re_group_from_file(file, comb_area_pattern, 2)

def get_noncomb_area(path):
  file = path+'/'+area_report
  return rh.get_re_group_from_file(file, noncomb_area_pattern, 2)

def get_buf_inv_area(path):
  file = path+'/'+area_report
  return rh.get_re_group_from_file(file, buf_inv_area_pattern, 2)

def get_macro_area(path):
  file = path+'/'+area_report
  return rh.get_re_group_from_file(file, macro_area_pattern, 2)

def get_net_area(path):
  file = path+'/'+area_report
  return rh.get_re_group_from_file(file, net_area_pattern, 2)

def get_cell_count(path):
  file = path+'/'+cell_count_report
  return rh.get_re_group_from_file(file, cell_count_pattern, 2)

def get_dynamic_pow(path):
  file = path+'/'+power_report
  return rh.get_re_group_from_file(file, dynamic_pow_pattern, 3)

def get_static_pow(path):
  file = path+'/'+power_report
  return rh.get_re_group_from_file(file, static_pow_pattern, 3)
