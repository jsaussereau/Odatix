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

# Read back a parameter Odatix wrote in the RTL file. Both the VHDL generic
# form ("WIDTH : integer := 16") and the Verilog parameter form
# ("parameter WIDTH = 16") are accepted, so that the same script serves both
# versions of the design.
read_parameter() {
  local file="$1"
  local name="$2"
  local value

  # VHDL: WIDTH : integer := 16
  value=$(grep -oE "${name}[[:space:]]*:[[:space:]]*[a-zA-Z_]+[[:space:]]*:=[[:space:]]*[0-9]+" "${file}" \
    | head -n1 | grep -oE "[0-9]+$")
  if [ -n "${value}" ]; then
    echo "${value}"
    return
  fi

  # Verilog / SystemVerilog: parameter [type] WIDTH = 16
  value=$(grep -oE "parameter[[:space:]]+([a-zA-Z_][a-zA-Z0-9_]*[[:space:]]+)?${name}[[:space:]]*=[[:space:]]*[0-9]+" "${file}" \
    | head -n1 | grep -oE "[0-9]+$")
  echo "${value}"
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

# The top level file, used to read the configuration back
top_file=""
for f in "${vhdl_sources[@]}" "${vlog_sources[@]}"; do
  base=$(basename "${f}")
  if [ "${base%.*}" = "${MODULE}" ]; then
    top_file="${f}"
    break
  fi
done
if [ -z "${top_file}" ]; then
  die "could not find the top level file of '${MODULE}' in '${RTL_DIR}'"
fi

########################################################
# Configuration
########################################################

# The testbench needs to know the parameters Odatix wrote in the RTL file, so
# that it can build its reference model. They are read back from the source
# and forwarded to the elaboration of the testbench.
cfg_width=$(read_parameter "${top_file}" "WIDTH")
cfg_iterations=$(read_parameter "${top_file}" "ITERATIONS")

if [ -z "${cfg_width}" ] || [ -z "${cfg_iterations}" ]; then
  die "could not read WIDTH/ITERATIONS back from '${top_file}'"
fi

{
  echo ""
  echo "######################################"
  echo "              Compiling               "
  echo "######################################"
  echo ""
  echo "top level file = ${top_file}"
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
