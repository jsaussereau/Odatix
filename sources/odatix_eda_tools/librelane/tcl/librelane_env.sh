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

# Run a command in the LibreLane environment.
#
#   librelane_env.sh <install_path> <command> [args...]
#
# LibreLane ships its tools (Yosys, OpenROAD, Magic, KLayout, ...) through Nix.
# When "librelane" is already on the PATH (Odatix started from a nix-shell, or a
# pip install with the tools installed by hand), the command runs as is.
# Otherwise <install_path> must be a LibreLane checkout: the command then runs
# in its nix-shell. That is "tool_install_path" in the target file.

install_path="$1"
shift

if [ $# -eq 0 ]; then
  echo "librelane_env.sh: no command given" >&2
  exit 2
fi

# LibreLane logs through rich, which wraps at the terminal width: 80 columns
# when there is no terminal, as in an Odatix job. Wide enough for one message
# per line.
export COLUMNS="${ODATIX_LIBRELANE_COLUMNS:-200}"

if command -v librelane > /dev/null 2>&1; then
  exec "$@"
fi

install_path="${install_path/#\~/$HOME}"

if [ -z "$install_path" ]; then
  echo "error: librelane is not on the PATH and no tool_install_path is set in the target file (target_librelane.yml)" >&2
  exit 127
fi

if [ ! -f "$install_path/shell.nix" ] && [ ! -f "$install_path/flake.nix" ]; then
  echo "error: \"$install_path\" is not a LibreLane checkout (no shell.nix or flake.nix there)" >&2
  exit 127
fi

if ! command -v nix-shell > /dev/null 2>&1; then
  echo "error: nix-shell not found: install Nix, or run Odatix from an environment where librelane is on the PATH" >&2
  exit 127
fi

exec nix-shell "$install_path" --run "$(printf '%q ' "$@")"
