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
RTL_DIR = ../../examples/counter_vhdl
OBJ_DIR = $(WORK_DIR)/obj
LOG_DIR = $(WORK_DIR)/log
VCD_DIR = $(WORK_DIR)/vcd
TB_DIR  = $(WORK_DIR)/tb

########################################################
# Simulation Parameters
########################################################

MODULE = counter
TB_MODULE = tb_$(MODULE)
VCD_FILE = $(VCD_DIR)/$(MODULE).vcd
EXECUTABLE = $(MODULE)
TMP_EXECUTABLE = $(MODULE)
PROGRESS_FILE = $(LOG_DIR)/progress.log

########################################################
# Tools Commands
########################################################

GTKWAVE = gtkwave
GHDL = ghdl
GHDL_FLAGS  = --ieee=synopsys --warn-no-vital-generic --workdir=$(OBJ_DIR) 

# Simulation break condition
#GHDL_SIM_OPT = --assert-level=error
STOP_TIME = 500ns
GHDL_SIM_OPT = --stop-time=$(STOP_TIME)

########################################################
# Text formatting
########################################################

_END     =\033[0m
_BOLD    =\033[1m
_CYAN    =\033[36m

########################################################
# Rules
########################################################

.PHONY: help
help:
	@printf "SIMULATION\n"
	@printf "\t$(_BOLD)make sim$(_END): run VHDL simulation\n"
	@printf "\t$(_BOLD)make view$(_END): view simulation waveform\n"
	@printf "OTHERS\n"
	@printf "\t$(_BOLD)make clean$(_END): clean generated files\n"
	@printf "\t$(_BOLD)make help$(_END): display a list of useful commands\n"

.PHONY: sim
sim: makedir $(VCD_FILE)

.PHONY: view
view: $(VCD_FILE)
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "              View Waves              \n"
	@printf "######################################\n"
	@printf "$(_END)\n"
	@$(GTKWAVE) $(VCD_FILE) -a gtkwave_setup.gtkw

$(VCD_FILE): $(RTL_DIR)/* $(TB_DIR)/*
	@echo "progress: 5%" > $(PROGRESS_FILE)
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "              Simulating              \n"
	@printf "######################################\n"
	@printf "$(_END)\n"
	@$(GHDL) -a $(GHDL_FLAGS) $(RTL_DIR)/*
	@echo "progress: 25%" > $(PROGRESS_FILE)
	@$(GHDL) -a $(GHDL_FLAGS) $(TB_DIR)/*
	@echo "progress: 50%" > $(PROGRESS_FILE)
	@$(GHDL) -e $(GHDL_FLAGS) -o $(EXECUTABLE) $(TB_MODULE)
	@echo "progress: 75%" > $(PROGRESS_FILE)
	@$(GHDL) -r $(EXECUTABLE) --vcd=$(VCD_FILE) $(GHDL_SIM_OPT) | tee $(LOG_DIR)/sim.log
	@echo "progress: 100%" > $(PROGRESS_FILE)

.PHONY: clean
clean:
	@rm -f $(EXECUTABLE) e~$(EXECUTABLE).o
	@rm -rf $(LOG_DIR)
	@rm -rf $(OBJ_DIR)
	@rm -rf $(VCD_DIR)

.PHONY: makedir
makedir:
	@mkdir -p $(LOG_DIR)
	@mkdir -p $(OBJ_DIR)
	@mkdir -p $(VCD_DIR)
