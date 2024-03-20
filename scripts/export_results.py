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
import yaml
import argparse

from os.path import exists

######################################
# Settings
######################################

fieldnames_fpga = ['', 'architecture', 'variant', '', 'Fmax', '', 'LUTs', 'Regs', 'Tot Ut', '', 'DynP', 'StaP', 'TotP']
fieldnames_asic = ['', 'architecture', 'variant', '', 'Fmax', '', 'Cells', 'Area', 'Tot Area', '', 'DynP', 'StaP', 'TotP']

frequency_search_log = 'log/frequency_search.log'
utilization_report = 'report/utilization.rep'
area_report = 'report/area.rep'
cell_count_report = 'report/cell_count.rep'
power_report = 'report/power.rep'
benchmark_file = 'benchmark/benchmark.yml'

status_done = 'Done: 100%'

fmax_pattern = re.compile("(.*)Highest frequency with timing constraints being met: ([0-9_]+) MHz")
slice_lut_pattern = re.compile("\\| Slice LUTs (\\s*)\\|(\\s*)([0-9]+)(.*)")
slice_reg_pattern = re.compile("\\| Slice Registers (\\s*)\\|(\\s*)([0-9]+)(.*)")
area_pattern = re.compile("Total cell area:(\\s*)([0-9,.]+)(.*)")
cell_count_pattern = re.compile("Cell count:(\\s*)([0-9,.]+)(.*)")
dynamic_pow_pattern = re.compile("\\| Dynamic \\(W\\) (\\s*)\\|(\\s*)([0-9.]+)(.*)")
static_pow_pattern = re.compile("\\| Device Static \\(W\\) (\\s*)\\|(\\s*)([0-9.]+)(.*)")

bad_value = ' /   '

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
  parser.add_argument('-i', '--input', default='work',
                      help='Input path (default: work/[fpga/asic])')
  parser.add_argument('-o', '--output', default='results',
                      help='Output path (default: results')
  parser.add_argument('-m', '--mode', choices=['fpga', 'asic'], default='fpga',
                      help='Select the mode (fpga or asic, default: fpga)')
  parser.add_argument('-f', '--format', choices=['csv', 'yml', 'all'], default='yml',
                      help='Output format: csv, yml, or all (default: yml)')
  parser.add_argument('-b', '--benchmark', action='store_true',
                      help='Use benchmark values in yaml file')
  return parser.parse_args()

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
  return bad_value

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

def get_dmips_per_mhz(architecture, variant, benchmark_data):
  try:
    dmips_value = benchmark_data[architecture][variant]['dmips_per_MHz']
    return dmips_value
  except KeyError as e:
    #print(f"Clé non trouvée : {e}")
    return None
  except Exception as e:
    print(f"Erreur lors de la lecture du fichier {benchmark_file} : {e}")
    return None

######################################
# Format functions
######################################

def cast_to_int(input):
  if input == bad_value:
    return '/'
  else:
    return safe_cast(input, int, 0)

def cast_to_float(input):
  if input == bad_value:
    return '/'
  else:
    return safe_cast(input, float, 0.0)

def write_to_yaml(args, output_file, benchmark_data):
  yaml_data = {}

  for target in sorted(next(os.walk(args.input))[1]):
    yaml_data[target] = {}
    for arch in sorted(next(os.walk(os.path.join(args.input, target)))[1]):
      yaml_data[target][arch] = {}
      for variant in sorted(next(os.walk(os.path.join(args.input, target, arch)))[1]):
        cur_path = os.path.join(args.input, target, arch, variant)

        # Vérification de la complétion de la synthèse
        if not exists(os.path.join(cur_path, 'log/status.log')):
          corrupted_directory(target, arch+'/'+variant)
          continue

        with open(os.path.join(cur_path, 'log/status.log'), "r") as f:
          if not status_done in f.read():
            corrupted_directory(target, arch+'/'+variant)
            continue

        # Extraction des valeurs
        fmax = get_fmax(cur_path)
        if args.mode == 'fpga':
          slice_lut = get_slice_lut(cur_path)
          slice_reg = get_slice_reg(cur_path)
          dynamic_pow = get_dynamic_pow(cur_path)
          static_pow = get_static_pow(cur_path)
          total_ut = safe_cast(slice_lut, int, 0) + safe_cast(slice_reg, int, 0)
          total_pow = safe_cast(static_pow, float, 0.0) + safe_cast(dynamic_pow, float, 0.0)

          yaml_data[target][arch][variant] = {
            'Fmax_MHz': cast_to_int(fmax),
            'LUT_count': cast_to_int(slice_lut),
            'Reg_count': cast_to_int(slice_reg),
            'Total_LUT_reg': cast_to_int(total_ut),
            'Dynamic_Power': cast_to_float(dynamic_pow),
            'Static_Power': cast_to_float(static_pow),
            'Total_Power': cast_to_float("%.3f" % total_pow)
          }

        elif args.mode == 'asic':
          area = get_area(cur_path)
          cell_count = get_cell_count(cur_path)

          yaml_data[target][arch][variant] = {
            'fmax': cast_to_int(fmax),
            'cell_count': cast_to_int(cell_count),
            'area': cast_to_float(area)
          }

        # benchmark
        if args.benchmark:
          dmips_per_mhz = get_dmips_per_mhz(arch, variant, benchmark_data)
          if dmips_per_mhz != None:
            dmips = safe_cast(fmax, float, 0.0) * safe_cast(dmips_per_mhz, float, 0.0)

            yaml_data[target][arch][variant].update({
              'DMIPS_per_MHz': cast_to_float("%.3f" % dmips_per_mhz),
              'DMIPS': cast_to_float("%.2f" % dmips)
          })

  with open(output_file, 'w') as file:
    yaml.dump(yaml_data, file, default_flow_style=False, sort_keys=False)

def write_to_csv(args, output_file, fieldnames):
  with open(output_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, delimiter='\t')

    for target in sorted(next(os.walk(args.input))[1]):
      writer.writerow([])
      writer.writerow([target])
      for arch in sorted(next(os.walk(args.input+'/'+target))[1]):
        writer.writerow(fieldnames)
        for variant in sorted(next(os.walk(args.input+'/'+target+'/'+arch))[1]):
          cur_path=args.input+'/'+target+'/'+arch+'/'+variant

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

######################################
# Main
######################################

if __name__ == "__main__":
  args = parse_arguments()

  if args.mode == 'fpga':
    fieldnames = fieldnames_fpga
  elif args.mode == 'asic':
    fieldnames = fieldnames_asic
  else:
    raise ValueError("Invalid mode selected. Please choose 'fpga' or 'asic'.")

  if not args.input.endswith(('/fpga', '/asic')):
    args.input = f"{args.input}/{args.mode}"

  benchmark_data = None
  if args.benchmark:
    if not exists(benchmark_file):
      args.benchmark = False
      print(f"{bcolors.ERROR}error{bcolors.ENDC}: cannot find benchmark file '{benchmark_file}', benchmark export disabled.")
    with open(benchmark_file, 'r') as file:
      benchmark_data = yaml.safe_load(file)

  if args.format in ['csv', 'all']:
    csv_file = f"{args.output}/results_{args.mode}.csv"
    write_to_csv(args, csv_file, fieldnames)

  if args.format in ['yml', 'all']:
    yaml_file = f"{args.output}/results_{args.mode}.yml"
    write_to_yaml(args, yaml_file, benchmark_data)
