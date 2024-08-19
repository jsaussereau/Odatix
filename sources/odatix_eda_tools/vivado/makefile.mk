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

VIVADO					= vivado
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

HASH := \#

VIVADO_COLOR            = "s/INFO/$(_CYAN)INFO$(_END)/;s/WARNING/$(_YELLOW)WARNING$(_END)/;s/ERROR/$(_RED)$(_BOLD)ERROR$(_END)/;s/<green>/$(_GREEN)/;s/<red>/$(_RED)/;s/<yellow>/$(_YELLOW)/;s/<cyan>/$(_CYAN)/;s/<blue>/$(_BLUE)/;s/<magenta>/$(_MAGENTA)/;s/<grey>/$(_GREY)/;s/<bold>/$(_BOLD)/;s/<end>/$(_END)/g"

########################################################
# Rules
########################################################

.PHONY: all
all: motd synth par


.PHONY: clean
clean:
	@rm -f ./*.jou
	@rm -f ./vivado*.log

.PHONY: motd
motd:
	@echo -ne "$(_BOLD)"
	@echo "********************************************************************"
	@echo "*                           Vivado Flow                            *"
	@echo "********************************************************************"
	@echo -ne "$(_END)"
	@echo ""

.PHONY: help
help:
	@echo -e "SYNTHESIS"
	@echo -e "\t$(_BOLD)make analyze$(_END): run $(ANALYZE_SCRIPT) (check syntax)"
	@echo -e "\t$(_BOLD)make synth$(_END): run the whole synthesis script"
	@echo -e "\t$(_BOLD)make synth_fmax$(_END): run synthesis with a binary search to find max frequency"
	@echo -e "OTHERS"
	@echo -e "\t$(_BOLD)make help$(_END): display a list of useful rules"

########################################################
# Synthesis
########################################################

.PHONY: analyze
analyze: motd analyze_only clean

.PHONY: analyze_only
analyze_only: logdir
	@$(VIVADO_INIT)\
	$(VIVADO) -mode tcl -notrace \
	-source $(SCRIPT_DIR)/$(INIT_SCRIPT) \
	-source $(SCRIPT_DIR)/$(ANALYZE_SCRIPT) \
	| tee $(LOG_DIR)/$(ANALYZE_SCRIPT).log | sed $(VIVADO_COLOR)
	@echo "result logged to \"$(LOG_DIR)/$(ANALYZE_SCRIPT).log\""

.PHONY: synth_fmax
synth_fmax: motd synth_fmax_only clean

.PHONY: synth_fmax_only
synth_fmax_only: logdir
	@/bin/bash -c '\
	$(VIVADO_INIT)\
	$(VIVADO) -mode tcl -notrace \
	-source $(SCRIPT_DIR)/$(SYNTH_FREQ_SCRIPT) \
	-source $(SCRIPT_DIR)/$(EXIT_SCRIPT) \
	| tee $(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log \
	| sed $(VIVADO_COLOR); \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	echo "result logged to \"$(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log\""; \
	exit $$EXIT_CODE'

.PHONY: test
test:
	@exit 0

.PHONY: synth
synth: motd synth_only clean

.PHONY: synth_only
synth_only: logdir
	@$(VIVADO_INIT)\
	$(VIVADO) -mode tcl -notrace \
	-source $(SCRIPT_DIR)/$(INIT_SCRIPT) \
	-source $(SCRIPT_DIR)/$(ANALYZE_SCRIPT) \
	-source $(SCRIPT_DIR)/$(SYNTH_SCRIPT) \
	-source $(SCRIPT_DIR)/$(EXIT_SCRIPT) \
	| tee $(LOG_DIR)/$(SYNTH_SCRIPT).log | sed $(VIVADO_COLOR)

.PHONY: vivado
vivado:
	@$(VIVADO_INIT)\
	$(VIVADO) -mode tcl -notrace \
	| sed $(VIVADO_COLOR)

.PHONY: test_tool
test_tool:
	@$(VIVADO_INIT) $(VIVADO) -version

.PHONY: logdir
logdir:
	@mkdir -p $(LOG_DIR)
