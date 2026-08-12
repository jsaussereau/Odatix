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
RTL_DIR = rtl
OBJ_DIR = $(WORK_DIR)/obj
LOG_DIR = $(WORK_DIR)/log
VCD_DIR = $(WORK_DIR)/vcd
TB_DIR  = $(WORK_DIR)/tb

########################################################
# Simulation Parameters
########################################################

MODULE = cordic
TB_MODULE = tb_$(MODULE)
VCD_FILE = $(VCD_DIR)/$(MODULE).vcd
RESULT_FILE = $(WORK_DIR)/results.yml
EXECUTABLE = $(TB_MODULE)
PROGRESS_FILE = $(LOG_DIR)/progress.log
SIM_LOGFILE = $(LOG_DIR)/sim.log

########################################################
# Configuration
########################################################

# The testbench needs to know the parameters Odatix wrote in the RTL file, so
# that it can build its reference model. Odatix passes the value of each
# parameter domain of the architecture to the command in _settings.yml
# (${width} and ${iterations}), so nothing has to be read back from the source.
CFG_WIDTH ?=
CFG_ITERATIONS ?=

GHDL_GENERICS = -gWIDTH=$(CFG_WIDTH) -gITERATIONS=$(CFG_ITERATIONS)

########################################################
# Tools Commands
########################################################

GTKWAVE = gtkwave
GHDL = ghdl
GHDL_FLAGS = --ieee=synopsys --warn-no-vital-generic --workdir=$(OBJ_DIR)

# The testbench stops its own clock once it is done, so the simulation ends by
# itself and needs no stop time.
GHDL_SIM_OPT =

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
sim: check_config makedir $(VCD_FILE)

.PHONY: check_config
check_config:
	@test -n "$(CFG_WIDTH)" -a -n "$(CFG_ITERATIONS)" || { \
	  printf "Error: CFG_WIDTH and CFG_ITERATIONS must be set\n"; \
	  printf "       (Odatix passes them from the \"width\" and \"iterations\" parameter domains)\n"; \
	  exit 1; \
	}

.PHONY: view
view: $(VCD_FILE)
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "              View Waves              \n"
	@printf "######################################\n"
	@printf "$(_END)\n"
	@$(GTKWAVE) $(VCD_FILE) -a gtkwave_setup.gtkw

$(VCD_FILE): $(RTL_DIR)/* $(TB_DIR)/*
	@echo "progress: 1%" > $(PROGRESS_FILE)
	@printf "\n$(_BOLD)$(_CYAN)"
	@printf "######################################\n"
	@printf "              Simulating              \n"
	@printf "######################################\n"
	@printf "$(_END)\n"
	@printf "WIDTH = $(CFG_WIDTH), ITERATIONS = $(CFG_ITERATIONS)\n"
	@$(GHDL) -a $(GHDL_FLAGS) $(RTL_DIR)/*
	@echo "progress: 2%" > $(PROGRESS_FILE)
	@$(GHDL) -a $(GHDL_FLAGS) $(TB_DIR)/*
	@echo "progress: 3%" > $(PROGRESS_FILE)
	@$(GHDL) -e $(GHDL_FLAGS) -o $(EXECUTABLE) $(TB_MODULE)
	@echo "progress: 5%" > $(PROGRESS_FILE)
	@$(GHDL) -r $(GHDL_FLAGS) $(TB_MODULE) $(GHDL_GENERICS) --vcd=$(VCD_FILE) $(GHDL_SIM_OPT) \
	| tee $(SIM_LOGFILE)
	@echo "progress: 100%" > $(PROGRESS_FILE)

.PHONY: clean
clean:
	@rm -f $(EXECUTABLE) e~$(EXECUTABLE).o
	@rm -rf $(LOG_DIR)
	@rm -rf $(OBJ_DIR)
	@rm -rf $(VCD_DIR)
	@rm -f $(RESULT_FILE)

.PHONY: makedir
makedir:
	@mkdir -p $(LOG_DIR)
	@mkdir -p $(OBJ_DIR)
	@mkdir -p $(VCD_DIR)
