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

"""
This module contains utility functions for file operations, error handling,
and user interactions within Odatix.

Functions:
    - copytree: Custom function to copy directories with filtering options.
    - chunk_list: Splits a list into smaller chunks of a given size.
    - read_from_list: Reads and validates values from a dictionary.
    - move_cursor_up: Moves the cursor up in the terminal.
    - progress_bar: Displays a progress bar in the terminal.
    - ask_to_continue: Prompts the user to continue or exit.
    - ask_yes_no: Prompts the user for a yes/no input.
    - create_dir: Creates a directory, removing it first if it exists.
    - internal_error: Logs internal errors and prints an error message.
    - safe_df_append: Safely appends data to a pandas DataFrame.
    - can_open_path_in_explorer: Tells if a file explorer is available on this system.
    - open_path_in_explorer: Opens a file or directory in the system explorer.
"""

import os
import re
import sys
import glob
import time
import stat
import shutil
import socket
import fnmatch
import platform
import traceback
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import odatix.lib.printc as printc
import odatix.components.motd

YAML_BOOL = ('true', 'false', 'yes', 'no', 'on', 'off')

# Keyword used (in CLI arguments, YAML settings and the GUI) to request that the
# number of parallel jobs be computed automatically from the available CPUs.
AUTO_NB_JOBS_KEYWORD = "auto"

def is_auto_nb_jobs(value):
    """Return True if `value` requests the automatic number of parallel jobs."""
    return isinstance(value, str) and value.strip().lower() == AUTO_NB_JOBS_KEYWORD

def resolve_nb_jobs(nb_jobs):
    """
    Resolve a raw nb_jobs value (int, numeric string, or the "auto" keyword) into
    a concrete positive integer.

    When `nb_jobs` is "auto", the number of parallel jobs is computed as the
    number of available CPUs minus one (at least 1), leaving a core free for the
    rest of the system.
    """
    if is_auto_nb_jobs(nb_jobs):
        try:
            cpu_count = os.cpu_count() or 1
        except (NotImplementedError, ValueError):
            cpu_count = 1
        return max(1, cpu_count - 1)
    return int(nb_jobs)

# copytree copies the first files one by one while timing them; if a file takes
# longer than COPYTREE_SLOW_FILE_SECONDS on average (network file system), the
# rest is copied by a pool of threads, which only slows down a local copy.
COPYTREE_PROBE_FILES = 16
COPYTREE_SLOW_FILE_SECONDS = 0.002
COPYTREE_MAX_WORKERS = 16

def _copy_file(src, dst):
    """
    Copy a file with its permission bits and timestamps, like shutil.copy2 but
    without the extended attributes, whose copy costs several extra round trips
    per file on a network file system.
    """
    shutil.copyfile(src, dst)
    src_stat = os.stat(src)
    os.chmod(dst, stat.S_IMODE(src_stat.st_mode))
    os.utime(dst, ns=(src_stat.st_atime_ns, src_stat.st_mtime_ns))

def _copy_files(copies, copy_one):
    """Copy the (source, destination) pairs, in parallel when files are slow to copy."""
    probe = copies[:COPYTREE_PROBE_FILES]
    start = time.time()
    for src_file, dst_file in probe:
        copy_one(src_file, dst_file)
    remaining = copies[len(probe):]
    if not remaining:
        return
    if time.time() - start <= COPYTREE_SLOW_FILE_SECONDS * len(probe):
        for src_file, dst_file in remaining:
            copy_one(src_file, dst_file)
        return
    with ThreadPoolExecutor(max_workers=COPYTREE_MAX_WORKERS) as executor:
        futures = [executor.submit(copy_one, src_file, dst_file) for src_file, dst_file in remaining]
        for future in futures:
            future.result()

def _compile_copy_patterns(patterns, src):
    """
    Normalize the whitelist/blacklist patterns of copytree into
    (regex, literal_prefix, is_glob) tuples, relative to `src` with "/" separators.
    """
    compiled = []
    for pattern in patterns or []:
        pattern = str(pattern)
        if os.path.isabs(pattern):
            pattern = os.path.relpath(os.path.realpath(pattern), src)
        pattern = os.path.normpath(pattern).replace(os.sep, "/")
        if pattern in (".", ""):
            pattern = "*"
        glob_index = min([i for i in (pattern.find(c) for c in "*?[") if i >= 0] or [len(pattern)])
        compiled.append((
            re.compile(fnmatch.translate(os.path.normcase(pattern))),
            pattern[:glob_index],
            glob_index < len(pattern),
        ))
    return compiled

def copytree(src, dst, dirs_exist_ok=False, whitelist=None, blacklist=None, **kwargs):
    """
    Custom copytree to copy directories with support for dirs_exist_ok, whitelist, and blacklist.

    Patterns are fnmatch patterns relative to `src` (absolute paths inside `src`
    are accepted too). A pattern matching a directory applies to its whole subtree.
    Directories that cannot hold any whitelisted path, and blacklisted ones, are
    not explored at all. Files keep their permission bits and timestamps but not
    their extended attributes (unless kwargs are given, which selects shutil.copy2),
    and are copied in parallel when the file system is slow (see _copy_files).

    Args:
        src (str): Source directory.
        dst (str): Destination directory.
        dirs_exist_ok (bool): Whether to allow overwriting the destination directory.
        whitelist (list, optional): List of patterns to include (relative to `src`).
        blacklist (list, optional): List of patterns to exclude (relative to `src`).
        **kwargs: Additional arguments passed to shutil.copy2.
    """
    # Normalize paths
    src = os.path.realpath(src)
    dst = os.path.realpath(dst)

    white = _compile_copy_patterns(whitelist, src)
    black = _compile_copy_patterns(blacklist, src)

    def matches(rel_path, patterns):
        rel_path = os.path.normcase(rel_path)
        for regex, _, _ in patterns:
            if regex.match(rel_path):
                return True
        return False

    def may_hold_whitelisted(rel_dir):
        """Whether some whitelist pattern can match a path below `rel_dir`."""
        rel_dir = rel_dir + "/"
        for _, prefix, is_glob in white:
            if prefix.startswith(rel_dir) or (is_glob and rel_dir.startswith(prefix)):
                return True
        return False

    # Ensure destination exists
    if os.path.exists(dst):
        if not dirs_exist_ok:
            raise FileExistsError(f"Destination directory {dst} exists and dirs_exist_ok is False.")
    else:
        os.makedirs(dst)

    # (source, destination) of every file to copy
    copies = []
    # Relative directories (from src) whose whole subtree is whitelisted
    whitelisted_dirs = set([""]) if not white else set()

    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        rel_root = "" if rel_root == "." else rel_root.replace(os.sep, "/")
        root_whitelisted = rel_root in whitelisted_dirs

        kept_dirs = []
        for d in dirs:
            rel_dir = rel_root + "/" + d if rel_root else d
            if os.path.join(root, d) == dst:
                continue # never copy the destination into itself
            if black and matches(rel_dir, black):
                continue
            if root_whitelisted or matches(rel_dir, white):
                whitelisted_dirs.add(rel_dir)
            elif not may_hold_whitelisted(rel_dir):
                continue
            kept_dirs.append(d)
        dirs[:] = kept_dirs

        dst_root = os.path.join(dst, rel_root) if rel_root else dst
        dst_root_created = False
        for file in files:
            rel_file = rel_root + "/" + file if rel_root else file
            if not root_whitelisted and not matches(rel_file, white):
                continue
            if black and matches(rel_file, black):
                continue
            if not dst_root_created:
                os.makedirs(dst_root, exist_ok=True)
                dst_root_created = True
            copies.append((os.path.join(root, file), os.path.join(dst_root, file)))

    if kwargs:
        _copy_files(copies, lambda src_file, dst_file: shutil.copy2(src_file, dst_file, **kwargs))
    else:
        _copy_files(copies, _copy_file)

def chunk_list(lst, n):
    """Splits a list into chunks of size n."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

class KeyNotInListError(Exception):
    """Exception raised when a required key is missing in a list."""
    pass

class BadValueInListError(Exception):
    """Exception raised when a value in a list is of the wrong type."""
    pass

def read_from_list(key, input_list, filename, raise_if_missing=True, optional=False, print_error=True, parent=None, type=None, script_name=""):
    """
    Retrieves a value from a dictionary, with error handling and type validation.
    """
    parent_string = "" if parent == None else ", inside list \"" + parent + "\","
    if not isinstance(input_list, dict):
        # e.g. empty YAML file (None) or scalar where a mapping was expected
        if print_error:
            printc.error("Cannot find key \"" + key + "\"" + parent_string + " in \"" + filename + "\" because the file or parent key is empty or not a mapping.", script_name)
        if raise_if_missing:
            raise KeyNotInListError
        return False
    if key in input_list:
        value = input_list[key]
        if type is None:
            return value
        else:
            if isinstance(value, type):
                return value
            else:
                if print_error:
                    if optional:
                        printc.note("Value \"" + str(value) + "\" for key \"" + key + "\"" + parent_string + " in \"" + filename + "\" is of type \"" + value.__class__.__name__ + "\" while it should be of type \"" + type.__name__ + "\". Using default values instead.", script_name)
                    else:
                        printc.error("Value \"" + str(value) + "\" for key \"" + key + "\"" + parent_string + " in \"" + filename + "\" is of type \"" + value.__class__.__name__ + "\" while it should be of type \"" + type.__name__ + "\".", script_name)
                if raise_if_missing:
                    raise BadValueInListError
                return False
    else:
        if print_error:
            if optional:
                printc.note("Cannot find optional key \"" + key + "\"" + parent_string + " in \"" + filename + "\". Using default values instead.", script_name)
            else:
                printc.error("Cannot find key \"" + key + "\"" + parent_string + " in \"" + filename + "\".", script_name)
        if raise_if_missing:
            raise KeyNotInListError
        return False
    
def move_cursor_up():
    """Moves the terminal cursor up one line."""
    sys.stdout.write('\x1b[1A') # Move cursor up
    sys.stdout.write("\033[K") # Clear to the end of line
    sys.stdout.flush()

def progress_bar(progress, title, title_size=50, bar_size=50, endstr='', progress_char="#"):
    """Displays a progress bar in the terminal."""
    if progress is None:
        limit = 1
    else:
        if progress > 100:
            progress = 100
        limit = int(progress * bar_size / 100)

    padded_title = title.ljust(title_size)

    print(padded_title + " [", end='')
    if progress is None:
        printc.color(printc.colors.BLINK)
    for i in range(0, limit):
        print(progress_char, end='')
    for i in range(limit, bar_size):
        print(' ', end='')
    if progress is None:
        printc.color(printc.colors.ENDC)
    print("]", end='')
    if progress is not None:
        print(" {}%".format(int(progress)) + endstr)
    else:
        print()

def ask_to_continue(exit_code=-1):
    print("Continue? ", end="")
    answer = ask_yes_no()
    if answer is False:
        sys.exit(exit_code)
        
def ask_yes_no():
    while True:
        try:
            answer = input("(Y/n) ")
        except EOFError:
            # No terminal to answer from (stdin closed or redirected).
            print()
            print("No answer could be read: run again with -y/--noask to skip this question.")
            return False
        if answer.lower() in ['yes', 'ye', 'y', '1', '']:
            return True
        elif answer.lower() in ['no', 'n', '0']:
            return False
        else:
            print("Please enter yes or no")

def create_dir_if_missing(dir):
    """
    Creates a directory, keeping its content when it already exists.

    Used by jobs resuming a flow split into steps: their directory holds what
    the steps already run produced (checkpoints, reports, step state) and must
    not be wiped, unlike create_dir.
    """
    os.makedirs(dir, exist_ok=True)


def create_dir(dir):
    """Creates a directory, removing it first if it exists."""
    if os.path.isdir(dir):
        for attempt in range(5):  # Try multiple times in case of latency or locked files
            try:
                shutil.rmtree(dir)
                if not os.path.exists(dir):  # Check if deletion was successful
                    break
            except (PermissionError, OSError):
                time.sleep(0.5)  # Wait before retrying
        else:
            printc.error(f"Unable to delete {dir} after 5 attempts")

    os.makedirs(dir)

def internal_error(e, error_logfile, script_name):
    tb_full = traceback.format_exc()
    command_line = ' '.join(sys.argv)
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    system_info = {
        "OS": platform.system(),
        "OS Version": platform.version(),
        "Python Version": platform.python_version(),
        "Machine": platform.machine(),
    }
    with open(error_logfile, "w") as log_file:
        log_file.write("Date and Time: " + current_time + "\n\n")
        log_file.write("System Information:\n")
        for key, value in system_info.items():
            log_file.write("  " + key + ": " + value + "\n")
        log_file.write("\nOdatix Version: " + str(odatix.components.motd.read_version()) + "\n\n")
        log_file.write("\nCommand:\n")
        log_file.write("  " + command_line + "\n\n")
        log_file.write(tb_full)
    printc.internal_error(type(e).__name__ + ": " + str(e), script_name)
    printc.note('Full error details written to "' + error_logfile + '"', script_name)
    printc.note("Please, report this error with the error log attached", script_name)

def safe_df_append(df, row, ignore_index=True):
    if hasattr(df, 'append'):
        return df.append(row, ignore_index=ignore_index)
    elif hasattr(df, '_append'):
        return df._append(row, ignore_index=ignore_index)
    else:
        # pandas >= 3.0: no (private) append anymore
        import pandas as pd
        row_df = row if isinstance(row, pd.DataFrame) else pd.DataFrame([row])
        if df.empty:
            return row_df.reset_index(drop=True) if ignore_index else row_df
        return pd.concat([df, row_df], ignore_index=ignore_index)

def can_open_path_in_explorer():
    """Returns True if a file explorer can actually be opened on this system.

    On Linux, xdg-open needs a graphical session: without DISPLAY nor
    WAYLAND_DISPLAY (headless servers), opening a path would just fail.
    """
    if sys.platform.startswith("win") or sys.platform.startswith("darwin"):
        return True
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return False

def open_path_in_explorer(path):
    """Opens the given path in the system file explorer."""
    if not can_open_path_in_explorer():
        raise NotImplementedError("No file explorer available on this system")

    if sys.platform.startswith("win"): # Windows
        os.startfile(path)
    elif sys.platform.startswith("linux"): # Linux
        subprocess.run(["xdg-open", path])
    elif sys.platform.startswith("darwin"): # macOS
        subprocess.run(["open", path])
    else:
        raise NotImplementedError(f"Unsupported platform: {platform}")

def merge_dicts_of_lists(base_dict, merging_dict):
    for key, new_list in merging_dict.items():
        if key not in base_dict:
            base_dict[key] = list(new_list)
        else:
            combined = set(base_dict[key]) | set(new_list)
            base_dict[key] = sorted(combined)
    return base_dict

def get_timestamp_string() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S") 

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def port_is_free(host, port):
    """
    Whether a server can listen on `host`:`port` right now.

    The probe sets SO_REUSEADDR, as the servers Odatix starts do (waitress,
    uvicorn): a port only held by connections in TIME_WAIT, which a server
    stopped a few seconds ago leaves behind, counts as free. Without it a
    restarted GUI would move to the next port for a minute or so.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != "nt":
            # On Windows SO_REUSEADDR lets two sockets share a port: never set it there
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()

def find_free_port(host, start_port, max_find_port_attempts=100, strict=False, script_name=""):
    """
    Find a free port by incrementing from the start_port.

    With `strict`, `start_port` was asked for explicitly: if it is taken, say so
    and exit instead of moving to another port (a tunnel or a bookmark to that
    port would otherwise reach whatever listens there, or nothing).
    """
    if strict:
        if port_is_free(host, start_port):
            return start_port
        printc.error("port " + str(start_port) + " is already in use on " + str(host)
                     + ": choose another port with -p, or leave -p out to take the next free one", script_name)
        sys.exit(1)
    for port in range(start_port, start_port + max_find_port_attempts):
        if port_is_free(host, port):
            return port
    printc.error("Could not find any available port in range [" + str(start_port) + ":" + str(start_port + max_find_port_attempts - 1) + "]", script_name)
    sys.exit(-1)


def open_browser_when_ready(url, host, port, timeout=30.0, poll_interval=0.05, script_name=""):
    """Open `url` in a browser, but only once the server actually accepts connections.

    Opening the browser right away (before the app is built and waitress is
    listening) makes the browser display a connection error and forces the user
    to refresh the page manually.
    """
    import webbrowser

    connect_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    deadline = time.time() + timeout
    while time.time() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            sock.connect((connect_host, port))
            break
        except OSError:
            time.sleep(poll_interval)
        finally:
            sock.close()
    webbrowser.open(url, new=0, autoraise=True)
    printc.note(f"Browser opened (use -B to disable this behavior)", script_name)
