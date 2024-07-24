#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#


########################################################
# Paths
########################################################

OPENLANE_DIR            = ~/Documents/ASIC/OpenLane
SCRIPT_DIR              = ./scripts
LOG_DIR                 = ./log
WORK_DIR                = ./tmp

########################################################
# Files
########################################################

LOG_FILE                = $(LOG_DIR)/find_fmax.log
LOG_FILE                = $(LOG_DIR)/synth.log
GEN_CONFIG_SCRIPT       = eda_tools/openlane/scripts/gen_config.py
SYNTH_FMAX_SCRIPT       = eda_tools/openlane/scripts/synth_fmax.py

########################################################
# Tool specific
########################################################

YOSYS                   = yosys

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

YOSYS_COLOR             = "s/INFO/$(_CYAN)INFO$(_END)/;s/WARNING/$(_YELLOW)WARNING$(_END)/;s/ERROR/$(_RED)$(_BOLD)ERROR$(_END)/;s/<green>/$(_GREEN)/;s/<red>/$(_RED)/;s/<yellow>/$(_YELLOW)/;s/<cyan>/$(_CYAN)/;s/<blue>/$(_BLUE)/;s/<magenta>/$(_MAGENTA)/;s/<grey>/$(_GREY)/;s/<bold>/$(_BOLD)/;s/<end>/$(_END)/g"

SIGNATURE               = $(_GREY)[eda_tools/openlane/makefile.mk]$(_END)

########################################################
# Rules
########################################################

.PHONY: synth_fmax_only
synth_fmax_only: 
	@printf "$(SIGNATURE) Stoping existing Docker container...\n"
	@docker stop $(LIB_NAME) 2>/dev/null || true
	@printf "$(SIGNATURE) Starting a new OpenLane Docker container...\n"
	@printf "$(_BOLD) > "
	@rm -rf $(WORK_DIR)/scripts $(WORK_DIR)/result $(WORK_DIR)/src | tee $(LOG_FILE)
	@bash -c "cd $(OPENLANE_DIR); make mount ENV_MOUNT='-d -v $(OPENLANE_DIR):/openlane --name $(LIB_NAME)'" | tee -a $(LOG_FILE)
	@printf "$(_END)"
	@printf "$(SIGNATURE) Waiting for Docker container... "
	@start_time=$$(date +%s); \
	end_time=$$((start_time + $(WAIT_TIME))); \
	while [ $$(date +%s) -lt $$end_time ]; do \
		if [ $$(docker inspect -f '{{.State.Running}}' $(LIB_NAME) 2>/dev/null) = "true" ]; then \
			printf "ready!\n" | tee -a $(LOG_FILE); \
			ready=true; \
			break; \
		fi; \
		sleep $(INTERVAL); \
	done; \
	if [ "$$ready" != "true" ]; then \
		printf "\n$(SIGNATURE) $(_BOLD)$(_RED)error:$(_END) $(_RED) Docker container not ready after $(WAIT_TIME) seconds\n" | tee -a $(LOG_FILE); \
		exit 1; \
	fi
		
	@python3 $(SYNTH_FMAX_SCRIPT) \
		--basepath $(WORK_DIR) \
		--command "docker exec -it $(LIB_NAME) /bin/sh -c 'cd $(WORK_DIR); /openlane/flow.tcl -tag asterism -overwrite' | tee -a $(SYNTH_LOG_FILE)" \
		| tee -a $(SYNTH_LOG_FILE)
	@docker stop $(LIB_NAME)

.PHONY: synth_
synth_:
	@rm -rf $(WORK_DIR)/scripts $(WORK_DIR)/result $(WORK_DIR)/src | tee $(LOG_FILE)
	@screen -dm bash -c "cd $(OPENLANE_DIR); make mount" | tee -a $(LOG_FILE)
	@$(eval DOCKER_ID := $(shell docker ps -lq))
	@printf "DOCKER_ID = $(DOCKER_ID)\n" | tee -a $(LOG_FILE)
	@sleep 2
	@python3 $(GEN_CONFIG_SCRIPT) --docker $(DOCKER_ID) --basepath $(WORK_DIR) | tee -a $(LOG_FILE)
	@docker exec -it $(DOCKER_ID) /bin/sh -c 'cd $(WORK_DIR); /openlane/flow.tcl -tag asterism' | tee -a $(LOG_FILE)

.PHONY: test_tool
test_tool:
	@$(YOSYS) --version
