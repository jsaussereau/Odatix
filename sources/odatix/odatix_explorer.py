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
import sys
import webbrowser
from threading import Thread
import select
import socket
import logging 
import argparse
from waitress import serve

import odatix.lib.printc as printc
import odatix.lib.term_mode as term_mode
from odatix.explorer.explorer_app import ResultExplorer

######################################
# Settings
######################################

script_name = os.path.basename(__file__)

start_port = 8052
max_find_port_attempts = 50

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument('-i', '--input', type=str, default='results', help='Directory of the result YAML files')
  parser.add_argument('-n', '--network', action='store_true', help='Run the server on the network')

def parse_arguments():
  parser = argparse.ArgumentParser(description='Odatix - Start Result Explorer')
  add_arguments(parser)
  return parser.parse_args()

######################################
# Misc functions
######################################

def open_browser():
  webbrowser.open("http://" + ip_address + ':' + str(port), new=0, autoraise=True)

def close_server(old_settings):
  term_mode.restore_mode(old_settings)
  os._exit(0)

def find_free_port(host, start_port):
  """Find a free port by incrementing from the start_port."""
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  port = start_port
  attempts = 0
  while True:
    if attempts >= max_find_port_attempts:
      printc.error(f"Could not find any available port in range [{start_port}:{port}]", script_name)
      sys.exit(-1)
    try:
      sock.bind((host, port))
      sock.close()
      return port
    except OSError:
      port += 1
      attempts += 1

def start_result_explorer(input, network=False):

  global ip_address
  global port

  # Default ip address: local
  host_address = '127.0.0.1'
  ip_address = host_address

  logging.getLogger('waitress').setLevel(logging.ERROR)

  if network:
    host_address = '0.0.0.0'
    ip_address = socket.gethostbyname(socket.gethostname())

  port = find_free_port(host_address, start_port)

  printc.say("Server running on " + printc.colors.BLUE + "http://" + ip_address + ":" + str(port) + '/' + printc.colors.ENDC, end="", script_name=script_name)
  if network:
    print(" (network-accessible)")
  else:
    print(" (localhost only)")
  printc.say("press 'q' to quit", script_name=script_name)

  # Open the web page
  process = Thread(target=open_browser).start()

  old_settings = term_mode.set_raw_mode()

  result_explorer = ResultExplorer(
    result_path=input,
    old_settings=old_settings
  )

  # Start the server
  serve_thread = Thread(target=serve, args=(result_explorer.app.server,), kwargs={'host': host_address, 'port': port})
  serve_thread.start()
  
  try:
    while True:
      # Check if a key is pressed
      if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        key = sys.stdin.read(1).lower()
        if key == 'q':
          close_server(old_settings)
  finally:
    term_mode.restore_mode(old_settings)

######################################
# Main
######################################

def main(args=None):
  if args is None:
    args = parse_arguments()

  network = args.network
  input = args.input
  start_result_explorer(input, network)

if __name__ == "__main__":
  main()
