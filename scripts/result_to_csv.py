'''
Copyright(C) 2022 by Jonathan Saussereau. All rights reserved.

All source codes and documentation contain proprietary confidential
information and are distributed under license. It may be used, copied
and/or disclosed only pursuant to the terms of a valid license agreement
with Jonathan Saussereau. This copyright must be retained at all times.

result_to_csv.py

use example: python3 result_to_csv.py
''' 

import os
import re
import csv
import argparse  # Import the argparse library

from os.path import exists


######################################
# Settings
######################################

result_path = "./result"
output_file = "result.csv"
fieldnames_fpga = ['', 'architecture             ', 'variant', '', 'Fmax', '', 'LUTs', 'Regs', 'Tot Ut', '', 'DynP', 'StaP', 'TotP']
fieldnames_asic = ['', 'architecture             ', 'variant', '', 'Fmax', '', 'Cells', 'Area', 'Tot Area', '', 'DynP', 'StaP', 'TotP']

frequency_search_log = 'log/frequency_search.log'
utilization_report = 'report/utilization.rep'
area_report = 'report/area.rep'
cell_count_report = 'report/cell_count.rep'
power_report = 'report/power.rep'

status_done = 'Done: 100%'

fmax_pattern = re.compile("(.*)Highest frequency with timing constraints being met: ([0-9_]+) MHz")
slice_lut_pattern = re.compile("\| Slice LUTs (\s*)\|(\s*)([0-9]+)(.*)")
slice_reg_pattern = re.compile("\| Slice Registers (\s*)\|(\s*)([0-9]+)(.*)")
area_pattern = re.compile("Total cell area:(\s*)([0-9,.]+)(.*)")
cell_count_pattern = re.compile("Cell count:(\s*)([0-9,.]+)(.*)")
dynamic_pow_pattern = re.compile("\| Dynamic \(W\) (\s*)\|(\s*)([0-9.]+)(.*)")
static_pow_pattern = re.compile("\| Device Static \(W\) (\s*)\|(\s*)([0-9.]+)(.*)")


######################################
# Misc functions
######################################

class bcolors:
  WARNING = '\033[93m'
  ENDC = '\033[0m'

def corrupted_directory(target, variant):
  print(f"{bcolors.WARNING}warning{bcolors.ENDC}: {target}/{variant} => synthesis has not finished or directory has been corrupted")

def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process FPGA or ASIC results')
    parser.add_argument('-o', '--output', default='result.csv',
                        help='Output file name (default: result.csv)')
    parser.add_argument('-m', '--mode', choices=['fpga', 'asic'], default='fpga',
                        help='Select the mode (fpga or asic, default: fpga)')
    args = parser.parse_args()
    return args


######################################
# Parsing functions
######################################

def get_re_group_from_file(file, pattern, group_id):
  if exists(file):
    for i, line in enumerate(open(file)):
      for match in re.finditer(pattern, line):
        parts = pattern.search(match.group())
        if group_id <= len(parts.groups()):
          return parts.group(group_id)
  return ' /   '

def get_fmax(path):
  file = path+'/'+frequency_search_log
  return get_re_group_from_file(file, fmax_pattern, 2)

def get_slice_lut(path):
  file = path+'/'+utilization_report
  return get_re_group_from_file(file, slice_lut_pattern, 3)

def get_slice_reg(path):
  file = path+'/'+utilization_report
  return get_re_group_from_file(file, slice_reg_pattern, 3)

def get_area(path):
  file = path+'/'+area_report
  return get_re_group_from_file(file, area_pattern, 2)

def get_cell_count(path):
  file = path+'/'+cell_count_report
  return get_re_group_from_file(file, cell_count_pattern, 2)

def get_dynamic_pow(path):
  file = path+'/'+power_report
  return get_re_group_from_file(file, dynamic_pow_pattern, 3)

def get_static_pow(path):
  file = path+'/'+power_report
  return get_re_group_from_file(file, static_pow_pattern, 3)


######################################
# Main
######################################

if __name__ == "__main__":

  args = parse_arguments()  # Parse command line arguments

  if args.mode == 'fpga':
    fieldnames = fieldnames_fpga
  elif args.mode == 'asic':
    fieldnames = fieldnames_asic
  else:
    raise ValueError("Invalid mode selected. Please choose 'fpga' or 'asic'.")

  output_file = args.output  # Use the specified output file

  with open(output_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, delimiter='\t')

    for target in sorted(next(os.walk(result_path))[1]):
      writer.writerow([])
      writer.writerow([target])
      for arch in sorted(next(os.walk(result_path+'/'+target))[1]):
        writer.writerow(fieldnames)
        for variant in sorted(next(os.walk(result_path+'/'+target+'/'+arch))[1]):
          cur_path=result_path+'/'+target+'/'+arch+'/'+variant

          # check if synthesis is complete
          if not exists(cur_path+'/log/status.log'):
            corrupted_directory(target, arch+'/'+variant)
          else:
            f = open(cur_path+'/log/status.log', "r")
            if not status_done in f.read():
              corrupted_directory(target, arch+'/'+variant)

          # get values
          fmax = get_fmax(cur_path)        
          if args.mode == 'fpga':
            slice_lut = get_slice_lut(cur_path)
            slice_reg = get_slice_reg(cur_path)
            dynamic_pow = get_dynamic_pow(cur_path)
            static_pow = get_static_pow(cur_path)
            try:
              total_ut = int(slice_lut) + int(slice_reg)
            except:
              total_ut = ' /  '
            try:
              total_pow = '%.3f'%(float(static_pow) + float(dynamic_pow))
            except:
              total_pow = ' /  '
          elif args.mode == 'asic':
            area = get_area(cur_path)
            cell_count = get_cell_count(cur_path)
          
          # write the line
          if args.mode == 'fpga':
            writer.writerow(['', arch, variant, '', fmax+'  ', '', slice_lut+' ', slice_reg+'  ', total_ut, '', dynamic_pow+' ', static_pow, total_pow])
          elif args.mode == 'asic':
            writer.writerow(['', arch, variant, '', fmax+'  ', '', cell_count, '            ', '' + area, '', '', '', ''])
        writer.writerow([])
