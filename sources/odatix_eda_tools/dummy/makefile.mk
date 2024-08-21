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

########################################################
# Paths
########################################################

WORK_DIR                = ./work
SCRIPT_DIR              = ./scripts
LOG_DIR                 = ./log

########################################################
# Files
########################################################

INIT_SCRIPT             = init_script.tcl
ANALYZE_SCRIPT          = analyze_script.tcl
SYNTH_SCRIPT            = synth_script.tcl
SYNTH_FREQ_SCRIPT       = find_fmax.tcl
EXIT_SCRIPT             = exit.tcl

########################################################
# Tool specific
########################################################

TCLSH					= /bin/tclsh
VIVADO_INIT             = export LC_ALL=C; unset LANGUAGE;

########################################################
# Text formatting
########################################################

_BOLD                   =\x1b[1m
_END                    =\x1b[0m
_BLACK                  =\x1b[30m
_RED                    =\x1b[31m
_GREEN                  =\x1b[32m
_YELLOW                 =\x1b[33m
_BLUE                   =\x1b[34m
_MAGENTA                =\x1b[35m
_CYAN                   =\x1b[36m
_WHITE                  =\x1b[37m
_GREY                   =\x1b[90m

TCL_COLOR               = "s/INFO/$(_CYAN)INFO$(_END)/;s/WARNING/$(_YELLOW)WARNING$(_END)/;s/ERROR/$(_RED)$(_BOLD)ERROR$(_END)/;s/<green>/$(_GREEN)/;s/<red>/$(_RED)/;s/<yellow>/$(_YELLOW)/;s/<cyan>/$(_CYAN)/;s/<blue>/$(_BLUE)/;s/<magenta>/$(_MAGENTA)/;s/<grey>/$(_GREY)/;s/<bold>/$(_BOLD)/;s/<end>/$(_END)/g"

########################################################
# Rules
########################################################

.PHONY: all
all: synth_fmax_only

########################################################
# Synthesis
########################################################

.PHONY: synth_fmax_only
synth_fmax_only: logdir
	@$(TCLSH) $(SCRIPT_DIR)/$(SYNTH_FREQ_SCRIPT) | sed $(TCL_COLOR);

.PHONY: test_tool
test_tool:
	@echo "puts $tcl_version;exit 0" | $(TCLSH)

.PHONY: logdir
logdir:
	@mkdir -p $(LOG_DIR)
