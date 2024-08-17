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
import tty
import termios
import select
import socket
import logging 
import argparse

import scripts.lib.printc as printc
from scripts.explorer.explorer_app import ResultExplorer

script_name = os.path.basename(__file__)

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

def close_server():
  restore_mode(old_settings)
  print('\r')
  os._exit(0)

def set_raw_mode():
  fd = sys.stdin.fileno()
  global old_settings
  old_settings = termios.tcgetattr(fd)
  tty.setraw(fd)
  return old_settings

def restore_mode(old_settings):
  fd = sys.stdin.fileno()
  termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def start_result_explorer(input, network=False):

  global ip_address
  global port

  # Default ip address: local
  host_address = '127.0.0.1'
  ip_address = host_address
  port = 8052

  from waitress import serve

  logging.getLogger('waitress').setLevel(logging.ERROR)

  if network:
    host_address = '0.0.0.0'
    ip_address = socket.gethostbyname(socket.gethostname())

  printc.say("Server running on " + printc.colors.BLUE + "http://" + ip_address + ":" + str(port) + '/' + printc.colors.ENDC, end="", script_name=script_name)
  if network:
    print(" (network-accessible)")
  else:
    print(" (localhost only)")
  printc.say("press 'q' to quit", script_name=script_name)

  # Open the web page
  process = Thread(target=open_browser).start()

  result_explorer = ResultExplorer(
    result_path=input
  )

  # Start the server
  serve_thread = Thread(target=serve, args=(result_explorer.app.server,), kwargs={'host': host_address, 'port': port})
  serve_thread.start()

  old_settings = set_raw_mode()
  try:
    while True:
      # Check if a key is pressed
      if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        key = sys.stdin.read(1).lower()
        if key == 'q':
          close_server()
  finally:
    restore_mode(old_settings)

######################################
# Main
######################################

def main(args):
  network = args.network
  input = args.input
  start_result_explorer(input, network)


if __name__ == "__main__":
  args = parse_arguments()
  main(args)
