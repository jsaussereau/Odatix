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
import csv
import yaml
import argparse

import sys
sys.path.append('eda_tools/vivado/parser')
sys.path.append('eda_tools/design_compiler/parser')

from os.path import exists

######################################
# Settings
######################################

fieldnames_fpga = ['', 'architecture', 'variant', '', 'Fmax', '', 'LUTs', 'Regs', 'Tot Ut', '', 'DynP', 'StaP', 'TotP']
fieldnames_asic = ['', 'architecture', 'variant', '', 'Fmax', '', 'Cells', 'Area', 'Tot Area', '', 'DynP', 'StaP', 'TotP']

benchmark_file = 'benchmark/benchmark.yml'

status_done = 'Done: 100%'

bad_value = ' /   '
format_mode = 'fpga'

######################################
# Misc functions
######################################

class bcolors:
  WARNING = '\033[93m'
  OKCYAN = '\033[96m'
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
                      help='Input path (default: work/<tool>)')
  parser.add_argument('-o', '--output', default='results',
                      help='Output path (default: results')
  #parser.add_argument('-m', '--mode', choices=['fpga', 'asic'], default='fpga',
  #                    help='Select the mode (fpga or asic, default: fpga)')
  parser.add_argument('-t', '--tool', choices=['vivado', 'design_compiler'], default='vivado',
                      help='eda tool in use (default: vivado)')
  parser.add_argument('-f', '--format', choices=['csv', 'yml', 'all'], default='yml',
                      help='Output format: csv, yml, or all (default: yml)')
  parser.add_argument('-b', '--benchmark', action='store_true',
                      help='Use benchmark values in yaml file')
  return parser.parse_args()

def import_result_parser(tool):
  if tool == 'vivado':
    import parse_vivado_results as selected_parser
  elif tool == 'design_compiler':
    import parse_design_compiler_results as selected_parser
  else:
    print("Unsupported parser")
    exit
  return selected_parser

######################################
# Parsing functions
######################################

def get_dmips_per_mhz(architecture, variant, benchmark_data):
  try:
    dmips_value = benchmark_data[architecture][variant]['dmips_per_MHz']
    return dmips_value
  except KeyError as e:
    #print(f"Could not find key in benchmark file: {e}")
    return None
  except Exception as e:
    print(f"Could not read benchmark file '{benchmark_file}': {e}")
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

def write_to_yaml(args, output_file, parser, benchmark_data):
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
        fmax = parser.get_fmax(cur_path)
        if format_mode == 'fpga':
          slice_lut = parser.get_slice_lut(cur_path)
          slice_reg = parser.get_slice_reg(cur_path)
          bram = parser.get_bram(cur_path)
          dsp = parser.get_dsp(cur_path)
          dynamic_pow = parser.get_dynamic_pow(cur_path)
          static_pow = parser.get_static_pow(cur_path)
          total_ut = safe_cast(slice_lut, int, 0) + safe_cast(slice_reg, int, 0)
          total_pow = safe_cast(static_pow, float, 0.0) + safe_cast(dynamic_pow, float, 0.0)

          yaml_data[target][arch][variant] = {
            'Fmax_MHz': cast_to_int(fmax),
            'LUT_count': cast_to_int(slice_lut),
            'Reg_count': cast_to_int(slice_reg),
            'BRAM_count': cast_to_int(bram),
            'DSP_count': cast_to_int(dsp),
            'Total_LUT_reg': cast_to_int(total_ut),
            'Dynamic_Power': cast_to_float(dynamic_pow),
            'Static_Power': cast_to_float(static_pow),
            'Total_Power': cast_to_float("%.3f" % total_pow)
          }

        elif format_mode == 'asic':
          area = parser.get_area(cur_path)
          cell_count = parser.get_cell_count(cur_path)

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

def write_to_csv(args, output_file, parser, fieldnames):
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
          fmax = parser.get_fmax(cur_path)        
          if format_mode == 'fpga':
            slice_lut = parser.get_slice_lut(cur_path)
            slice_reg = parser.get_slice_reg(cur_path)
            dynamic_pow = parser.get_dynamic_pow(cur_path)
            static_pow = parser.get_static_pow(cur_path)
            try:
              total_ut = int(slice_lut) + int(slice_reg)
            except:
              total_ut = ' /  '
            try:
              total_pow = '%.3f'%(float(static_pow) + float(dynamic_pow))
            except:
              total_pow = ' /  '
          elif format_mode == 'asic':
            area = parser.get_area(cur_path)
            cell_count = parser.get_cell_count(cur_path)
          
          # write the line
          if format_mode == 'fpga':
            writer.writerow(['', arch, variant, '', fmax+'  ', '', slice_lut+' ', slice_reg+'  ', total_ut, '', dynamic_pow+' ', static_pow, total_pow])
          elif format_mode == 'asic':
            writer.writerow(['', arch, variant, '', fmax+'  ', '', cell_count, '            ', '' + area, '', '', '', ''])
        writer.writerow([])

######################################
# Main
######################################

if __name__ == "__main__":
  print(f"{bcolors.OKCYAN}exporting results...{bcolors.ENDC}")

  args = parse_arguments()

  if args.tool == 'vivado':
    format_mode = 'fpga'
  elif args.tool == 'design_compiler':
    format_mode = 'asic'
  else:
    raise ValueError(f"Unsupported tool ({args.tool}) selected. Please choose 'vivado' or 'design_compiler'.")

  parser = import_result_parser(args.tool)

  if format_mode == 'fpga':
    fieldnames = fieldnames_fpga
  elif format_mode == 'asic':
    fieldnames = fieldnames_asic
  else:
    raise ValueError(f"Invalid format mode ({format_mode}) selected. Please choose 'fpga' or 'asic'.")

  if not args.input.endswith(('/vivado', '/design_compiler')):
    args.input = f"{args.input}/{args.tool}"

  if not os.path.isdir(args.input):
    print(f"Input directory '{args.input}' does not exist")
    sys.exit()

  benchmark_data = None
  if args.benchmark:
    if not exists(benchmark_file):
      args.benchmark = False
      print(f"{bcolors.ERROR}error{bcolors.ENDC}: cannot find benchmark file '{benchmark_file}', benchmark export disabled.")
    with open(benchmark_file, 'r') as file:
      benchmark_data = yaml.safe_load(file)

  if args.format in ['csv', 'all']:
    csv_file = f"{args.output}/results_{args.tool}.csv"
    write_to_csv(args, csv_file, parser, fieldnames)

  if args.format in ['yml', 'all']:
    yaml_file = f"{args.output}/results_{args.tool}.yml"
    write_to_yaml(args, yaml_file, parser, benchmark_data)
