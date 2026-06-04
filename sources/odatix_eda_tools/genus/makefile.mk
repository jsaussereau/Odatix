# **********************************************************************

# Odatix

# **********************************************************************

########################################################
# Paths
########################################################

WORK_DIR                = ./work
SCRIPT_DIR              = ./scripts
LOG_DIR                 = ./log

########################################################
# Files
########################################################

INIT_SCRIPT             = init_script.tcl
ANALYZE_SCRIPT          = analyze_script.tcl
SYNTH_SCRIPT            = synth_script.tcl
SYNTH_FREQ_SCRIPT       = find_fmax.tcl

########################################################

# Tool specific

########################################################

GENUS                   = /softs/cadence/genus/21.19-s055_1/bin/genus

########################################################

# Text formatting

########################################################

_BOLD                   =\x1b[1m
_END                    =\x1b[0m
_RED                    =\x1b[31m
_GREEN                  =\x1b[32m
_YELLOW                 =\x1b[33m
_CYAN                   =\x1b[36m
_GREY                   =\x1b[90m

GENUS_COLOR = "s/Error/$(_RED)$(_BOLD)Error$(_END)/;s/Warning/$(_YELLOW)Warning$(_END)/;s//$(_GREEN)/;s//$(_RED)/;s//$(_CYAN)/;s//$(_GREY)/;s//$(_BOLD)/;s//$(_END)/g"

########################################################

# Rules

########################################################


# $(GENUS) -batch -files $(SCRIPT_DIR)/$(SYNTH_FREQ_SCRIPT) = $(GENUS) -batch -execute "source $(SCRIPT_DIR)/$(SYNTH_FREQ_SCRIPT); exit" 

.PHONY: synth_fmax
synth_fmax: logdir
	@cd $(WORK_DIR); \
	$(GENUS) -batch -execute "source $(SCRIPT_DIR)/$(SYNTH_FREQ_SCRIPT); exit"  \
	|  tee $(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log \
	|  sed $(GENUS_COLOR); \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	echo "result logged to "$(LOG_DIR)/$(SYNTH_FREQ_SCRIPT).log""; \
	exit $$EXIT_CODE

#.PHONY: synth
#synth: logdir
#	@cd $(WORK_DIR); 
#	$(GENUS) -batch -files $(SCRIPT_DIR)/$(RUN_SCRIPT) 
#	| tee $(LOG_DIR)/$(RUN_SCRIPT).log 
#	| sed $(GENUS_COLOR); 
#	EXIT_CODE=$${PIPESTATUS[0]}; 
#	echo "result logged to "$(LOG_DIR)/$(RUN_SCRIPT).log""; 
#	exit $$EXIT_CODE


.PHONY: synth
synth: logdir
	@cd $(WORK_DIR); \
	$(GENUS) -batch -execute "source $(SCRIPT_DIR)/$(INIT_SCRIPT); source $(SCRIPT_DIR)/$(ANALYZE_SCRIPT); source $(SCRIPT_DIR)/$(SYNTH_SCRIPT); exit" \
	| tee $(LOG_DIR)/$(SYNTH_SCRIPT).log \
	| sed $(GENUS_COLOR); \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	echo "result logged to "$(LOG_DIR)/$(SYNTH_SCRIPT).log"" \
	exit $$EXIT_CODE 


.PHONY: analyse
analyse: logdir
	@cd $(WORK_DIR); \
	$(GENUS) -batch -execute "source $(SCRIPT_DIR)/$(INIT_SCRIPT); source $(SCRIPT_DIR)/$(ANALYZE_SCRIPT); exit" \
	| tee $(LOG_DIR)/$(ANALYZE_SCRIPT).log \
	| sed $(GENUS_COLOR); \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	echo "result logged to "$(LOG_DIR)/$(ANALYZE_SCRIPT).log"" \
	exit $$EXIT_CODE 

.PHONY: test_tool
test_tool:
#	$(GENUS) -batch -execute "exit"
	$(GENUS) -version

.PHONY: logdir
logdir:
	@mkdir -p $(LOG_DIR)