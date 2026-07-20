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
    "vivado": "XILINX VIVADO",
    "verilator": "VERILATOR"
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
    errors = []
    critical_warnings = []
    standard_warning_count = 0

    if not os.path.exists(log_file):
        return errors, critical_warnings, standard_warning_count

    genus_lookahead_lines_left = 0
    genus_error_pending = False

    # Structural / Functional danger keywords
    BLACKBOX_KEYWORDS = ["black box", "blackbox", "unresolved", "cannot resolve", "cannot find", "modmissing", "missing"]

    with open(log_file, "r", errors="ignore") as f:
        for line in f:
            line_str = line.strip()

            # --- VERILATOR ENGINE ---
            if "%Error" in line_str:
                if "Exiting due to" in line_str:
                    continue
                if "Cannot find file containing module" in line_str:
                    if match := re.search(r"module: '([^']+)'", line_str):
                        errors.append(f"Module not found: {match.group(1)}")
                    else:
                        errors.append("Module not found")
                elif "Cannot find include file" in line_str:
                    if match := re.search(r"include file: '([^']+)'", line_str):
                        errors.append(f"Include file not found: {match.group(1)}")
                    else:
                        errors.append("Include file not found")
                elif "Can't find definition of variable" in line_str:
                    if match := re.search(r"variable: '([^']+)'", line_str):
                        errors.append(f"Undeclared variable: {match.group(1)}")
                    else:
                        errors.append("Reference to undeclared variable")
                else:
                    clean_err = re.sub(r"^%Error:[^:]+:[^:]+:\s*", "%Error: ", line_str)
                    errors.append(clean_err)
                continue
                
            elif "%Warning" in line_str:
                if any(k in line_str.lower() for k in BLACKBOX_KEYWORDS):
                    critical_warnings.append(line_str)
                else:
                    standard_warning_count += 1
                continue

            # --- BROAD ENGINE WARNING CATCHMENT ---
            is_warning = (
                any(line_str.lower().startswith(x) for x in ["warning:", "warn:", "(warning)", "critical warning:"]) or
                "warn" in line_str.lower() or 
                any(c in line_str for c in ["(MW-", "(VLOGPT-", "(LINT-"])
            )

            if is_warning:
                if not any(x in line_str for x in ["LINK-1806", "fetching", "loading"]):
                    if any(k in line_str.lower() for k in BLACKBOX_KEYWORDS):
                        critical_warnings.append(line_str)
                    else:
                        standard_warning_count += 1
                continue

            # Process lookahead windows for Genus undeclared variables
            if genus_lookahead_lines_left > 0:
                match = re.search(r"Symbol '([^']+)'", line_str)
                if match:
                    errors.append(f"Undeclared variable: {match.group(1)}")
                    genus_lookahead_lines_left = 0
                    genus_error_pending = False
                else:
                    genus_lookahead_lines_left -= 1
                    if genus_lookahead_lines_left == 0 and genus_error_pending:
                        errors.append("Reference to undeclared variable")
                        genus_error_pending = False

            # Genus: Undeclared variable trigger
            if "Reference to undeclared variable" in line_str:
                genus_lookahead_lines_left = 4
                genus_error_pending = True
                continue

            # DC: VER-956
            elif "VER-956" in line_str:
                match = re.search(r"The symbol '([^']+)' is not defined", line_str)
                if match:
                    errors.append(f"Undeclared variable: {match.group(1)}")
                else:
                    errors.append(line_str) 
                
            # Genus: VLOGPT-1
            elif "VLOGPT-1" in line_str:
                errors.append(line_str)

            # DC: Compilation failed
            elif "Presto compilation terminated" in line_str:
                errors.append("Compilation failed")

            # Parsing error
            elif "Parsing error" in line_str:
                errors.append(line_str)

            # Missing instance name
            elif "Instance name required for module instance" in line_str:
                errors.append("Missing instance name")

            # Missing HDL design
            elif "Could not find an HDL design" in line_str:
                errors.append("Could not find HDL design")

            # Vivado: undeclared signal
            elif "is not declared" in line_str:
                match = re.search(r"'([^']+)' is not declared", line_str)
                if match:
                    errors.append(f"Undeclared signal: {match.group(1)}")
                else:
                    errors.append("Undeclared signal")

            # Vivado: module not found
            elif "module '" in line_str and "not found" in line_str:
                match = re.search(r"module '([^']+)' not found", line_str)
                if match:
                    errors.append(f"Module not found: {match.group(1)}")
                else:
                    errors.append("Module not found")

            # Vivado: RTL elaboration failed
            elif "RTL Elaboration failed" in line_str:
                errors.append("RTL Elaboration failed")

            # Vivado: synth_design failed
            elif "synth_design failed" in line_str:
                errors.append("synth_design failed")

            # Intercept DC hierarchy notifications 
            elif "unresolved references" in line_str or "Cannot find the design" in line_str or "Unable to resolve reference" in line_str:
                continue

            # Generic Error
            elif line_str.startswith("Error"):
                errors.append(line_str)

    if genus_error_pending:
        errors.append("Reference to undeclared variable")

    return list(dict.fromkeys(errors)), list(dict.fromkeys(critical_warnings)), standard_warning_count

    
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
            
            if match := re.search(r"Total number of unresolved references.*:\s*(\d+)", line_str):
                unresolved_count = int(match.group(1))

    return max(unresolved_count, len(unresolved_instances)), unresolved_instances


def get_dc_unresolved_info(log_file):
    unresolved_instances = []

    if not os.path.exists(log_file):
        return 0, []

    with open(log_file, "r", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if match := re.search(r"Cannot find the design '([^']+)'", line_str):
                instance = match.group(1)
                msg = f"Unresolved: {instance} (Missing Module)"
                if msg not in unresolved_instances:
                    unresolved_instances.append(msg)
            elif match := re.search(r"Unable to resolve reference '([^']+)' in '([^']+)'", line_str):
                instance = match.group(1)
                msg = f"Unresolved: {instance} (Missing Module)"
                if msg not in unresolved_instances:
                    unresolved_instances.append(msg)
            elif match := re.search(r"Design '([^']+)' has.*unresolved references", line_str):
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


def generate_analysis_summary(root_dir, output_file, tool):
    results = []

    for root, _, files in os.walk(root_dir):
        log_file_name = next((f for f in files if f in ["analysis.log", "verilator.log"]), None)
        if not log_file_name:
            continue
        
        log_file = os.path.join(root, log_file_name)
        
        rel_path = os.path.relpath(root, root_dir)
        match_arch = re.search(r"([^/]+/[^/]+)(?:/log)?$", rel_path)
        architecture = match_arch.group(1) if match_arch else rel_path

        base_dir = root
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

        blackbox_warnings = unresolved_instances + [w for w in critical_log_warnings if w not in unresolved_instances]
        total_warn_count = len(blackbox_warnings) + standard_warning_count

        if errors:
            status = "FAILED"
            error_message = get_most_relevant_error(errors)
        elif not is_analysis_complete(root):
            # No error was logged, but the analysis never reached its completion
            # marker (interrupted / quit before the end): do not report it as
            # passed, its warnings/pass verdict cannot be trusted.
            status = "INCOMPLETE"
            error_message = ""
        elif total_warn_count > 0:
            status = "WARNING"
            error_message = ""
        else:
            status = "PASSED"
            error_message = ""

        results.append({
            "architecture": architecture,
            "tool": tool,
            "log_file": log_file,
            "status": status,
            "error": error_message,
            "errors": errors,
            "blackbox_warnings": blackbox_warnings,
            "standard_warning_count": standard_warning_count,
            "error_count": len(errors),
            "warning_count": total_warn_count
        })

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
    total_warnings_sum = sum(r["warning_count"] for r in results)

    # Generate Output File Report
    with open(output_file, "w") as f:
        f.write("=========================================\n")
        f.write("         ANALYSIS SUMMARY\n")
        f.write("=========================================\n\n")
        f.write(f"Total: {total} | PASSED: {passed} | TOTAL WARNINGS: {total_warnings_sum} | INCOMPLETE: {incomplete} | FAILED: {failed}\n\n")

        for result in results:
            if result["status"] == "PASSED":
                f.write(f"{result['architecture']}: ✓ PASSED\n")
            elif result["status"] == "WARNING":
                f.write(f"{result['architecture']}: ⚠ WARNING ({result['warning_count']} warning(s) detected)\n")
                if result["blackbox_warnings"]:
                    for wrn in result["blackbox_warnings"][:3]:
                        f.write(f"    -> {wrn}\n")
                    if len(result["blackbox_warnings"]) > 3:
                        remaining = len(result["blackbox_warnings"]) - 3
                        f.write(f"    -> {remaining} more critical warning(s).... please check the log file\n")
                if result["standard_warning_count"] > 0:
                    f.write(f"    -> Info: {result['standard_warning_count']} standard warning(s) masked. Check log file for layout metrics.\n")
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
    print(f"{BOLD}Total: {GREEN}✓ PASSED: {passed}{RESET} | {YELLOW}⚠ WARNING: {warnings_cnt}{RESET} | {MAGENTA}/ INCOMPLETE: {incomplete}{RESET} | {RED}✗ FAILED: {failed}{RESET}\n")

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
            print(f"{YELLOW}⚠  {BOLD}{arch}{RESET} {YELLOW}({result.get('warning_count', 0)} warnings){RESET}")
            bbs = result.get("blackbox_warnings", [])
            if bbs:
                clean_warn = bbs[0].replace("Warning: ", "").replace("WARNING: ", "").strip()
                print(f"   ├─ {YELLOW}Primary issue: {clean_warn}{RESET}")
            elif result.get("standard_warning_count", 0) > 0:
                print(f"   └─ {YELLOW}INFO: {result['standard_warning_count']} standard warning(s) logged.{RESET}")
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
