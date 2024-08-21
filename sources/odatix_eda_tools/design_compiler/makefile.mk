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

########################################################
# Tool specific
########################################################

DC_COMPILER				= design_vision

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

DC_COLOR				= "s/Information/$(_CYAN)Information$(_END)/;s/Warning/$(_YELLOW)Warning$(_END)/;s/Error/$(_RED)$(_BOLD)Error$(_END)/;s/<green>/$(_GREEN)/;s/<red>/$(_RED)/;s/<cyan>/$(_CYAN)/;s/<magenta>/$(_MAGENTA)/;s/<grey>/$(_GREY)/;s/<bold>/$(_BOLD)/;s/<Err0r>/Error/;s/<W4rning>/Warning/;s/<end>/$(_END)/g"

########################################################
# Rules
########################################################

.PHONY: synth_fmax_only
synth_fmax_only: logdir
	@cd $(WORK_DIR); \
	$(DC_COMPILER) -no_gui -x "cd ../../../../../; source $(SCRIPT_DIR)/$(SYNTH_FREQ_SCRIPT); quit" \
	| tee ../../../../../$(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log \
	| sed $(DC_COLOR); \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	echo "result logged to \"$(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log\""; \
	exit $$EXIT_CODE

.PHONY: test_tool
test_tool:
	$(DC_COMPILER) -no_gui -x "exit"

.PHONY: logdir
logdir:
	@mkdir -p $(LOG_DIR)
