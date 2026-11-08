WORK_DIR := .
SCRIPT_DIR := ./scripts
LOG_DIR := ./log

# "pipefail" (bash): the exit code is the one of Verilator, not the one of tee.
SHELL := /bin/bash

# Verilator exits with 1 when it reports errors in the design: the analysis is
# done all the same. Any other failure (not installed, crashed) leaves it
# unfinished, without the completion marker.
analyze:
	@mkdir -p $(LOG_DIR)
	@echo "Running Verilator analysis..."
	@set -o pipefail; \
	top_file=rtl/$$(grep "set top_level_file" $(SCRIPT_DIR)/settings.tcl | awk '{print $$3}'); \
	packages=$$(grep -rlE --include='*.sv' --include='*.v' '^[[:space:]]*package[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*;' rtl | sort | grep -vxF "$$top_file"); \
	verilator --lint-only -Wall -Wno-fatal \
		-Irtl -y rtl \
		--top-module $$(grep "set top_level_module" $(SCRIPT_DIR)/settings.tcl | awk '{print $$3}') \
		$$packages "$$top_file" \
		2>&1 | tee $(LOG_DIR)/analysis.log; \
	status=$$?; \
	if [ $$status -le 1 ]; then echo "Done: 100%" > $(LOG_DIR)/synth_status.log; fi; \
	exit $$status
