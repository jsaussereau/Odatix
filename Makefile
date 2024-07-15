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

SCRIPT_DIR              = scripts
CURRENT_DIR             = .
WORK_DIR                = $(CURRENT_DIR)/work
BUILD_DIR               = build
DIST_DIR                = dist
RELEASE_DIR             = release
TOOLS_DIR               = eda_tools

########################################################
# Files
########################################################

ASTERISM_SCRIPT         = $(SCRIPT_DIR)/asterism.py
EXPLORE_SCRIPT          = $(SCRIPT_DIR)/asterism-explorer.py
EXPORT_SCRIPT           = $(ASTERISM_SCRIPT) res_synth --nobanner
BENCHMARKS_SCRIPT		= $(ASTERISM_SCRIPT) res_benchmark --nobanner
SYNTH_SCRIPT            = $(ASTERISM_SCRIPT) synth --nobanner
SIM_SCRIPT              = $(ASTERISM_SCRIPT) sim --nobanner
MOTD_SCRIPT             = $(SCRIPT_DIR)/motd.py
VIVADO_SUCCESS_FILE     = $(WORK_DIR)/.run_vivado_success
VERSION_FILE            = version.txt
DIST_ASTERISM           = $(DIST_DIR)/asterism
DIST_ASTERISM_EXPLORER  = $(DIST_DIR)/asterism-explorer

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

PIPX_CHECK              = command -v pipx >/dev/null 2>&1
PIPX_INSTALL_CMD        = pipx install ./pipx --include-deps
PIPX_VENV_PATH          = $(shell $(PIPX_CHECK) && pipx list | sed -n "s/venvs are in \(.*\)/\1/p")
PIPX_ACTIVATE_SCRIPT    = $(PIPX_VENV_PATH)/asterism/bin/activate
ACTIVATE_VENV           = [[ -f $(PIPX_ACTIVATE_SCRIPT) ]] && source $(PIPX_ACTIVATE_SCRIPT) && printf "$(_GREY)[Makefile]$(_END) activated asterism virtual environment\n"

VERSION                 := $(shell cat $(VERSION_FILE))
RELEASE_NAME            := asterism-$(VERSION)

########################################################
# General rules
########################################################

.PHONY: help
help: full_motd
	@printf "SIMULATION\n"
	@printf "\t$(_BOLD)make sim$(_END): run simulations\n"
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

.PHONY: full_motd
full_motd:
	@python3 $(MOTD_SCRIPT) -f
.PHONY: motd
motd:
	@python3 $(MOTD_SCRIPT)

.PHONY: clean
clean: clean_vivado clean_dc

########################################################
# Installation
########################################################

.PHONY: check_pipx
check_pipx:
	@if ! $(PIPX_CHECK); then \
		printf "$(_GREY)[Makefile]$(_END) $(_BOLD)$(_RED)error:$(_END) $(_RED)pipx is not installed. Please install pipx to proceed with installation of python requirements\n"; \
		printf "$(_GREY)[Makefile]$(_END) $(_CYAN)note:$(_END) $(_CYAN)follow installation guide at $(_BLUE)https://asterism.readthedocs.io/en/latest/installation.html$(_END)\n"; \
		exit 1; \
	fi

.PHONY: pipx_install
pipx_install: check_pipx
	@$(PIPX_INSTALL_CMD)

########################################################
# Build
########################################################$

SOURCE_FILES = $(wildcard $(SCRIPT_DIR)/*.py) $(wildcard $(SCRIPT_DIR)/**/*.py)

.PHONY: build
build: $(DIST_DIR)/asterism $(DIST_DIR)/asterism-explorer

$(DIST_DIR)/asterism: $(SOURCE_FILES)
	@pyinstaller $(SCRIPT_DIR)/asterism.py --onefile --path $(SCRIPT_DIR)/lib

$(DIST_DIR)/asterism-explorer: $(SOURCE_FILES)
	@pyinstaller asterism-explorer.spec

.PHONY: clean_build
clean_build:
	@rm -rf $(BUILD_DIR)
	@rm -rf $(DIST_DIR)

.PHONY: release
release: $(DIST_DIR)/asterism $(DIST_DIR)/asterism-explorer release_only

.PHONY: release_only
release_only:
	@mkdir -p $(RELEASE_DIR)/$(RELEASE_NAME)/bin
	@cp -r $(DIST_DIR)/* $(RELEASE_DIR)/$(RELEASE_NAME)/bin
	@cp -r  $(TOOLS_DIR) $(RELEASE_DIR)/$(RELEASE_NAME)
	@cp $(VERSION_FILE) $(RELEASE_DIR)/$(RELEASE_NAME)
	@find $(TOOLS_DIR) -type d -name __pycache__ -prune -exec rm -rf {} \;
	@bash -c "cd $(RELEASE_DIR); zip -FSr $(RELEASE_NAME).zip $(RELEASE_NAME)"

.PHONY: clean_release
clean_release:
	@rm -rf $(RELEASE_DIR)

########################################################
# Simulation
########################################################

.PHONY: sim
sim: motd sim_only

.PHONY: sim_only
sim_only: 
	@python3 $(SIM_SCRIPT) $(OPTIONS)

.PHONY: results_benchmarks
results_benchmarks: motd results_benchmarks_only

.PHONY: results_benchmarks_only
results_benchmarks_only: 
	@python3 $(BENCHMARKS_SCRIPT) $(OPTIONS)

########################################################
# Vivado
########################################################

.PHONY: vivado
vivado: motd run_vivado_only clean_vivado

.PHONY: run_vivado
run_vivado: motd run_vivado_only

.PHONY: run_vivado_only
run_vivado_only:
	@python3 $(SYNTH_SCRIPT) --tool vivado $(OPTIONS)

.PHONY: results_vivado
results_vivado: motd results_vivado_only

.PHONY: results_vivado_only
results_vivado_only:
	@python3 $(EXPORT_SCRIPT) --tool vivado --use_benchmark $(OPTIONS)

.PHONY: clean_vivado
clean_vivado:
	@rm -rf $(CURRENT_DIR)/.Xil
	@rm -f  $(CURRENT_DIR)/*.jou
	@rm -f  $(CURRENT_DIR)/vivado*.log
	@rm -f  $(CURRENT_DIR)/tight_setup_hold_pins.txt

########################################################
# Design Compiler
########################################################

.PHONY: dc
dc: motd run_dc_only clean_dc_work

.PHONY: run_dc
run_dc: motd run_dc_only

.PHONY: run_dc_only
run_dc_only:
	@python3 $(SYNTH_SCRIPT) --tool design_compiler $(OPTIONS) 

.PHONY: results_dc
results_dc: motd results_dc_only

.PHONY: results_dc_only
results_dc_only:
	@python3 $(EXPORT_SCRIPT) --tool design_compiler --use_benchmark $(OPTIONS)

.PHONY: clean_dc
clean_dc: clean_dc_work
	@rm -f  $(CURRENT_DIR)/command.log
	@rm -f  $(CURRENT_DIR)/default.svf
	@rm -f  $(CURRENT_DIR)/change_names_verilog
	@rm -f  $(CURRENT_DIR)/filenames*.log
	@rm -rf $(CURRENT_DIR)/DC_WORK_*_autoread
	@rm -rf $(CURRENT_DIR)/WORK_autoread
	@rm -rf $(WORK_DIR)/ARCH
	@rm -rf $(WORK_DIR)/ENTI
	@rm -f  $(WORK_DIR)/*.syn
	@rm -f  $(WORK_DIR)/*.mr

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
	@/bin/bash -c '$(ACTIVATE_VENV); python3 ./$(EXPLORE_SCRIPT) $(OPTIONS)'

.PHONY: explore_network
explore_network: motd explore_network_only

.PHONY: explore_network_only
explore_network_only:
	@/bin/bash -c '$(ACTIVATE_VENV); python3 ./$(EXPLORE_SCRIPT) --network $(OPTIONS)'
