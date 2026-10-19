WORK_DIR := .
SCRIPT_DIR := ./scripts
LOG_DIR := ./log

# "pipefail" (bash): the exit code is the one of iverilog, not the one of tee.
SHELL := /bin/bash

# iverilog has no lint-only mode: "-t null" elaborates the design and generates
# nothing, which is the same work without the output file.
#
# It exits with the number of errors it found in the design: the analysis is
# done all the same. Only a failure of its own leaves it unfinished, without the
# completion marker: 126 and 127 are what a shell says of a command it cannot
# run, and 128 and above a signal.
analyze:
	@mkdir -p $(LOG_DIR)
	@echo "Running Icarus Verilog analysis..."
	@set -o pipefail; \
	iverilog -g2012 -Wall -t null \
		-I rtl -y rtl -Y .sv -Y .svh \
		-s $$(grep "set top_level_module" $(SCRIPT_DIR)/settings.tcl | awk '{print $$3}') \
		rtl/$$(grep "set top_level_file" $(SCRIPT_DIR)/settings.tcl | awk '{print $$3}') \
		2>&1 | tee $(LOG_DIR)/analysis.log; \
	status=$$?; \
	if [ $$status -lt 126 ]; then echo "Done: 100%" > $(LOG_DIR)/synth_status.log; fi; \
	exit $$status
