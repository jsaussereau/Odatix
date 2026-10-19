#!/usr/bin/env bash
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

# Run a Quartus command in the Quartus environment.
#
#   quartus_env.sh <install path> [--log <file>] <command> [args...]
#
# The executables are taken from the installation given as tool_install_path
# in target_quartus.yml when it is set: the directory holding qinit.sh
# ("/opt/altera/altera_pro/26.1.1") or its quartus directory. It wins over a
# Quartus found on the PATH, which is used when no path is set. qinit.sh itself is not sourced: it finds the installation from its
# own location, which only bash gives it, and prints the PATH it builds.
#
# With --log, the output also goes to that file, and the exit code is still the
# one of the command, not the one of tee.

install_path="$1"
shift

log_file=""
if [ "$1" = "--log" ]; then
    log_file="$2"
    shift 2
fi

if [ -n "$install_path" ] && [ "$install_path" != "/" ]; then
    for root in "$install_path" "$install_path/quartus" "$install_path/.."; do
        if [ -x "$root/quartus/bin/quartus_sh" ]; then
            root="$(cd "$root" && pwd)"
            for dir in quartus/bin qsys/bin; do
                [ -d "$root/$dir" ] && PATH="$root/$dir:$PATH"
            done
            [ -d "$root/qsys/bin" ] && export QSYS_ROOTDIR="$root/qsys/bin"
            export PATH
            break
        fi
    done
fi

if ! command -v quartus_sh > /dev/null 2>&1; then
    echo "error: quartus_sh not found" >&2
    echo "note: put the Quartus executables in your PATH, or set tool_install_path in target_quartus.yml" >&2
    echo "      to the directory of your installation that holds qinit.sh (e.g. /opt/altera/altera_pro/26.1.1)" >&2
    exit 127
fi

# Quartus messages are in English whatever the locale, the Tcl number parsing
# of the scripts is not.
export LC_ALL=C

if [ -z "$log_file" ]; then
    exec "$@"
fi

mkdir -p "$(dirname "$log_file")"
set -o pipefail
"$@" 2>&1 | tee "$log_file"
