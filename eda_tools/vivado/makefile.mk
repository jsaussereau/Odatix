#******************************************************#
#     					AsteRISC     
#******************************************************#
#
# Copyright(C) 2022 by Jonathan Saussereau. All rights reserved.
# 
# All source codes and documentation contain proprietary confidential
# information and are distributed under license. It may be used, copied
# and/or disclosed only pursuant to the terms of a valid license agreement
# with Jonathan Saussereau. This copyright must be retained at all times.
#
# Vivado Makefile
#
# Last edited: 2022/07/04 18:20
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

ANALYZE_SCRIPT          = analyze_script.tcl
SYNTH_SCRIPT            = synth_script.tcl
SYNTH_FREQ_SCRIPT       = find_fmax.tcl
EXIT_SCRIPT             = exit.tcl

########################################################
# Tool specific
########################################################

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

HASH := \#

VIVADO_COLOR            = "s/INFO/$(_CYAN)INFO$(_END)/;s/WARNING/$(_YELLOW)WARNING$(_END)/;s/ERROR/$(_RED)$(_BOLD)ERROR$(_END)/;s/<green>/$(_GREEN)/;s/<red>/$(_RED)/;s/<yellow>/$(_YELLOW)/;s/<cyan>/$(_CYAN)/;s/<blue>/$(_BLUE)/;s/<magenta>/$(_MAGENTA)/;s/<bold>/$(_BOLD)/;s/<end>/$(_END)/g"

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
	vivado -mode tcl -notrace \
	-source $(SCRIPT_DIR)/$(ANALYZE_SCRIPT) \
	| tee $(LOG_DIR)/$(ANALYZE_SCRIPT).log | sed $(VIVADO_COLOR)
	@echo "result logged to \"$(LOG_DIR)/$(ANALYZE_SCRIPT).log\""

.PHONY: synth_fmax
synth_fmax: motd synth_fmax_only clean

.PHONY: synth_fmax_only
synth_fmax_only: logdir
	@$(VIVADO_INIT)\
	vivado -mode tcl -notrace \
	-source $(SCRIPT_DIR)/$(SYNTH_FREQ_SCRIPT) \
	-source $(SCRIPT_DIR)/$(EXIT_SCRIPT) \
	| tee $(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log \
	| sed $(VIVADO_COLOR); \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	echo "result logged to \"$(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log\""; \
	exit $$EXIT_CODE

.PHONY: test
test:
	@exit 0

.PHONY: synth
synth: motd synth_only clean

.PHONY: synth_only
synth_only: logdir
	@$(VIVADO_INIT)\
	vivado -mode tcl -notrace \
	-source $(SCRIPT_DIR)/$(ANALYZE_SCRIPT) \
	-source $(SCRIPT_DIR)/$(SYNTH_SCRIPT) \
	-source $(SCRIPT_DIR)/$(EXIT_SCRIPT) \
	| tee $(LOG_DIR)/$(SYNTH_SCRIPT).log | sed $(VIVADO_COLOR)

.PHONY: vivado
vivado:
	@$(VIVADO_INIT)\
	vivado -mode tcl -notrace \
	| sed $(VIVADO_COLOR)

.PHONY: logdir
logdir:
	@mkdir -p $(LOG_DIR)
