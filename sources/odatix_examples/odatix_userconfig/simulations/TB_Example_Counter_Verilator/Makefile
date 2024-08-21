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

WORK_DIR = .
RTL_DIR = ../../examples/counter_sv
OBJ_DIR = $(WORK_DIR)/obj
LOG_DIR = $(WORK_DIR)/log
VCD_DIR = $(WORK_DIR)/vcd
TB_DIR  = $(WORK_DIR)/tb

ENV_SET = export LC_ALL=C; unset LANGUAGE;

########################################################
# Simulation Parameters
########################################################

MODULE = counter
VCD_FILE = $(VCD_DIR)/$(MODULE).vcd

########################################################
# Files
########################################################

VERILATOR_LOGFILE = verilator.log
SIM_LOGFILE = sim.log

# Compiler les fichiers SystemVerilog
EXCLUDE_PREFIX = tb_
RTL_FILES := $(shell find $(RTL_DIR) -name '*.sv' -not -name '$(EXCLUDE_PREFIX)*')
SV_FILES := $(wildcard $(RTL_DIR)/**/*.sv)

# Compiler les fichiers C++
CPP_FILES := $(wildcard $(TB_DIR)/*.cpp)

# Définir les cibles pour les fichiers Verilated
SIM_FILE = $(OBJ_DIR)/V$(MODULE)

PROGRESS_FILE = $(LOG_DIR)/progress.log

# Options Verilator
VERILATOR_FLAGS = -Wall -Wno-UNUSEDPARAM -Wno-UNUSEDSIGNAL --trace --x-assign unique --x-initial unique

########################################################
# Text formatting
########################################################

_END     =\033[0m
_BOLD    =\033[1m
_BLACK   =\033[30m
_RED     =\033[31m
_GREEN   =\033[32m
_YELLOW  =\033[33m
_BLUE    =\033[34m
_MAGENTA =\033[35m
_CYAN    =\033[36m
_WHITE   =\033[37m
_GREY    =\033[90m

VERILATOR_COLOR := $(shell printf 's/%%Error\\(\\S*\\):\\(.*\\)/%%$(_BOLD)$(_RED)Error\\1$(_END):$(_RED)\\2$(_END)/g;s/%%Warning\\(\\S*\\):\\(.*\\)/%%$(_BOLD)$(_YELLOW)Warning\\1$(_END):$(_YELLOW)\\2$(_END)/g')########################################################

########################################################
# Rules
########################################################

.PHONY: help
help:
	@printf "VERIFICATION\n"
	@printf "\t$(_BOLD)make lint$(_END): check syntax of rtl files\n"
	@printf "SIMULATION\n"
	@printf "\t$(_BOLD)make verilate$(_END): compile rtl\n"
	@printf "\t$(_BOLD)make sim$(_END): run the simulation\n"
	@printf "\t$(_BOLD)make view$(_END): view simulation waveform\n"
	@printf "OTHERS\n"
	@printf "\t$(_BOLD)make clean$(_END): clean generated files\n"
	@printf "\t$(_BOLD)make help$(_END): display a list of useful commands\n"

.PHONY: sim
sim: $(VCD_FILE)

.PHONY: view
view:
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "              View Waves              \n"
	@printf "######################################\n"
	@printf "$(_END)\n"
	@gtkwave $(VCD_FILE) -a gtkwave_setup.gtkw

$(VCD_FILE): $(SIM_FILE)
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "              Simulating              \n"
	@printf "######################################\n"
	@printf "$(_END)\n"
	@$(SIM_FILE) --vcd_file "$(VCD_FILE)" \
	| tee "$(LOG_DIR)/$(SIM_LOGFILE)" | sed "$(VERILATOR_COLOR)"
#	+verilator+rand+reset+2 
	@echo "progress: 100%" > $(PROGRESS_FILE)

$(SIM_FILE): .stamp.verilate
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "         Building Simulation          \n"
	@printf "######################################\n"
	@printf "$(_END)"
	@make -C $(OBJ_DIR) -f V$(MODULE).mk V$(MODULE) MAKEFLAGS=s --no-print-directory
	@echo "progress: 75%" > $(PROGRESS_FILE)


.PHONY: verilate
verilate: .stamp.verilate

.stamp.verilate: makedir $(SV_FILES) $(CPP_FILES)
	@echo "progress: 5%" > $(PROGRESS_FILE)
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "              Verilating              \n"
	@printf "######################################\n"
	@printf "$(_END)\n"
	@$(ENV_SET) verilator -Mdir $(OBJ_DIR) --top-module $(MODULE) $(VERILATOR_FLAGS) -cc $(RTL_FILES) --exe $(CPP_FILES) \
	2>&1 | tee "$(LOG_DIR)/$(VERILATOR_LOGFILE)" | sed "$(VERILATOR_COLOR)"
	@touch .stamp.verilate
	@echo "progress: 25%" > $(PROGRESS_FILE)

.PHONY: lint
lint: $(SV_FILES)
	@$(ENV_SET) verilator --lint-only --top-module $(MODULE) $(VERILATOR_FLAGS) -cc $(RTL_FILES) \
	 2>&1 | sed $(VERILATOR_COLOR)

.PHONY: hierarchy
hierarchy: $(SV_FILES)
	@$(ENV_SET) verilator -C --top-module $(MODULE) $(VERILATOR_FLAGS) -cc $(RTL_FILES) \
	 2>&1 | sed $(VERILATOR_COLOR)

.PHONY: clean
clean:
	@rm -rf .stamp.*
	@rm -rf $(OBJ_DIR)
	@rm -rf $(LOG_DIR)
	@rm -rf $(VCD_DIR)

.PHONY: makedir
makedir:
	@mkdir -p $(LOG_DIR)
	@mkdir -p $(VCD_DIR)
