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
SNAPSHOT="${TB_MODULE}_sim"

PROGRESS_FILE="${LOG_DIR}/progress.log"
RESULT_FILE="results.yml"
VCD_FILE="${VCD_DIR}/${MODULE}.vcd"
TRANSCRIPT_FILE="${LOG_DIR}/sim.log"

# Language standards
VHDL_STD="--2008"

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

rm -rf "${WORK_LIB}" xsim.dir "${SNAPSHOT}.wdb"

if [ "${#vhdl_sources[@]}" -gt 0 ]; then
  xvhdl ${VHDL_STD} -work "${WORK_LIB}" -log "${LOG_DIR}/xvhdl.log" "${vhdl_sources[@]}"
  xvhdl_status=$?
  cat "${LOG_DIR}/xvhdl.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
  [ ${xvhdl_status} -eq 0 ] || die "VHDL compilation failed, see ${TRANSCRIPT_FILE}"
fi
report_progress 2

if [ "${#vlog_sources[@]}" -gt 0 ]; then
  xvlog -sv -work "${WORK_LIB}" -log "${LOG_DIR}/xvlog.log" "${vlog_sources[@]}"
  xvlog_status=$?
  cat "${LOG_DIR}/xvlog.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
  [ ${xvlog_status} -eq 0 ] || die "Verilog compilation failed, see ${TRANSCRIPT_FILE}"
fi
report_progress 3

# The testbench itself is always SystemVerilog: it drives the design through
# its ports only, so it does not care which language the design is written in.
mapfile -t tb_sources < <(find "${TB_DIR}" -type f \( -name "*.v" -o -name "*.sv" -o -name "*.svh" \) 2>/dev/null | sort)
if [ "${#tb_sources[@]}" -eq 0 ]; then
  die "no testbench source found in '${TB_DIR}'"
fi

xvlog -sv -work "${WORK_LIB}" -log "${LOG_DIR}/xvlog_tb.log" "${tb_sources[@]}"
xvlog_tb_status=$?
cat "${LOG_DIR}/xvlog_tb.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
[ ${xvlog_tb_status} -eq 0 ] || die "testbench compilation failed, see ${TRANSCRIPT_FILE}"

report_progress 5

########################################################
# Elaboration
########################################################

xelab -L "${WORK_LIB}" \
  -debug typical \
  -generic_top "WIDTH=${cfg_width}" \
  -generic_top "ITERATIONS=${cfg_iterations}" \
  "${WORK_LIB}.${TB_MODULE}" \
  -s "${SNAPSHOT}" \
  -log "${LOG_DIR}/xelab.log"
xelab_status=$?
cat "${LOG_DIR}/xelab.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
[ ${xelab_status} -eq 0 ] || die "elaboration failed, see ${TRANSCRIPT_FILE}"

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

cat > "${LOG_DIR}/run.tcl" <<EOF
open_vcd ${VCD_FILE}
log_vcd /${TB_MODULE}/uut
run all
close_vcd
quit
EOF

xsim "${SNAPSHOT}" -tclbatch "${LOG_DIR}/run.tcl" -log "${LOG_DIR}/xsim.log"
sim_status=$?
cat "${LOG_DIR}/xsim.log" >> "${TRANSCRIPT_FILE}" 2>/dev/null
[ ${sim_status} -eq 0 ] || die "simulation failed, see ${TRANSCRIPT_FILE}"

########################################################
# Results
########################################################

if [ ! -f "${RESULT_FILE}" ]; then
  die "the testbench did not write '${RESULT_FILE}'"
fi

report_progress 100

exit 0
