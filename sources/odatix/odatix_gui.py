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
import socket
import logging 
import argparse
from waitress import serve

try:
    from urllib.parse import urlencode
except ImportError:  # Python 2 fallback, kept for safety
    from urllib import urlencode

if sys.platform == "win32":
    import msvcrt
else:
    import select

# Add parent dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sources_dir = os.path.realpath(os.path.join(current_dir, os.pardir))
if sources_dir not in sys.path:
    sys.path.append(sources_dir)

import odatix.lib.printc as printc
import odatix.lib.term_mode as term_mode
from odatix.lib.settings import OdatixSettings
from odatix.gui.app import OdatixApp
from odatix.lib.utils import get_local_ip, find_free_port

sys.stdout = term_mode.RawModeOutputWrapper(sys.stdout)

######################################
# Settings
######################################

script_name = os.path.basename(__file__)

start_port = 8052

######################################
# Parse Arguments
######################################

job_types = ["fmax_synthesis", "custom_freq_synthesis", "pnr", "analyze", "workflow", "simulation"]
synthesis_job_types = ["fmax_synthesis", "custom_freq_synthesis", "pnr"]

class PageOption:
    """A page-specific command line option, forwarded to the page as an url parameter."""

    def __init__(self, flags, url_key, help, dest=None, type=str, choices=None):
        self.flags = flags if isinstance(flags, (list, tuple)) else [flags]
        self.url_key = url_key
        self.help = help
        self.dest = dest if dest is not None else "page_" + url_key
        self.type = type
        self.choices = choices

    def add_to(self, parser):
        parser.add_argument(*self.flags, dest=self.dest, default=None, type=self.type, choices=self.choices, help=self.help)

    def value(self, args):
        return getattr(args, self.dest, None)

# Pages that can be opened directly from the command line.
# Each entry maps a command name to the path of the corresponding Dash page,
# and to the options this page accepts (forwarded as url parameters).
gui_pages = {
    "home": ("/", []),
    "monitor": ("/monitor", [
        PageOption(['-S', '--session'], "session", "daemon session name or selector"),
        PageOption(['--host'], "host", "daemon API host (default: current workspace daemon host)"),
        PageOption(['--port'], "port", "daemon API port (default: current workspace daemon port)", type=int),
    ]),
    "jobs": ("/choose_job_type", []),
    "run_jobs": ("/run_jobs", [
        PageOption(['--type'], "type", "job type to run", choices=job_types),
        PageOption(['--tool'], "tool", "eda tool to use"),
        PageOption(['--flow'], "flow", "flow to run"),
        PageOption(['--until'], "until", "last step to run"),
    ]),
    "eda_tool": ("/choose_eda_tool", [
        PageOption(['--type'], "type", "job type to choose an eda tool for", choices=synthesis_job_types),
    ]),
    "select_targets": ("/select_targets", [
        PageOption(['--tool'], "tool", "eda tool to select targets for"),
    ]),
    "architectures": ("/architectures", []),
    "arch_editor": ("/arch_editor", [
        PageOption(['--arch'], "arch", "architecture to edit"),
    ]),
    "config_editor": ("/config_editor", []),
    "workflows": ("/workflows", []),
    "workflow_editor": ("/workflow_editor", [
        PageOption(['--workflow'], "workflow", "workflow to edit"),
    ]),
    "tools": ("/tools", []),
    "tool_editor": ("/tool_editor", [
        PageOption(['--tool'], "tool", "eda tool to edit"),
    ]),
    "sim_editor": ("/sim_editor", [
        PageOption(['--sim'], "sim", "simulation to edit"),
    ]),
    "metric_editor": ("/metric_editor", [
        PageOption(['--tool'], "tool", "edit the exported metrics of this eda tool"),
        PageOption(['--workflow'], "workflow", "edit the exported metrics of this workflow"),
        PageOption(['--simulation'], "simulation", "edit the exported metrics of this simulation"),
    ]),
    "derived_metrics": ("/derived_metrics", []),
    "clean": ("/clean", []),
    "workspace": ("/workspace", []),
}

default_page = "home"

def add_arguments(parser, suppress_defaults=False, skip_flags=()):
    def default(value):
        return argparse.SUPPRESS if suppress_defaults else value

    def add(flags, **kwargs):
        if any(flag in skip_flags for flag in flags):
            return
        parser.add_argument(*flags, **kwargs)

    add(['-i', '--input'], type=str, default=default('results'), help='Directory of the result YAML files')
    add(['-n', '--network'], action='store_true', default=default(False), help='Run the server on the network')
    add(['-p', '--port'], type=int, default=default(start_port), help='Port to run the server on')
    add(['-N', '--normal_term_mode'], action='store_true', default=default(False), help='Do not change terminal mode')
    add(['--safe_mode'], action='store_true', default=default(False), help='Do not exit on internal error')
    add(['-B', '--nobrowser'], action='store_true', default=default(False), help='Do not open browser')
    add(['-T', '--theme'], default=default(None), help='Use a specific theme')
    add(["-c", "--config"], default=default(OdatixSettings.DEFAULT_SETTINGS_FILE), help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")")

def add_page_parsers(parser):
    subparsers = parser.add_subparsers(dest='page', help='page to open (default: ' + default_page + ')')
    for page, (path, options) in gui_pages.items():
        page_parser = subparsers.add_parser(page, help='open the ' + path + ' page')
        # Global options are also accepted after the page name, unless the page defines
        # an option with the same flag (for instance '--port' on the monitor page refers
        # to the daemon port, as in `odatix monitor`). In that case, the global option
        # is only available before the page name.
        page_flags = [flag for option in options for flag in option.flags]
        add_arguments(page_parser, suppress_defaults=True, skip_flags=page_flags)
        for option in options:
            option.add_to(page_parser)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Odatix - Start Graphical User Interface')
    add_arguments(parser)
    add_page_parsers(parser)
    # Try enabling autocompletion if argcomplete is installed
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass  # No error if argcomplete is missing
    return parser.parse_args()

def get_landing_page(args):
    """Build the url path (with query string) of the page to open, from parsed arguments."""
    page = getattr(args, 'page', None) or default_page
    path, options = gui_pages.get(page, gui_pages[default_page])

    query = {}
    for option in options:
        value = option.value(args)
        if value is not None:
            query[option.url_key] = value

    if query:
        path = path + '?' + urlencode(query)
    return path

######################################
# Misc functions
######################################

def open_browser():
    webbrowser.open("http://" + ip_address + ':' + str(port) + landing_page, new=0, autoraise=True)

def close_server(old_settings):
    if old_settings is not None:
        term_mode.restore_mode(old_settings)
    os._exit(0)

def start_odatix_app(network=False, preferred_port=None, normal_term_mode=False, safe_mode=False, do_not_open_browser=False, config_file=OdatixSettings.DEFAULT_SETTINGS_FILE, theme=None, page="/"):

    global ip_address
    global port
    global landing_page

    landing_page = page if page.startswith("/") else "/" + page

    # Default ip address: local
    host_address = '127.0.0.1'
    ip_address = host_address

    logging.getLogger('waitress').setLevel(logging.ERROR)

    if network:
        host_address = '0.0.0.0'
        ip_address = get_local_ip()

    if preferred_port is not None:
        port = find_free_port(host_address, preferred_port)
    else:
        port = find_free_port(host_address, start_port)

    printc.say("Server running on " + printc.colors.BLUE + "http://" + ip_address + ":" + str(port) + landing_page + printc.colors.ENDC, end="", script_name=script_name)
    if network:
        print(" (network-accessible)")
    else:
        print(" (localhost only)")

    if normal_term_mode:
        printc.say("press 'q', then enter to quit", script_name=script_name)
    else:
        printc.say("press 'q' to quit", script_name=script_name)

    # Open the web page
    if not do_not_open_browser:
        process = Thread(target=open_browser).start()

    if normal_term_mode:
        old_settings = None
    else:
        old_settings = term_mode.set_raw_mode()

    odatix_app = OdatixApp(
        old_settings=old_settings,
        safe_mode=safe_mode,
        config_file=config_file,
        theme=theme,
    )

    # Start the server
    # More worker threads than the waitress default (4): monitor callbacks issue
    # blocking HTTP requests to the daemon, and too few threads let one slow call
    # stall every other callback (and thus the whole UI).
    serve_thread = Thread(
        target=serve,
        args=(odatix_app.app.server,),
        kwargs={'host': host_address, 'port': port, 'threads': 16},
    )
    serve_thread.start()
    
    try:
        while True:
            # Check if a key is pressed
            if sys.platform == "win32":
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8").lower()
                    if key == 'q':
                        close_server(old_settings)
            else:
                if sys.stdin in select.select([sys.stdin], [], [], 0.5)[0]:
                    key = sys.stdin.read(1).lower()
                    if key == 'q':
                        close_server(old_settings)
    finally:
        if old_settings is not None:
            term_mode.restore_mode(old_settings)

######################################
# Main
######################################

def main(args=None):
    if args is None:
        args = parse_arguments()

    network = args.network
    input = args.input
    normal_term_mode = args.normal_term_mode
    safe_mode = args.safe_mode
    do_not_open_browser = args.nobrowser
    config_file = args.config
    port = args.port

    start_odatix_app(network, port, normal_term_mode, safe_mode, do_not_open_browser, config_file, args.theme, get_landing_page(args))

if __name__ == "__main__":
    main()
