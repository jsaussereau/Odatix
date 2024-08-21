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

OPENLANE_DIR            = ~/Documents/ASIC/OpenLane
SCRIPT_DIR              = ./scripts
LOG_DIR                 = ./log
REPORT_DIR              = ./report
WORK_DIR                = ./tmp

########################################################
# Files
########################################################

SYNTH_FREQ_SCRIPT       = find_fmax.tcl
LOG_FILE                = $(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log
GEN_CONFIG_SCRIPT       = eda_tools/openlane/scripts/gen_config.py

########################################################
# Tool specific
########################################################

LIB_NAME                = openlane_test

MOUNT_CMD               = cd $(OPENLANE_DIR); make mount ENV_MOUNT='-d -v $(OPENLANE_DIR):/openlane --name $(LIB_NAME)'
FLOW_CMD                = docker exec $(LIB_NAME) /bin/sh -c 'cd $(WORK_DIR); tclsh scripts/$(SYNTH_FREQ_SCRIPT)'
GEN_CONFIG_CMD          = python3 $(GEN_CONFIG_SCRIPT) --basepath $(WORK_DIR)
TEST_CMD                = docker exec $(LIB_NAME) /bin/sh -c 'exit'

CLOCK_SIGNAL            = clock
TOP_LEVEL_MODULE        = module

WAIT_TIME ?= 10
INTERVAL ?= 1

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

OPENLANE_COLOR          = "s/INFO/$(_CYAN)INFO$(_END)/;s/WARNING/$(_YELLOW)WARNING$(_END)/;s/ERROR/$(_RED)$(_BOLD)ERROR$(_END)/;s/<green>/$(_GREEN)/;s/<red>/$(_RED)/;s/<yellow>/$(_YELLOW)/;s/<cyan>/$(_CYAN)/;s/<blue>/$(_BLUE)/;s/<magenta>/$(_MAGENTA)/;s/<grey>/$(_GREY)/;s/<bold>/$(_BOLD)/;s/<end>/$(_END)/g"

SIGNATURE               = $(_GREY)[eda_tools/openlane/makefile.mk]$(_END)

########################################################
# Rules
########################################################
.PHONY: synth_fmax_only
synth_fmax_only: dirs 
	@printf "\n$(SIGNATURE) $(_CYAN)Kill existing Docker container$(_END)\n"
	@docker kill $(LIB_NAME) 2>/dev/null || true
	@printf "$(SIGNATURE) $(_CYAN)Start a new OpenLane Docker container$(_END)\n"
	@rm -rf $(WORK_DIR)/result $(WORK_DIR)/src
	@printf "$(_BOLD) > $(MOUNT_CMD)$(_END)"
	@bash -c "$(MOUNT_CMD)"
	@printf "$(SIGNATURE) $(_CYAN)Wait for Docker container$(_END)"
	@start_time=$$(date +%s); \
	end_time=$$((start_time + $(WAIT_TIME))); \
	while [ $$(date +%s) -lt $$end_time ]; do \
		if [ $$(docker inspect -f '{{.State.Running}}' $(LIB_NAME) 2>/dev/null) = "true" ]; then \
			printf "ready!\n"; \
			ready=true; \
			break; \
		fi; \
		sleep $(INTERVAL); \
	done; \
	if [ "$$ready" != "true" ]; then \
		printf "\n$(SIGNATURE) $(_BOLD)$(_RED)error:$(_END) $(_RED) Docker container not ready after $(WAIT_TIME) seconds\n"; \
		exit 1; \
	fi
	@$(GEN_CONFIG_CMD)
	@printf "$(SIGNATURE) $(_CYAN)Run Fmax synthesis flow$(_END)"
	@printf "$(_BOLD) > $(FLOW_CMD)$(_END)"
	@$(FLOW_CMD) | tee $(LOG_FILE) | sed $(OPENLANE_COLOR) ; \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	[ $$EXIT_CODE -eq 0 ] || exit $$EXIT_CODE
	@printf "\n$(SIGNATURE) $(_CYAN)Stop Docker container$(_END)\n"
	@docker kill $(LIB_NAME) 2>/dev/null || true
	@printf "\n$(SIGNATURE) $(_GREEN)Done!$(_END)\n"

.PHONY: test_tool
test_tool:
	@docker kill $(LIB_NAME) 2>/dev/null || true
	@$(MOUNT_CMD)
	@start_time=$$(date +%s); \
	end_time=$$((start_time + $(WAIT_TIME))); \
	while [ $$(date +%s) -lt $$end_time ]; do \
		if [ $$(docker inspect -f '{{.State.Running}}' $(LIB_NAME) 2>/dev/null) = "true" ]; then \
			ready=true; \
			break; \
		fi; \
		sleep $(INTERVAL); \
	done; \
	if [ "$$ready" != "true" ]; then \
		exit 1; \
	fi
	@$(TEST_CMD)
	@docker kill $(LIB_NAME) 2>/dev/null || true

.PHONY: dirs
dirs:
	@mkdir -p $(LOG_DIR)
	@mkdir -p $(REPORT_DIR)
