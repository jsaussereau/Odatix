import os
import re

import odatix.lib.hard_settings as hard_settings

## define colors
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
RESET   = "\033[0m"

TOOL_NAMES = {
    "design_compiler": "SYNOPSYS DESIGN COMPILER",
    "genus": "CADENCE GENUS",
    "fusion_compiler": "SYNOPSYS FUSION COMPILER",
    "vivado": "XILINX VIVADO",
    "verilator": "VERILATOR",
}

ERROR_PRIORITY = [
    "Undeclared signal",
    "Module not found",
    "Include file not found",
    "RTL Elaboration failed",
    "synth_design failed",
    "Reference to undeclared variable",
    "VER-956",
    "VLOGPT-1",
    "VER-294",
    "VER-964",
    "%Error",
    "Instance name required for module instance",
    "unresolved references",
    "Could not find an HDL design",
    "Cannot find the design",
    "Parsing error",
]


def get_analysis_errors_and_warnings(log_file):
    """Classify errors and only structural RTL/hierarchy warnings as critical."""
    errors = []
    critical_warnings = []
    standard_warning_count = 0
    if not os.path.exists(log_file):
        return errors, critical_warnings, standard_warning_count

    genus_lookahead_lines_left = 0
    genus_error_pending = False

    # Known non-structural warnings: useful in the log, but they must not make
    # a completed RTL analysis WARNING.
    NON_CRITICAL_WARNING_CODES = {
        "PHYS-15",      # Genus physical technology information
        "TECH-026",     # Fusion Compiler technology-file attribute
        "AUTOREAD-105", # Fusion Compiler search-path adjustment
        "LINK-1806",
    }

    # Only specific structural/hierarchy problems are critical. Avoid broad
    # tokens such as "missing" or "cannot find", which cause false positives.
    CRITICAL_PATTERNS = [
        r"\bblack[\s-]?box(?:es)?\b",
        r"\bunresolved reference(?:s)?\b",
        r"\bunable to resolve reference\b",
        r"\bcannot resolve reference\b",
        r"\bunbound (?:instance|component)(?:s)?\b",
        r"\bcannot find file containing module\b",
        r"\bmodule ['\"]?[^'\"]+['\"]? (?:is )?not found\b",
        r"\bcannot find (?:the )?design ['\"]",
        r"\bcannot find (?:the )?module\b",
        r"\bmissing (?:hdl )?(?:module|entity|component|design)\b",
        r"\bundefined (?:module|entity|component)\b",
    ]

    def message_code(line):
        m = re.search(r"[\[(]([A-Za-z][A-Za-z0-9_-]*-\d+)[\])]", line)
        return m.group(1).upper() if m else None

    def is_summary_table_line(line):
        s = line.strip()
        return s.startswith("|") and s.endswith("|")

    def is_critical_warning(line):
        if message_code(line) in NON_CRITICAL_WARNING_CODES:
            return False
        return any(re.search(p, line, re.IGNORECASE) for p in CRITICAL_PATTERNS)

    def add_critical(line):
        line = line.strip()
        if line and line not in critical_warnings:
            critical_warnings.append(line)

    with open(log_file, "r", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue

            # Verilator errors
            if "%Error" in line_str:
                if "Exiting due to" in line_str:
                    continue
                if "Cannot find file containing module" in line_str:
                    m = re.search(r"module: '([^']+)'", line_str)
                    errors.append(f"Module not found: {m.group(1)}" if m else "Module not found")
                elif "Cannot find include file" in line_str:
                    m = re.search(r"include file: '([^']+)'", line_str)
                    errors.append(f"Include file not found: {m.group(1)}" if m else "Include file not found")
                elif "Can't find definition of variable" in line_str:
                    m = re.search(r"variable: '([^']+)'", line_str)
                    errors.append(f"Undeclared variable: {m.group(1)}" if m else "Reference to undeclared variable")
                else:
                    errors.append(re.sub(r"^%Error:[^:]+:[^:]+:\s*", "%Error: ", line_str))
                continue

            # Warnings from all supported tools.
            is_warning = (
                "%Warning" in line_str
                or re.search(r"\bwarning\b", line_str, re.IGNORECASE) is not None
                or any(x in line_str for x in ["(MW-", "(VLOGPT-", "(LINT-"])
            )
            if is_warning:
                # Genus/other tools may print a summary table repeating messages.
                if is_summary_table_line(line_str):
                    continue
                if is_critical_warning(line_str):
                    add_critical(line_str)
                else:
                    standard_warning_count += 1
                continue

            # Genus undeclared-variable lookahead.
            if genus_lookahead_lines_left > 0:
                m = re.search(r"Symbol '([^']+)'", line_str)
                if m:
                    errors.append(f"Undeclared variable: {m.group(1)}")
                    genus_lookahead_lines_left = 0
                    genus_error_pending = False
                else:
                    genus_lookahead_lines_left -= 1
                    if genus_lookahead_lines_left == 0 and genus_error_pending:
                        errors.append("Reference to undeclared variable")
                        genus_error_pending = False

            if "Reference to undeclared variable" in line_str:
                genus_lookahead_lines_left = 4
                genus_error_pending = True
                continue
            elif "VER-956" in line_str:
                m = re.search(r"The symbol '([^']+)' is not defined", line_str)
                errors.append(f"Undeclared variable: {m.group(1)}" if m else line_str)
            elif "VLOGPT-1" in line_str:
                errors.append(line_str)
            elif "Presto compilation terminated" in line_str:
                errors.append("Compilation failed")
            elif "Parsing error" in line_str:
                errors.append(line_str)
            elif "Instance name required for module instance" in line_str:
                errors.append("Missing instance name")
            elif "Could not find an HDL design" in line_str:
                errors.append("Could not find HDL design")
            elif "is not declared" in line_str:
                m = re.search(r"'([^']+)' is not declared", line_str)
                errors.append(f"Undeclared signal: {m.group(1)}" if m else "Undeclared signal")
            elif "module '" in line_str and "not found" in line_str:
                m = re.search(r"module '([^']+)' not found", line_str)
                errors.append(f"Module not found: {m.group(1)}" if m else "Module not found")
            elif "RTL Elaboration failed" in line_str:
                errors.append("RTL Elaboration failed")
            elif "synth_design failed" in line_str:
                errors.append("synth_design failed")
            elif (
                "unresolved references" in line_str
                or "Cannot find the design" in line_str
                or "Unable to resolve reference" in line_str
            ):
                # Dedicated hierarchy scanners collect these without duplication.
                continue
            elif line_str.startswith("Error"):
                errors.append(line_str)

    if genus_error_pending:
        errors.append("Reference to undeclared variable")

    return (
        list(dict.fromkeys(errors)),
        list(dict.fromkeys(critical_warnings)),
        standard_warning_count,
    )


def get_most_relevant_error(errors):
    for priority in ERROR_PRIORITY:
        match = next((err for err in errors if priority in err), None)
        if match:
            return match
    return errors[0] if errors else ""


def get_genus_unresolved_info(unresolved_file):
    unresolved_count = 0
    unresolved_instances = []

    if not os.path.exists(unresolved_file):
        return unresolved_count, unresolved_instances

    with open(unresolved_file, "r", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if line_str.startswith("hinst:"):
                raw_instance = line_str.replace("hinst:", "").strip()
                module_name = raw_instance.split("/")[-1] if "/" in raw_instance else raw_instance
                if "." in module_name:
                    module_name = module_name.split(".")[-1]
                
                formatted_msg = f"Unresolved: {module_name} (Missing Module)"
                if formatted_msg not in unresolved_instances:
                    unresolved_instances.append(formatted_msg)
            
            match = re.search(r"Total number of unresolved references.*:\s*(\d+)", line_str)
            if match:
                unresolved_count = int(match.group(1))

    return max(unresolved_count, len(unresolved_instances)), unresolved_instances


def get_dc_unresolved_info(log_file):
    unresolved_instances = []

    if not os.path.exists(log_file):
        return 0, []

    with open(log_file, "r", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            match = re.search(r"Cannot find the design '([^']+)'", line_str)
            if match:
                instance = match.group(1)
                msg = f"Unresolved: {instance} (Missing Module)"
                if msg not in unresolved_instances:
                    unresolved_instances.append(msg)
            else:
                match = re.search(r"Unable to resolve reference '([^']+)' in '([^']+)'", line_str)
                if match:
                    instance = match.group(1)
                    msg = f"Unresolved: {instance} (Missing Module)"
                    if msg not in unresolved_instances:
                        unresolved_instances.append(msg)
                else:
                    match = re.search(r"Design '([^']+)' has.*unresolved references", line_str)
                    if match:
                        instance = match.group(1)
                        msg = f"Unresolved: Hierarchy Link Issue ({instance})"
                        if msg not in unresolved_instances:
                            unresolved_instances.append(msg)

    return len(unresolved_instances), unresolved_instances


def is_analysis_complete(log_dir):
    """
    Return True if the analysis of this job reached its completion marker.

    A finished analysis writes "Done: 100%" (hard_settings.valid_status) to the
    synthesis status file at the very end of its flow. If that marker is missing
    (e.g. the monitor was quit before the job finished, or the process was
    killed), the analysis is considered incomplete and must not be reported as
    passed.
    """
    status_file = os.path.join(log_dir, hard_settings.synth_status_filename)
    if not os.path.isfile(status_file):
        return False
    try:
        with open(status_file, "r", errors="ignore") as f:
            content = f.read()
    except OSError:
        return False
    return hard_settings.valid_status in content


def analyze_log_dir(log_dir, tool, architecture):
    """
    Analyze a single job's log directory and return its result dict, or None if
    no analysis log is found there.

    ``log_dir`` is the directory that holds the analysis log (typically the job's
    "log" sub-directory). ``architecture`` is the display name for that job
    (usually "<architecture>/<configuration>"). Shared by the whole-directory
    summary (generate_analysis_summary) and the per-job export
    (odatix.components.export_analysis.export_single_analysis_job).
    """
    if not os.path.isdir(log_dir):
        return None

    log_file_name = next((f for f in os.listdir(log_dir) if f in ["analysis.log", "verilator.log"]), None)
    if not log_file_name:
        return None

    log_file = os.path.join(log_dir, log_file_name)

    base_dir = log_dir
    if os.path.basename(base_dir) == "log":
        base_dir = os.path.dirname(base_dir)

    unresolved_file = os.path.join(base_dir, "report", "unresolved.rep")

    errors, critical_log_warnings, standard_warning_count = get_analysis_errors_and_warnings(log_file)

    if tool == "design_compiler":
        unresolved_count, unresolved_instances = get_dc_unresolved_info(log_file)
    elif tool == "genus":
        unresolved_count, unresolved_instances = get_genus_unresolved_info(unresolved_file)
    else:
        unresolved_count, unresolved_instances = 0, []

    # Only structural/functional critical warnings affect the verdict.
    # Ordinary tool warnings remain available as metadata, but a completed
    # design with only ordinary warnings is PASSED.
    critical_warnings = unresolved_instances + [
        w for w in critical_log_warnings if w not in unresolved_instances
    ]
    critical_warning_count = len(critical_warnings)

    if errors:
        status = "FAILED"
        error_message = get_most_relevant_error(errors)
    elif not is_analysis_complete(log_dir):
        status = "INCOMPLETE"
        error_message = ""
    elif critical_warning_count > 0:
        status = "WARNING"
        error_message = ""
    else:
        status = "PASSED"
        error_message = ""

    return {
        "architecture": architecture,
        "tool": tool,
        "log_file": log_file,
        "status": status,
        "error": error_message,
        "errors": errors,
        # Keep the old key for compatibility with any exporter that already
        # consumes it, but it now contains critical warnings only.
        "blackbox_warnings": critical_warnings,
        "critical_warnings": critical_warnings,
        "standard_warning_count": standard_warning_count,
        "error_count": len(errors),
        "warning_count": critical_warning_count,
        "critical_warning_count": critical_warning_count,
    }


def generate_analysis_summary(root_dir, output_file, tool):
    results = []

    for root, _, files in os.walk(root_dir):
        log_file_name = next((f for f in files if f in ["analysis.log", "verilator.log"]), None)
        if not log_file_name:
            continue

        rel_path = os.path.relpath(root, root_dir)
        match_arch = re.search(r"([^/]+/[^/]+)(?:/log)?$", rel_path)
        architecture = match_arch.group(1) if match_arch else rel_path

        result = analyze_log_dir(root, tool, architecture)
        if result is not None:
            results.append(result)

    if not results:
        print(f"{YELLOW}⚠ No analysis logs found in the specified directory.{RESET}")
        return {
            "tool": tool, "total": 0, "passed": 0, "PASSED": 0,
            "warnings": 0, "WARNINGS": 0, "incomplete": 0, "INCOMPLETE": 0,
            "failed": 0, "FAILED": 0, "results": []
        }

    status_order = {"FAILED": 0, "INCOMPLETE": 1, "WARNING": 2, "PASSED": 3}
    results.sort(key=lambda x: (status_order[x["status"]], x["architecture"]))

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    warnings_cnt = sum(1 for r in results if r["status"] == "WARNING")
    incomplete = sum(1 for r in results if r["status"] == "INCOMPLETE")
    total_critical_warnings = sum(r.get("critical_warning_count", r["warning_count"]) for r in results)

    # Generate Output File Report
    with open(output_file, "w") as f:
        f.write("=========================================\n")
        f.write("         ANALYSIS SUMMARY\n")
        f.write("=========================================\n\n")
        f.write(f"Total: {total} | PASSED: {passed} | CRITICAL WARNINGS: {total_critical_warnings} | INCOMPLETE: {incomplete} | FAILED: {failed}\n\n")

        for result in results:
            if result["status"] == "PASSED":
                f.write(f"{result['architecture']}: ✓ PASSED\n")
            elif result["status"] == "WARNING":
                f.write(f"{result['architecture']}: ⚠ CRITICAL WARNING ({result['warning_count']} structural warning(s) detected)\n")
                criticals = result.get("critical_warnings", result.get("blackbox_warnings", []))
                for wrn in criticals[:3]:
                    f.write(f"    -> {wrn}\n")
                if len(criticals) > 3:
                    remaining = len(criticals) - 3
                    f.write(f"    -> {remaining} more critical warning(s); check the log file\n")
            elif result["status"] == "INCOMPLETE":
                f.write(f"{result['architecture']}: / INCOMPLETE (analysis did not finish)\n")
            else:
                f.write(f"{result['architecture']}: ✗ FAILED\n")
                f.write(f"    -> {result['error']}\n")

    # --- STREAMLINED SUMMARY PRESENTATION ---
    print(f"\n{CYAN}========================================={RESET}")
    print(f"{BOLD}{CYAN}         ANALYSIS SUMMARY{RESET}")
    print(f"{CYAN}========================================={RESET}")

    current_tool = results[0].get("tool")
    tool_name = TOOL_NAMES.get(current_tool, str(current_tool).upper())

    print(f"{CYAN}TOOL:{RESET} {BOLD}{BLUE}{tool_name}{RESET}\n")
    print(f"{BOLD}Total: {GREEN}✓ PASSED: {passed}{RESET} | {YELLOW}⚠ CRITICAL WARNING: {warnings_cnt}{RESET} | {MAGENTA}/ INCOMPLETE: {incomplete}{RESET} | {RED}✗ FAILED: {failed}{RESET}\n")

    for result in results:
        arch = result['architecture']
        log_path = result['log_file']

        if result["status"] == "PASSED":
            print(f"{GREEN}✓  {BOLD}{arch}{RESET}")

        elif result["status"] == "INCOMPLETE":
            print(f"{MAGENTA}/  {BOLD}{arch}{RESET}")
            print(f"   ├─ {MAGENTA}Analysis did not finish (interrupted before completion){RESET}")
            print(f"   └─ Log: For more info please check {MAGENTA}{log_path}{RESET}")

        elif result["status"] == "WARNING":
            criticals = result.get("critical_warnings", result.get("blackbox_warnings", []))
            print(
                f"{YELLOW}⚠  {BOLD}{arch}{RESET} "
                f"{YELLOW}({len(criticals)} structural critical warning(s)){RESET}"
            )

            for index, warning in enumerate(criticals[:3]):
                clean_warn = warning.replace("Warning: ", "").replace("WARNING: ", "").strip()
                branch = "└─" if index == len(criticals[:3]) - 1 and len(criticals) <= 3 else "├─"
                print(f"   {branch} {YELLOW}{clean_warn}{RESET}")

            if len(criticals) > 3:
                print(f"   ├─ {YELLOW}{len(criticals) - 3} more critical warning(s){RESET}")

            print(f"   └─ Log: For more info please check {MAGENTA}{log_path}{RESET}")
                
        else:
            print(f"{RED}✗  {BOLD}{arch}{RESET}")
            error_msg = result.get('error', 'Unknown Error')
            clean_err = error_msg.split("For more info")[0].strip()
            if clean_err.lower().startswith("error:"):
                clean_err = clean_err[6:].strip()
                
            print(f"   ├─ {RED}Error: {clean_err}{RESET}")
            print(f"   └─ Log: For more info please check {MAGENTA}{log_path}{RESET}")

    print(f"\nAnalysis written to: {output_file}\n")

    return {
        "tool": tool,
        "total": total,
        "passed": passed,
        "PASSED": passed,
        "warnings": warnings_cnt,
        "WARNINGS": warnings_cnt,
        "incomplete": incomplete,
        "INCOMPLETE": incomplete,
        "failed": failed,
        "FAILED": failed,
        "results": results
    }


if __name__ == "__main__":
    target_tool = "design_compiler" 
    
    generate_analysis_summary(
        root_dir="work/analysis/design_compiler",
        output_file="analysis_report.txt",
        tool=target_tool
    )
