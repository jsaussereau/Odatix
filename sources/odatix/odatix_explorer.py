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
from threading import Thread
import logging
import argparse
from waitress import serve

# Add parent dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sources_dir = os.path.realpath(os.path.join(current_dir, os.pardir))
if sources_dir not in sys.path:
    sys.path.append(sources_dir)

import odatix.lib.printc as printc
import odatix.lib.term_mode as term_mode
from odatix.explorer.standalone import ExplorerStandaloneApp
from odatix.lib.utils import get_local_ip, find_free_port, open_browser_when_ready
from odatix.components.cli_options import HelpFormatter, deprecated_option
from odatix.lib.settings import OdatixSettings

sys.stdout = term_mode.RawModeOutputWrapper(sys.stdout)

######################################
# Settings
######################################

script_name = "odatix-explorer"

start_port = 8052

######################################
# Parse Arguments
######################################

def theme_help():
    """The help of -T/--theme, with the themes there are."""
    try:
        import odatix.gui.themes as themes

        names = themes.theme_list()
    except Exception:
        names = []
    text = "theme to start with (default: the one chosen last in the browser)"
    if names:
        text += ": " + ", ".join(names)
    return text

def add_arguments(parser):
    parser.add_argument('-i', '--input', type=str, default=None, help='result directory (default: "result_path" of the workspace settings file, else ' + OdatixSettings.DEFAULT_RESULT_PATH + ')')
    parser.add_argument('-c', '--config', default=OdatixSettings.DEFAULT_SETTINGS_FILE, help='workspace settings file, which gives the result directory (default: ' + OdatixSettings.DEFAULT_SETTINGS_FILE + ')')
    parser.add_argument('-n', '--network', action='store_true', help='serve on the network, not only on this machine')
    parser.add_argument('-p', '--port', type=int, default=None, help='port to serve on, which must be free (default: ' + str(start_port) + ', or the next free one)')
    parser.add_argument('-N', '--normal-term-mode', dest='normal_term_mode', action='store_true', help='leave the terminal mode alone (then "q" needs Enter)')
    parser.add_argument('--safe-mode', dest='safe_mode', action='store_true', help='keep running on an internal error')
    parser.add_argument('-B', '--nobrowser', action='store_true', help='do not open a browser')
    parser.add_argument('-T', '--theme', default=None, metavar='THEME', help=theme_help())
    parser.add_argument('--read-only', dest='read_only', action='store_true', help='do not let visitors save views on the server (recommended with --network)')
    deprecated_option(parser, '--normal_term_mode', '-N/--normal-term-mode', action='store_true', dest='normal_term_mode')
    deprecated_option(parser, '--safe_mode', '--safe-mode', action='store_true', dest='safe_mode')
    deprecated_option(parser, '--read_only', '--read-only', action='store_true', dest='read_only')

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='odatix-explorer', description='Odatix result explorer: the charts of the results, on their own',
        formatter_class=HelpFormatter,
    )
    add_arguments(parser)
    # Try enabling autocompletion if argcomplete is installed
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass  # No error if argcomplete is missing
    return parser.parse_args()

######################################
# Misc functions
######################################

def open_browser(host_address):
    """Open the explorer page, once the server is up and accepting connections."""
    open_browser_when_ready("http://" + ip_address + ':' + str(port) + "/explorer", host_address, port, script_name=script_name)

def close_server(old_settings):
    if old_settings is not None:
        term_mode.restore_mode(old_settings)
    os._exit(0)

def start_result_explorer(input, network=False, preferred_port=None, normal_term_mode=False, safe_mode=False, do_not_open_browser=False, theme=None, read_only=False):

    global ip_address
    global port

    # Default ip address: local
    host_address = '127.0.0.1'
    ip_address = host_address

    logging.getLogger('waitress').setLevel(logging.ERROR)

    if network:
        host_address = '0.0.0.0'
        ip_address = get_local_ip()

    if preferred_port is not None:
        # Asked for explicitly: that port or nothing, never another one in silence
        port = find_free_port(host_address, preferred_port, strict=True, script_name=script_name)
    else:
        port = find_free_port(host_address, start_port, script_name=script_name)
        if port != start_port:
            printc.note("port " + str(start_port) + " is in use, using port " + str(port), script_name=script_name)

    if not os.path.isdir(input):
        printc.warning('Result directory "' + input + '" does not exist (yet). Results will appear as soon as they are written.', script_name=script_name)

    printc.say("Server running on " + printc.colors.BLUE + "http://" + ip_address + ":" + str(port) + '/' + printc.colors.ENDC, end="", script_name=script_name)
    if network:
        print(" (network-accessible)")
    else:
        print(" (localhost only)")
    if read_only:
        printc.say("read-only: saving views is disabled", script_name=script_name)

    printc.say(term_mode.quit_hint(normal_term_mode), script_name=script_name)
    # Under nohup or a service manager stdout is a file, fully buffered: the
    # address (and the port actually taken) must reach it now, not at exit.
    sys.stdout.flush()

    if normal_term_mode:
        old_settings = None
    else:
        old_settings = term_mode.set_raw_mode()

    result_explorer = ExplorerStandaloneApp(
        result_path=input,
        old_settings=old_settings,
        safe_mode=safe_mode,
        theme=theme,
        read_only=read_only,
    )

    # Start the server
    serve_thread = Thread(target=serve, args=(result_explorer.app.server,), kwargs={'host': host_address, 'port': port})
    serve_thread.start()

    # Open the web page, only once the server is actually listening
    if not do_not_open_browser:
        Thread(target=open_browser, args=(host_address,), daemon=True).start()

    try:
        term_mode.wait_for_quit_key(lambda: close_server(old_settings), serve_thread)
    finally:
        if old_settings is not None:
            term_mode.restore_mode(old_settings)

######################################
# Main
######################################

def result_directory(input=None, config=OdatixSettings.DEFAULT_SETTINGS_FILE):
    """
    The result directory to explore: "-i" when given, else the "result_path"
    of the workspace settings file (relative to that file), else "results".
    """
    if input:
        return input
    if config and os.path.isfile(config):
        settings = OdatixSettings(config, silent=True)
        result_path = getattr(settings, "result_path", None) or OdatixSettings.DEFAULT_RESULT_PATH
        if not os.path.isabs(result_path):
            result_path = os.path.join(os.path.dirname(config), result_path) if os.path.dirname(config) else result_path
        return result_path
    if config and config != OdatixSettings.DEFAULT_SETTINGS_FILE:
        printc.warning('Workspace settings file "' + config + '" does not exist: exploring "' + OdatixSettings.DEFAULT_RESULT_PATH + '"', script_name=script_name)
    return OdatixSettings.DEFAULT_RESULT_PATH

######################################

def main(args=None):
    # No color codes nor carriage returns in a file or a pipe (nohup, a
    # service manager): its log is read as text.
    printc.plain_unless_terminal()
    printc.set_command(script_name)

    if args is None:
        args = parse_arguments()

    network = args.network
    input = result_directory(args.input, getattr(args, "config", OdatixSettings.DEFAULT_SETTINGS_FILE))
    normal_term_mode = args.normal_term_mode
    safe_mode = args.safe_mode
    do_not_open_browser = args.nobrowser
    port = args.port

    start_result_explorer(input, network, port, normal_term_mode, safe_mode, do_not_open_browser, args.theme, getattr(args, "read_only", False))

if __name__ == "__main__":
    main()
