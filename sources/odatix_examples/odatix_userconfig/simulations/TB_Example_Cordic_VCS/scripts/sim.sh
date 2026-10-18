#!/usr/bin/env bash

set -uo pipefail

########################################################
# Parameters
########################################################

MODULE="cordic"
TB_MODULE="tb_${MODULE}"

RTL_DIR="rtl"
TB_DIR="tb"
LOG_DIR="log"
VCD_DIR="vcd"
WORK_LIB="worklib"

PROGRESS_FILE="${LOG_DIR}/progress.log"
RESULT_FILE="results.yml"
VCD_FILE="${VCD_DIR}/${MODULE}.vcd"
TRANSCRIPT_FILE="${LOG_DIR}/sim.log"
SIMV="./simv"

# Language standards
VHDL_STD="-2008"

########################################################
# Helpers
########################################################

report_progress() {
  echo "progress: $1%" > "${PROGRESS_FILE}"
}

die() {
  echo "Error: $1"
  exit 1
}

########################################################
# Setup
########################################################

mkdir -p "${LOG_DIR}" "${VCD_DIR}"
rm -f "${TRANSCRIPT_FILE}"
rm -f "${RESULT_FILE}"

report_progress 1

########################################################
# Source files
########################################################

mapfile -t vhdl_sources < <(find "${RTL_DIR}" -type f \( -name "*.vhd" -o -name "*.vhdl" \) 2>/dev/null | sort)
mapfile -t vlog_sources < <(find "${RTL_DIR}" -type f \( -name "*.v" -o -name "*.sv" -o -name "*.svh" \) 2>/dev/null | sort)

if [ "${#vhdl_sources[@]}" -eq 0 ] && [ "${#vlog_sources[@]}" -eq 0 ]; then
  die "no source file found in '${RTL_DIR}'"
fi

########################################################
# Configuration
########################################################

# The testbench needs to know the parameters Odatix wrote in the RTL file, so
# that it can build its reference model. Odatix substitutes the value of each
# parameter domain of the architecture in the command of _settings.yml
# (${width} and ${iterations}), which passes them here as environment
# variables, so nothing has to be read back from the source.
cfg_width="${CFG_WIDTH:-}"
cfg_iterations="${CFG_ITERATIONS:-}"

if [ -z "${cfg_width}" ] || [ -z "${cfg_iterations}" ]; then
  die "CFG_WIDTH and CFG_ITERATIONS must be set (Odatix passes them from the \"width\" and \"iterations\" parameter domains)"
fi

{
  echo ""
  echo "######################################"
  echo "              Compiling               "
  echo "######################################"
  echo ""
  echo "WIDTH = ${cfg_width}, ITERATIONS = ${cfg_iterations}"
} | tee -a "${TRANSCRIPT_FILE}"

########################################################
# Compilation
########################################################

rm -rf "${WORK_LIB}" csrc simv simv.daidir AN.DB

if [ "${#vhdl_sources[@]}" -gt 0 ]; then
  vhdlan ${VHDL_STD} -work "${WORK_LIB}" -l "${LOG_DIR}/vhdlan.log" "${vhdl_sources[@]}"
  vhdlan_status=$?
  cat "${LOG_DIR}/vhdlan.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
  [ ${vhdlan_status} -eq 0 ] || die "VHDL compilation failed, see ${TRANSCRIPT_FILE}"
fi
report_progress 2

if [ "${#vlog_sources[@]}" -gt 0 ]; then
  vlogan -sverilog -work "${WORK_LIB}" -l "${LOG_DIR}/vlogan.log" "${vlog_sources[@]}"
  vlogan_status=$?
  cat "${LOG_DIR}/vlogan.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
  [ ${vlogan_status} -eq 0 ] || die "Verilog compilation failed, see ${TRANSCRIPT_FILE}"
fi
report_progress 3

# The testbench itself is always SystemVerilog: it drives the design through
# its ports only, so it does not care which language the design is written in.
mapfile -t tb_sources < <(find "${TB_DIR}" -type f \( -name "*.v" -o -name "*.sv" -o -name "*.svh" \) 2>/dev/null | sort)
if [ "${#tb_sources[@]}" -eq 0 ]; then
  die "no testbench source found in '${TB_DIR}'"
fi

vlogan -sverilog -work "${WORK_LIB}" -l "${LOG_DIR}/vlogan_tb.log" "${tb_sources[@]}"
vlogan_tb_status=$?
cat "${LOG_DIR}/vlogan_tb.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
[ ${vlogan_tb_status} -eq 0 ] || die "testbench compilation failed, see ${TRANSCRIPT_FILE}"

report_progress 5

########################################################
# Elaboration
########################################################

vcs -full64 -sverilog -work "${WORK_LIB}" \
  -pvalue+${TB_MODULE}.WIDTH=${cfg_width} \
  -pvalue+${TB_MODULE}.ITERATIONS=${cfg_iterations} \
  -debug_access+all \
  -l "${LOG_DIR}/vcs_elab.log" \
  "${WORK_LIB}.${TB_MODULE}" -o simv
vcs_status=$?
cat "${LOG_DIR}/vcs_elab.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
[ ${vcs_status} -eq 0 ] || die "elaboration failed, see ${TRANSCRIPT_FILE}"

########################################################
# Simulation
########################################################

{
  echo ""
  echo "######################################"
  echo "              Simulating              "
  echo "######################################"
  echo ""
} | tee -a "${TRANSCRIPT_FILE}"

cat > "${LOG_DIR}/dump.tcl" <<EOF
dump -file ${VCD_FILE} -type VCD
dump -add /${TB_MODULE}/uut/* -depth 0
run
dump -closefile
quit
EOF

${SIMV} -ucli -do "${LOG_DIR}/dump.tcl" -l "${LOG_DIR}/simv.log" +vcs+finish
sim_status=$?
cat "${LOG_DIR}/simv.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
[ ${sim_status} -eq 0 ] || die "simulation failed, see ${TRANSCRIPT_FILE}"

########################################################
# Results
########################################################

if [ ! -f "${RESULT_FILE}" ]; then
  die "the testbench did not write '${RESULT_FILE}'"
fi

report_progress 100

exit 0
