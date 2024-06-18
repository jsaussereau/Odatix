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

SCRIPT_DIR              = ./scripts
WORK_DIR                = ./work
LOG_DIR                 = $(WORK_DIR)/log

########################################################
# Files
########################################################

EXPORT_SCRIPT           = $(SCRIPT_DIR)/export_results.py
EXPLORE_SCRIPT          = $(SCRIPT_DIR)/start_result_explorer.py
RUN_SCRIPT              = $(SCRIPT_DIR)/run_config.py
MOTD_SCRIPT             = $(SCRIPT_DIR)/motd.py

########################################################
# Text formatting
########################################################

_BOLD                   =\033[1m
_END                    =\033[0m
_RED                    =\033[31m
_BLUE                   =\033[34m
_CYAN                   =\033[36m
_YELLOW                 =\033[33m
_GREEN                  =\033[32m
_WHITE                  =\033[37m
_GREY                   =\033[90m
_BLACK                  =\033[30m

VIVADO_COLOR            = "s/INFO/$(_CYAN)INFO$(_END)/;s/WARNING/$(_YELLOW)WARNING$(_END)/;s/ERROR/$(_RED)$(_BOLD)ERROR$(_END)/;s/<green>/$(_GREEN)/;s/<red>/$(_RED)/;s/<yellow>/$(_YELLOW)/;s/<cyan>/$(_CYAN)/;s/<bold>/$(_BOLD)/;s/<end>/$(_END)/"

########################################################
# Installation
########################################################

PIPX_INSTALL_CMD        = pipx install ./pipx --include-deps
PIPX_ACTIVATE_SCRIPT    = ~/.local/share/pipx/venvs/asterism/bin/activate
ACTIVATE_VENV           = [[ -f $(PIPX_ACTIVATE_SCRIPT) ]] && source $(PIPX_ACTIVATE_SCRIPT) && printf "$(_GREY)[Makefile]$(_END) activated asterism virtual environment\n"

########################################################
# General rules
########################################################

.PHONY: help
help: motd
	@printf "SYNTHESIS\n"
	@printf "\t$(_BOLD)make vivado$(_END): run synthesis + place&route in Vivado\n"
	@printf "\t$(_BOLD)make dc$(_END): run synthesis + place&route in Design Compiler\n"
	@printf "DATA EXPORT\n"
	@printf "\t$(_BOLD)make results$(_END): export synthesis results\n"
	@printf "\t$(_BOLD)make results_vivado$(_END): export Vivado synthesis results\n"
	@printf "\t$(_BOLD)make results_dc$(_END): export Design Compiler synthesis results\n"
	@printf "DATA EXPLORATION\n"
	@printf "\t$(_BOLD)make explore$(_END): explore results in a web app (localhost only)\n"
	@printf "\t$(_BOLD)make explore_network$(_END): explore results in a web app (network-accessible)\n"
	@printf "OTHERS\n"
	@printf "\t$(_BOLD)make help$(_END): display a list of useful commands\n"

.PHONY: motd
motd:
	@python3 $(MOTD_SCRIPT)

.PHONY: clean
clean: clean_vivado clean_dc

########################################################
# Installation
########################################################

.PHONY: pipx_install
pipx_install:
	@$(PIPX_INSTALL_CMD)

########################################################
# Vivado
########################################################

.PHONY: vivado
vivado: motd run_vivado_only clean_vivado results_vivado_only

.PHONY: run_vivado
run_vivado: motd run_vivado_only

.PHONY: run_vivado_only
run_vivado_only:
	@python3 $(RUN_SCRIPT) --tool vivado

.PHONY: results_vivado
results_vivado: motd results_vivado_only

.PHONY: results_vivado_only
results_vivado_only:
	@python3 ./$(EXPORT_SCRIPT) --tool vivado --benchmark

.PHONY: clean_vivado
clean_vivado:
	@rm -rf .Xil
	@rm -f *.jou
	@rm -f vivado*.log
	@rm -f tight_setup_hold_pins.txt

########################################################
# Design Compiler
########################################################

.PHONY: dc
dc: motd run_dc_only results_dc_only clean_dc_work

.PHONY: run_dc
run_dc: motd run_dc_only

.PHONY: run_dc_only
run_dc_only:
	@python3 $(SCRIPT_DIR)/run_config.py --tool design_compiler

.PHONY: results_dc
results_dc: motd results_dc_only

.PHONY: results_dc_only
results_dc_only:
	@python3 ./$(SCRIPT_DIR)/export_results.py --tool design_compiler --benchmark

.PHONY: clean_dc
clean_dc: clean_dc_work
	@rm -f command.log
	@rm -f default.svf
	@rm -f filenames*.log
	@rm -rf DC_WORK_*_autoread
	@rm -rf work/ARCH
	@rm -rf WORK_autoread
	@rm -rf work/ENTI
	@rm -f work/*.syn
	@rm -f work/*.mr
	@rm -f change_names_verilog

.PHONY: clean_dc_work
clean_dc_work:
	@rm -rf alib-*
	@rm -rf DC_WORK_*_autoread

########################################################
# Generic
########################################################

# export results 

.PHONY: results
results: motd results_only

.PHONY: results_only
results_only: results_vivado_only results_dc_only


# explore results

.PHONY: explore
explore: motd explore_only

.PHONY: explore_only
explore_only:
	@/bin/bash -c '$(ACTIVATE_VENV); python3 ./$(EXPLORE_SCRIPT)'

.PHONY: explore_network
explore_network: motd explore_network_only

.PHONY: explore_network_only
explore_network_only:
	@/bin/bash -c '$(ACTIVATE_VENV); python3 ./$(EXPLORE_SCRIPT) --network'
