WORK_DIR := .
SCRIPT_DIR := ./scripts
LOG_DIR := ./log

analyze:
	@mkdir -p $(LOG_DIR)
	@echo "Running Verilator analysis..."
	@verilator --cc \
		-Irtl -y rtl \
		--top-module $$(grep "set top_level_module" $(SCRIPT_DIR)/settings.tcl | awk '{print $$3}') \
		rtl/$$(grep "set top_level_file" $(SCRIPT_DIR)/settings.tcl | awk '{print $$3}') \
		2>&1 | tee $(LOG_DIR)/analysis.log