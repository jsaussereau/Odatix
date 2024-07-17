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

import re
import os
import sys
import csv
import yaml
import argparse

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.append(lib_path)

from settings import AsterismSettings
import re_helper as rh
from utils import *
import printc

######################################
# Settings
######################################

DEFAULT_FORMAT = "yml"

# get eda_tools folder
if getattr(sys, 'frozen', False):
  base_path = os.path.dirname(sys.executable)
else:
  base_path = current_dir
eda_tools_path = os.path.realpath(os.path.join(base_path, "..", "eda_tools"))

parser_filename = os.path.join("parser", "parser_settings.yml")

fieldnames_fpga = ['', 'architecture', 'variant', '', 'Fmax', '', 'LUTs', 'Regs', 'Tot Ut', '', 'DynP', 'StaP', 'TotP']
fieldnames_asic = ['', 'architecture', 'variant', '', 'Fmax', '', 'Cells', 'Area', 'Tot Area', '', 'DynP', 'StaP', 'TotP']

status_done = 'Done: 100%'

bad_value = ' /   '
format_mode = 'fpga'

script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument('-t', '--tool', default='vivado', help='eda tool in use (default: vivado)')
  parser.add_argument('-f', '--format', choices=['csv', 'yml', 'all'], default=DEFAULT_FORMAT, help='Output format: csv, yml, or all (default: ' + DEFAULT_FORMAT  + ')')
  parser.add_argument('-u', '--use_benchmark', action='store_true', help='Use benchmark values in yaml file')
  parser.add_argument('-B', '--benchmark_file', help='Benchmark file')
  parser.add_argument('-w', '--work', help='work directory')
  parser.add_argument('-r', '--respath', help='Result path')
  parser.add_argument('-c', '--config', default=AsterismSettings.DEFAULT_SETTINGS_FILE, help='global settings file for asterism (default: ' + AsterismSettings.DEFAULT_SETTINGS_FILE + ')')

def parse_arguments():
  parser = argparse.ArgumentParser(description='Process FPGA or ASIC results')
  add_arguments(parser)
  return parser.parse_args()

######################################
# Misc functions
######################################

def corrupted_directory(target, variant):
  printc.warning(target + "/" + variant + " => synthesis has not finished or directory has been corrupted", script_name)

def safe_cast(val, to_type, default=None):
  try:
    return to_type(val)
  except (ValueError, TypeError):
    return default

######################################
# Parsing functions
######################################

class RegEx:
  def __init__(self, file, pattern, group_id):
    self.file = str(file)
    self.pattern = re.compile(str(pattern))
    self.group_id = int(group_id)

  def __str__(self):
    out_str ="  file=" + self.file + "\n"
    out_str +="  pattern=" + str(self.pattern) + "\n"
    out_str +="  group_id=" + str(self.group_id) + "\n"
    return out_str

class ResultParser:
  def __init__(self, yaml_file):
    self.asic = None
    self.fpga = None
    self.common = None
    self.valid = False

    if not os.path.isfile(yaml_file):
      printc.error("There is no parser settings file \"" + yaml_file + "\".", script_name=script_name)
      return
    with open(yaml_file, "r") as f:
      try:
        yaml_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
      except Exception as e:
        printc.error("Invalid yaml file \"" +  yaml_file + "\" for parser settings.", script_name=script_name)
        printc.cyan("error details: ", script_name=script_name, end="")
        print(str(e))
        return

      try:
        self.format_mode = read_from_list("format_mode", yaml_data, yaml_file, script_name=script_name)
      except Exception as e:
        return

      self.format_mode = self.format_mode.lower()
      if self.format_mode == "fpga":
        self.fpga = FpgaParser(yaml_data, yaml_file)
        if not self.fpga.valid:
          return
      elif self.format_mode == "asic":
        self.asic = AsicParser(yaml_data, yaml_file)
        if not self.asic.valid:
          return
      else:
        printc.error("Unsupported format_mode declared in \"" + yaml_file + "\": \"" + self.format_mode + "\". Please choose \"fpga\" or \"asic\"", script_name=script_name)
        return
      self.common = CommonParser(yaml_data, yaml_file)
      if not self.common.valid:
        return
    self.valid = True

  @staticmethod
  def get_regex(yaml_data, yaml_filename, parent=""):
    file = read_from_list("file", yaml_data, yaml_filename, parent=parent, script_name=script_name)
    pattern = read_from_list("pattern", yaml_data, yaml_filename, parent=parent, script_name=script_name)
    group_id = read_from_list("group_id", yaml_data, yaml_filename, parent=parent, script_name=script_name)
    try:
      regex = RegEx(file, pattern, group_id)
    except Exception as e:
      printc.error("Parser settings values for \"" +  parent + "\" are not valid.", script_name=script_name)
      printc.cyan("error details: ", script_name=script_name, end="")
      print(str(e))
      raise
    return regex

class CommonParser:
  def __init__(self, yaml_data, yaml_filename):
    self.valid = False

    try:
      fmax_yaml = read_from_list("fmax", yaml_data, yaml_filename, script_name=script_name)
      dynamic_pow_yaml = read_from_list("dynamic_pow", yaml_data, yaml_filename, script_name=script_name)
      static_pow_yaml = read_from_list("static_pow", yaml_data, yaml_filename, script_name=script_name)
    except KeyNotInListError as e:
      return

    try:
      self.fmax_regex = ResultParser.get_regex(fmax_yaml, yaml_filename, "fmax")
      self.dynamic_pow_regex = ResultParser.get_regex(dynamic_pow_yaml, yaml_filename, "dynamic_pow")
      self.static_pow_regex = ResultParser.get_regex(static_pow_yaml, yaml_filename, "static_pow")
    except Exception as e:
      return

    self.valid = True

  def get_fmax(self, cur_path):
    file = os.path.join(cur_path, self.fmax_regex.file)
    result = rh.get_re_group_from_file(file, self.fmax_regex.pattern, self.fmax_regex.group_id)
    return result

  def get_dynamic_pow(self, cur_path):
    file = os.path.join(cur_path, self.dynamic_pow_regex.file)
    return rh.get_re_group_from_file(file, self.dynamic_pow_regex.pattern, self.dynamic_pow_regex.group_id)

  def get_static_pow(self, cur_path):
    file = os.path.join(cur_path, self.static_pow_regex.file)
    return rh.get_re_group_from_file(file, self.static_pow_regex.pattern, self.static_pow_regex.group_id)

class FpgaParser:
  def __init__(self, yaml_data, yaml_filename):
    self.valid = False

    try:
      slice_lut_yaml = read_from_list("slice_lut", yaml_data, yaml_filename, script_name=script_name)
      slice_reg_yaml = read_from_list("slice_reg", yaml_data, yaml_filename, script_name=script_name)
      bram_yaml = read_from_list("bram", yaml_data, yaml_filename, script_name=script_name)
      dsp_yaml = read_from_list("dsp", yaml_data, yaml_filename, script_name=script_name)
    except KeyNotInListError as e:
      return

    try:
      self.slice_lut_regex = ResultParser.get_regex(slice_lut_yaml, yaml_filename)
      self.slice_reg_regex = ResultParser.get_regex(slice_reg_yaml, yaml_filename)
      self.bram_regex = ResultParser.get_regex(bram_yaml, yaml_filename)
      self.dsp_regex = ResultParser.get_regex(dsp_yaml, yaml_filename)
    except Exception as e:
      return

    self.valid = True

  def get_slice_lut(self, cur_path):
    file = os.path.join(cur_path, self.slice_lut_regex.file)
    return rh.get_re_group_from_file(file, self.slice_lut_regex.pattern, self.slice_lut_regex.group_id)

  def get_slice_reg(self, cur_path):
    file = os.path.join(cur_path, self.slice_reg_regex.file)
    return rh.get_re_group_from_file(file, self.slice_reg_regex.pattern, self.slice_reg_regex.group_id)

  def get_bram(self, cur_path):
    file = os.path.join(cur_path, self.bram_regex.file)
    return rh.get_re_group_from_file(file, self.bram_regex.pattern, self.bram_regex.group_id)

  def get_dsp(self, cur_path):
    file = os.path.join(cur_path, self.dsp_regex.file)
    return rh.get_re_group_from_file(file, self.dsp_regex.pattern, self.dsp_regex.group_id)

class AsicParser:
  def __init__(self, yaml_data, yaml_filename):
    self.valid = False

    try:
      cell_area_yaml = read_from_list("cell_area", yaml_data, yaml_filename, script_name=script_name)
      total_area_yaml = read_from_list("total_area", yaml_data, yaml_filename, script_name=script_name)
      comb_area_yaml = read_from_list("comb_area", yaml_data, yaml_filename, script_name=script_name)
      noncomb_area_yaml = read_from_list("noncomb_area", yaml_data, yaml_filename, script_name=script_name)
      buf_inv_area_yaml = read_from_list("buf_inv_area", yaml_data, yaml_filename, script_name=script_name)
      macro_area_yaml = read_from_list("macro_area", yaml_data, yaml_filename, script_name=script_name)
      net_area_yaml = read_from_list("net_area", yaml_data, yaml_filename, script_name=script_name)
      cell_count_yaml = read_from_list("cell_count", yaml_data, yaml_filename, script_name=script_name)
      pass
    except KeyNotInListError as e:
      return

    try:
      self.cell_area_regex = ResultParser.get_regex(cell_area_yaml, yaml_filename)
      self.total_area_regex = ResultParser.get_regex(total_area_yaml, yaml_filename)
      self.comb_area_regex = ResultParser.get_regex(comb_area_yaml, yaml_filename)
      self.noncomb_area_regex = ResultParser.get_regex(noncomb_area_yaml, yaml_filename)
      self.buf_inv_area_regex = ResultParser.get_regex(buf_inv_area_yaml, yaml_filename)
      self.macro_area_regex = ResultParser.get_regex(macro_area_yaml, yaml_filename)
      self.net_area_regex = ResultParser.get_regex(net_area_yaml, yaml_filename)
      self.cell_count_regex = ResultParser.get_regex(cell_count_yaml, yaml_filename)
      pass
    except Exception as e:
      return

    self.valid = True

  def get_cell_area(self, cur_path):
    file = os.path.join(cur_path, self.cell_area_regex.file)
    return rh.get_re_group_from_file(file, self.cell_area_regex.pattern, self.cell_area_regex.group_id)

  def get_total_area(self, cur_path):
    file = os.path.join(cur_path, self.total_area_regex.file)
    return rh.get_re_group_from_file(file, self.total_area_regex.pattern, self.total_area_regex.group_id)

  def get_comb_area(self, cur_path):
    file = os.path.join(cur_path, self.comb_area_regex.file)
    return rh.get_re_group_from_file(file, self.comb_area_regex.pattern, self.comb_area_regex.group_id)

  def get_noncomb_area(self, cur_path):
    file = os.path.join(cur_path, self.noncomb_area_regex.file)
    return rh.get_re_group_from_file(file, self.noncomb_area_regex.pattern, self.noncomb_area_regex.group_id)

  def get_buf_inv_area(self, cur_path):
    file = os.path.join(cur_path, self.buf_inv_area_regex.file)
    return rh.get_re_group_from_file(file, self.buf_inv_area_regex.pattern, self.buf_inv_area_regex.group_id)

  def get_macro_area(self, cur_path):
    file = os.path.join(cur_path, self.macro_area_regex.file)
    return rh.get_re_group_from_file(file, self.macro_area_regex.pattern, self.macro_area_regex.group_id)

  def get_net_area(self, cur_path):
    file = os.path.join(cur_path, self.net_area_regex.file)
    return rh.get_re_group_from_file(file, self.net_area_regex.pattern, self.net_area_regex.group_id)

  def get_cell_count(self, cur_path):
    file = os.path.join(cur_path, self.cell_count_regex.file)
    return rh.get_re_group_from_file(file, self.cell_count_regex.pattern, self.cell_count_regex.group_id)

def get_dmips_per_mhz(architecture, variant, benchmark_data, benchmark_file):
  try:
    dmips_value = benchmark_data[architecture][variant]['dmips_per_MHz']
    return dmips_value
  except KeyError as e:
    #printc.error(f"could not find key in benchmark file: {e}", script_name)
    return None
  except Exception as e:
    printc.error("could not read benchmark file \"" + benchmark_file + " : " + str(e), script_name)
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

def write_to_yaml(input, output_file, format_mode, parser, use_benchmark, benchmark_file, benchmark_data):
  yaml_data = {}

  for target in sorted(next(os.walk(input))[1]):
    yaml_data[target] = {}
    for arch in sorted(next(os.walk(os.path.join(input, target)))[1]):
      yaml_data[target][arch] = {}
      for variant in sorted(next(os.walk(os.path.join(input, target, arch)))[1]):
        cur_path = os.path.join(input, target, arch, variant)

        # Vérification de la complétion de la synthèse
        if not os.path.isfile(os.path.join(cur_path, 'log/status.log')):
          corrupted_directory(target, arch+'/'+variant)
          continue

        with open(os.path.join(cur_path, 'log/status.log'), "r") as f:
          if not status_done in f.read():
            corrupted_directory(target, arch+'/'+variant)
            continue

        # Extraction des valeurs
        fmax = parser.common.get_fmax(cur_path)
        dynamic_pow = parser.common.get_dynamic_pow(cur_path)
        static_pow = parser.common.get_static_pow(cur_path)
        if format_mode == 'fpga':
          slice_lut = parser.fpga.get_slice_lut(cur_path)
          slice_reg = parser.fpga.get_slice_reg(cur_path)
          bram = parser.fpga.get_bram(cur_path)
          dsp = parser.fpga.get_dsp(cur_path)
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
          total_area = parser.asic.get_total_area(cur_path)
          cell_area = parser.asic.get_cell_area(cur_path)
          comb_area = parser.asic.get_comb_area(cur_path)
          noncomb_area = parser.asic.get_noncomb_area(cur_path)
          buf_inv_area = parser.asic.get_buf_inv_area(cur_path)
          macro_area = parser.asic.get_macro_area(cur_path)
          net_area = parser.asic.get_net_area(cur_path)
          cell_count = parser.asic.get_cell_count(cur_path)

          yaml_data[target][arch][variant] = {
            'Fmax_MHz': cast_to_int(fmax),
            'Cell_count': cast_to_int(cell_count),
            'Total_area_um2': cast_to_float(total_area),
            'Cell_area_um2': cast_to_float(cell_area),
            'Comb_area_um2': cast_to_float(comb_area),
            'Non_comb_area_um2': cast_to_float(noncomb_area),
            'Buf_inv_area_um2': cast_to_float(buf_inv_area),
            'Macro_area_um2': cast_to_float(macro_area),
            'Net_area_um2': cast_to_float(net_area)
          }

        # benchmark
        if use_benchmark:
          dmips_per_mhz = get_dmips_per_mhz(arch, variant, benchmark_data, benchmark_file)
          if dmips_per_mhz != None:
            dmips = safe_cast(fmax, float, 0.0) * safe_cast(dmips_per_mhz, float, 0.0)

            yaml_data[target][arch][variant].update({
              'DMIPS_per_MHz': cast_to_float("%.3f" % dmips_per_mhz),
              'DMIPS': cast_to_float("%.2f" % dmips)
          })

  with open(output_file, 'w') as file:
    yaml.dump(yaml_data, file, default_flow_style=False, sort_keys=False)
    printc.say("Results written to \"" + output_file + "\"", script_name=script_name)

def write_to_csv(input, output_file, format_mode, parser, fieldnames):
  with open(output_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, delimiter='\t')

    for target in sorted(next(os.walk(input))[1]):
      writer.writerow([])
      writer.writerow([target])
      for arch in sorted(next(os.walk(input+'/'+target))[1]):
        writer.writerow(fieldnames)
        for variant in sorted(next(os.walk(input+'/'+target+'/'+arch))[1]):
          cur_path=input+'/'+target+'/'+arch+'/'+variant

          # check if synthesis is complete
          if not os.path.isfile(cur_path+'/log/status.log'):
            corrupted_directory(target, arch+'/'+variant)
          else:
            f = open(cur_path+'/log/status.log', "r")
            if not status_done in f.read():
              corrupted_directory(target, arch+'/'+variant)

          # get values
          fmax = parser.common.get_fmax(cur_path)     
          dynamic_pow = parser.common.get_dynamic_pow(cur_path)
          static_pow = parser.common.get_static_pow(cur_path)   
          if format_mode == 'fpga':
            slice_lut = parser.fpga.get_slice_lut(cur_path)
            slice_reg = parser.fpga.get_slice_reg(cur_path)
            try:
              total_ut = int(slice_lut) + int(slice_reg)
            except:
              total_ut = ' /  '
            try:
              total_pow = '%.3f'%(float(static_pow) + float(dynamic_pow))
            except:
              total_pow = ' /  '
          elif format_mode == 'asic':
            area = parser.asic.get_cell_area(cur_path)
            cell_count = parser.asic.get_cell_count(cur_path)
          
          # write the line
          if format_mode == 'fpga':
            writer.writerow(['', arch, variant, '', fmax+'  ', '', slice_lut+' ', slice_reg+'  ', total_ut, '', dynamic_pow+' ', static_pow, total_pow])
          elif format_mode == 'asic':
            writer.writerow(['', arch, variant, '', fmax+'  ', '', cell_count, '            ', '' + area, '', '', '', ''])
        writer.writerow([])
  printc.say("Results written to \"" + output_file + "\"", script_name=script_name)


######################################
# Export Results
######################################

def export_results(input, output, tool, format, use_benchmark, benchmark_file):
  print(printc.colors.CYAN + "Export " +  tool + " results" + printc.colors.ENDC)

  parser_file = os.path.join(eda_tools_path, tool, parser_filename)

  parser = ResultParser(parser_file)

  if not parser.valid:
    printc.error("Invalid parser for " + tool + ".", script_name)
    sys.exit(1)

  try:
    format_mode = parser.format_mode
  except:
    printc.error("Invalid parser. Cannot find \"format_mode\" in parser for " + tool, script_name)
    sys.exit(1)

  if format_mode == 'fpga':
    fieldnames = fieldnames_fpga
  elif format_mode == 'asic':
    fieldnames = fieldnames_asic
  else:
    printc.error("Invalid format mode (" + format_mode + ") selected in parser file. Please choose 'fpga' or 'asic'", script_name)
    sys.exit(1)

  if not input.endswith(('/vivado', '/design_compiler')):
    input = input + "/" + tool

  if not os.path.isdir(input):
    printc.error("Input directory \"" + input + "\" does not exist", script_name)
    sys.exit(1)

  benchmark_data = None
  if use_benchmark:
    if not os.path.isfile(benchmark_file):
      use_benchmark = False
      printc.warning("Cannot find benchmark file \"" + benchmark_file + "\", benchmark export disabled", script_name)
    else:
      with open(benchmark_file, 'r') as file:
        benchmark_data = yaml.safe_load(file)

  if not os.path.isdir(output):
    os.makedirs(output)

  if format in ['csv', 'all']:
    csv_file = output + "/results_" + tool + ".csv"
    try:
      write_to_csv(input, csv_file, format_mode, parser, fieldnames)
    except Exception as e:
      printc.error("Could not write \"" + csv_file + "\"", script_name=script_name)
      printc.cyan("error details: ", script_name=script_name, end="")
      print(str(e))

  if format in ['yml', 'all']:
    yaml_file = output + "/results_" + tool + ".yml"
    try:
      write_to_yaml(input, yaml_file, format_mode, parser, use_benchmark, benchmark_file, benchmark_data)
    except Exception as e:
      printc.error("Could not write \"" + yaml_file + "\"", script_name=script_name)
      printc.cyan("error details: ", script_name=script_name, end="")
      print(str(e))

  print()

######################################
# Main
######################################
  
def main(args, settings=None):

  # Get settings
  if settings is None:
    settings = AsterismSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  if args.use_benchmark is not None:
    use_benchmark  = args.use_benchmark
  else:
    use_benchmark = settings.use_benchmark

  if args.benchmark_file is not None:
    benchmark_file  = args.benchmark_file
  else:
    benchmark_file = settings.benchmark_file

  if args.work is not None:
    input = args.work
  else:
    input = settings.work_path

  if args.respath is not None:
    output = args.respath
  else:
    output = settings.result_path

  export_results(
    input=input,
    output=output,
    tool=args.tool,
    format=args.format,
    use_benchmark=use_benchmark, 
    benchmark_file=benchmark_file
  )

if __name__ == "__main__":
  args = parse_arguments()
  main(args)
