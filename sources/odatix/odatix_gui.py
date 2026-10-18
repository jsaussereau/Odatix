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
import socket
import logging 
import argparse
from waitress import serve

try:
    from urllib.parse import urlencode
except ImportError:  # Python 2 fallback, kept for safety
    from urllib import urlencode

# Add parent dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sources_dir = os.path.realpath(os.path.join(current_dir, os.pardir))
if sources_dir not in sys.path:
    sys.path.append(sources_dir)

import odatix.lib.printc as printc
import odatix.lib.term_mode as term_mode
from odatix.lib.settings import OdatixSettings
from odatix.gui.app import OdatixApp
from odatix.lib.utils import get_local_ip, find_free_port, open_browser_when_ready
from odatix.components.cli_options import HelpFormatter, deprecated_option

sys.stdout = term_mode.RawModeOutputWrapper(sys.stdout)

######################################
# Settings
######################################

script_name = "odatix-gui"

start_port = 8052

######################################
# Parse Arguments
######################################

job_types = ["fmax_synthesis", "custom_freq_synthesis", "pnr", "analyze", "workflow", "simulation"]
synthesis_job_types = ["fmax_synthesis", "custom_freq_synthesis", "pnr"]

class PageOption:
    """A page-specific command line option, forwarded to the page as an url parameter."""

    def __init__(self, flags, url_key, help, dest=None, type=str, choices=None, former=()):
        self.flags = flags if isinstance(flags, (list, tuple)) else [flags]
        self.url_key = url_key
        self.help = help
        self.dest = dest if dest is not None else "page_" + url_key
        self.type = type
        self.choices = choices
        # Former spellings, still read for one version (see deprecated_option).
        self.former = tuple(former)

    def add_to(self, parser):
        parser.add_argument(*self.flags, dest=self.dest, default=None, type=self.type, choices=self.choices, help=self.help)
        for flag in self.former:
            deprecated_option(parser, flag, "/".join(self.flags), dest=self.dest, type=self.type)

    def value(self, args):
        return getattr(args, self.dest, None)

# Pages that can be opened directly from the command line.
# Each entry maps a command name to the path of the corresponding Dash page,
# and to the options this page accepts (forwarded as url parameters).
gui_pages = {
    "home": ("/", []),
    "monitor": ("/monitor", [
        PageOption(['-S', '--session'], "session", "session to show: its name, ID, PID or the start of one (default: the latest one of the workspace)"),
        # "--port" is the port of the GUI, before or after the page name: the
        # port of a session given by hand has a name of its own.
        PageOption(['--daemon-host'], "host", "host of a session reached by hand, rather than by its name", former=['--host']),
        PageOption(['--daemon-port'], "port", "port of a session reached by hand, rather than by its name", type=int),
    ]),
    "jobs": ("/choose_job_type", []),
    "run_jobs": ("/run_jobs", [
        PageOption(['--type'], "type", "job type to run", choices=job_types),
        PageOption(['--tool'], "tool", "eda tool to use"),
        PageOption(['--flow'], "flow", "flow to run"),
        PageOption(['--until'], "until", "last step to run"),
    ]),
    "eda_tool": ("/choose_eda_tool", [
        PageOption(['--type'], "type", "job type to choose a tool for", choices=synthesis_job_types),
    ]),
    "select_targets": ("/select_targets", [
        PageOption(['--tool'], "tool", "tool to select targets for"),
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
        PageOption(['--tool'], "tool", "tool to edit"),
    ]),
    "sim_editor": ("/sim_editor", [
        PageOption(['--sim'], "sim", "simulation to edit"),
    ]),
    "metric_editor": ("/metric_editor", [
        PageOption(['--tool'], "tool", "edit the exported metrics of this tool"),
        PageOption(['--workflow'], "workflow", "edit the exported metrics of this workflow"),
        PageOption(['--simulation'], "simulation", "edit the exported metrics of this simulation"),
    ]),
    "derived_metrics": ("/derived_metrics", []),
    "clean": ("/clean", []),
    "workspace": ("/workspace", []),
}

default_page = "home"

#: What each page is for, as "odatix-gui -h" lists it.
page_descriptions = {
    "home": "home page",
    "monitor": "follow the jobs of a session",
    "jobs": "choose what to run",
    "run_jobs": "check and start a run",
    "eda_tool": "choose the tool of a synthesis",
    "select_targets": "choose the targets of a tool",
    "architectures": "list the architectures",
    "arch_editor": "edit an architecture",
    "config_editor": "generate configurations",
    "workflows": "list the workflows",
    "workflow_editor": "edit a workflow",
    "tools": "list the tools",
    "tool_editor": "edit a tool",
    "sim_editor": "edit a simulation",
    "metric_editor": "edit the metrics a tool, workflow or simulation exports",
    "derived_metrics": "edit the derived metrics",
    "clean": "remove generated files",
    "workspace": "edit the workspace settings",
}


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

def add_arguments(parser, suppress_defaults=False, skip_flags=()):
    def default(value):
        return argparse.SUPPRESS if suppress_defaults else value

    def add(flags, **kwargs):
        if any(flag in skip_flags for flag in flags):
            return
        parser.add_argument(*flags, **kwargs)

    add(['-i', '--input'], type=str, default=default('results'), help='result directory (default: results)')
    add(['-n', '--network'], action='store_true', default=default(False), help='serve on the network, not only on this machine')
    add(['-p', '--port'], type=int, default=default(None), help='port to serve on, which must be free (default: ' + str(start_port) + ', or the next free one)')
    add(['-N', '--normal-term-mode'], dest='normal_term_mode', action='store_true', default=default(False), help='leave the terminal mode alone (then "q" needs Enter)')
    add(['--safe-mode'], dest='safe_mode', action='store_true', default=default(False), help='keep running on an internal error')
    add(['-B', '--nobrowser'], action='store_true', default=default(False), help='do not open a browser')
    add(['-T', '--theme'], default=default(None), metavar='THEME', help=theme_help())
    add(["-c", "--config"], default=default(OdatixSettings.DEFAULT_SETTINGS_FILE), help="workspace settings file (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")")
    if '--normal_term_mode' not in skip_flags:
        deprecated_option(parser, '--normal_term_mode', '-N/--normal-term-mode', action='store_true', dest='normal_term_mode')
        deprecated_option(parser, '--safe_mode', '--safe-mode', action='store_true', dest='safe_mode')

def add_page_parsers(parser):
    subparsers = parser.add_subparsers(dest='page', metavar='<page>', help='page to open (default: ' + default_page + ')')
    for page, (path, options) in gui_pages.items():
        description = page_descriptions.get(page, 'open the ' + path + ' page')
        page_parser = subparsers.add_parser(page, help=description, description=description[:1].upper() + description[1:],
                                            formatter_class=HelpFormatter)
        # Global options are also accepted after the page name, unless the page defines
        # an option with the same flag. In that case, the global option is only
        # available before the page name.
        page_flags = [flag for option in options for flag in option.flags]
        add_arguments(page_parser, suppress_defaults=True, skip_flags=page_flags)
        for option in options:
            option.add_to(page_parser)

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='odatix-gui', description='Odatix graphical interface: configure, run and explore', formatter_class=HelpFormatter,
    )
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

def open_browser(host_address):
    """Open the landing page, once the server is up and accepting connections."""
    open_browser_when_ready("http://" + ip_address + ':' + str(port) + landing_page, host_address, port, script_name=script_name)

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
        # Asked for explicitly: that port or nothing, never another one in silence
        port = find_free_port(host_address, preferred_port, strict=True, script_name=script_name)
    else:
        port = find_free_port(host_address, start_port, script_name=script_name)
        if port != start_port:
            printc.note("port " + str(start_port) + " is in use, using port " + str(port), script_name=script_name)

    printc.say("Server running on " + printc.colors.BLUE + "http://" + ip_address + ":" + str(port) + landing_page + printc.colors.ENDC, end="", script_name=script_name)
    if network:
        print(" (network-accessible)")
    else:
        print(" (localhost only)")

    printc.say(term_mode.quit_hint(normal_term_mode), script_name=script_name)
    # Under nohup or a service manager stdout is a file, fully buffered: the
    # address (and the port actually taken) must reach it now, not at exit.
    sys.stdout.flush()

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

def main(args=None):
    # No color codes nor carriage returns in a file or a pipe (nohup, a
    # service manager): its log is read as text.
    printc.plain_unless_terminal()
    printc.set_command(script_name)
    # The sessions started from here are named after the GUI, not after the
    # terminal it was started from.
    import odatix.lib.parallel_job_handler.daemon_control as daemon_control
    daemon_control.set_session_origin("gui")

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
