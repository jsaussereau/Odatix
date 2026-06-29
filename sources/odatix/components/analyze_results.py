import os
import re

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
    warnings = []

    if not os.path.exists(log_file):
        return errors, warnings

    genus_lookahead_lines_left = 0
    genus_error_pending = False
    genus_warning_active = False

    # Keywords for dangerous warnings you care about (filtering out benign alerts)
    DANGEROUS_WARNING_KEYWORDS = ["black box", "blackbox", "unresolved", "cannot resolve", "cannot find", "modmissing", "missing"]

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
                if any(k in line_str.lower() for k in DANGEROUS_WARNING_KEYWORDS):
                    warnings.append(line_str)
                continue

            # --- CADENCE GENUS MULTI-LINE WARNING TRACKER ---
            if "Warning :" in line_str or "Warn :" in line_str:
                genus_warning_active = any(k in line_str.lower() for k in DANGEROUS_WARNING_KEYWORDS)
                if genus_warning_active:
                    if not any(x in line_str for x in ["LINK-1806", "fetching", "loading"]):
                        warnings.append(line_str)
                continue
            elif line_str.startswith(":") and genus_warning_active:
                # Capture subsequent indented contextual summary statements for Genus warnings
                warnings.append(line_str.lstrip(": ").strip())
                continue
            else:
                # Reset if context block snaps
                if not line_str.startswith(":"):
                    genus_warning_active = False

            # Standard General Warnings (DC, Vivado)
            if any(x in line_str.lower() for x in ["warning:", "(warning)"]):
                if any(k in line_str.lower() for k in DANGEROUS_WARNING_KEYWORDS):
                    warnings.append(line_str)
                continue

            # Process lookahead windows for Genus undeclared variables
            if genus_lookahead_lines_left > 0:
                if match := re.search(r"Symbol '([^']+)'", line_str):
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
                if match := re.search(r"The symbol '([^']+)' is not defined", line_str):
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
                if match := re.search(r"'([^']+)' is not declared", line_str):
                    errors.append(f"Undeclared signal: {match.group(1)}")
                else:
                    errors.append("Undeclared signal")

            # Vivado: module not found
            elif "module '" in line_str and "not found" in line_str:
                if match := re.search(r"module '([^']+)' not found", line_str):
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

    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def get_most_relevant_error(errors):
    for priority in ERROR_PRIORITY:
        if match := next((err for err in errors if priority in err), None):
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
                unresolved_instances.append(line_str.replace("hinst:", ""))
            if match := re.search(r"Total number of unresolved references.*:\s*(\d+)", line_str):
                unresolved_count = int(match.group(1))

    return unresolved_count, unresolved_instances


def get_dc_unresolved_info(log_file):
    unresolved_instances = []

    if not os.path.exists(log_file):
        return 0, []

    with open(log_file, "r", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if match := re.search(r"Unable to resolve reference '([^']+)' in '([^']+)'", line_str):
                instance = match.group(1)
                if instance not in unresolved_instances:
                    unresolved_instances.append(instance)
            elif match := re.search(r"Cannot find the design '([^']+)'", line_str):
                instance = match.group(1)
                if instance not in unresolved_instances:
                    unresolved_instances.append(f"{instance} (Missing Module)")
            elif match := re.search(r"Design '([^']+)' has.*unresolved references", line_str):
                instance = match.group(1)
                msg = f"Hierarchy Link Issue ({instance})"
                if msg not in unresolved_instances:
                    unresolved_instances.append(msg)

    return len(unresolved_instances), unresolved_instances


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

        # FIXED: Absolute directory calculations for Genus/DC structures
        if rel_path.endswith("log"):
            analysis_dir = os.path.dirname(os.path.dirname(root))
        else:
            analysis_dir = root
            
        unresolved_file = os.path.join(analysis_dir, "report", "unresolved.rep")

        errors, warnings = get_analysis_errors_and_warnings(log_file)

        if tool == "design_compiler":
            unresolved_count, unresolved_instances = get_dc_unresolved_info(log_file)
        elif tool == "genus":
            unresolved_count, unresolved_instances = get_genus_unresolved_info(unresolved_file)
        else:
            unresolved_count, unresolved_instances = 0, []

        if errors:
            status = "FAILED"
            error_message = get_most_relevant_error(errors)
        elif unresolved_count > 0 or warnings:
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
            "all_warnings": warnings,
            "error_count": len(errors),
            "unresolved_references": unresolved_count,
            "instances": unresolved_instances
        })

    if not results:
        print(f"{YELLOW}⚠ No analysis logs found in the specified directory.{RESET}")
        return {
            "tool": tool, "total": 0, "passed": 0, "PASSED": 0,
            "warnings": 0, "WARNINGS": 0, "failed": 0, "FAILED": 0, "results": []
        }

    status_order = {"FAILED": 0, "WARNING": 1, "PASSED": 2}
    results.sort(key=lambda x: (status_order[x["status"]], x["architecture"]))

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASSED")
    warnings_cnt = sum(1 for r in results if r["status"] == "WARNING")
    failed = sum(1 for r in results if r["status"] == "FAILED")

    # Generate Output File Report
    with open(output_file, "w") as f:
        f.write("=========================================\n")
        f.write("         ANALYSIS SUMMARY\n")
        f.write("=========================================\n\n")
        f.write(f"Total: {total} | PASSED: {passed} | WARNING: {warnings_cnt} | FAILED: {failed}\n\n")

        for result in results:
            if result["status"] == "PASSED":
                f.write(f"{result['architecture']}: ✓ PASSED\n")
            elif result["status"] == "WARNING":
                ref_msg = f"{result['unresolved_references']} unresolved references" if result['unresolved_references'] else "critical design warnings detected"
                f.write(f"{result['architecture']}: ⚠ WARNING ({ref_msg})\n")
                combined_warnings = [f"Unresolved Ref: {i}" for i in result["instances"]] + result["all_warnings"]
                for wrn in combined_warnings[:3]:
                    f.write(f"    -> {wrn}\n")
                if len(combined_warnings) > 3:
                    remaining = len(combined_warnings) - 3
                    f.write(f"    -> {remaining} more warning(s).... please check the log\n")
            else:
                f.write(f"{result['architecture']}: ✗ FAILED\n")
                f.write(f"    -> {result['error']}\n")
                tool_label = TOOL_NAMES.get(result['tool'], "Tool").title()
                f.write(f"    -> {result['error_count']} {tool_label} error(s)\n")

    # Console Output Execution
    print(f"\n{CYAN}========================================={RESET}")
    print(f"{BOLD}{CYAN}         ANALYSIS SUMMARY{RESET}")
    print(f"{CYAN}========================================={RESET}")

    current_tool = results[0].get("tool")
    tool_name = TOOL_NAMES.get(current_tool, str(current_tool).upper())

    print(f"{CYAN}TOOL:{RESET} {BOLD}{BLUE}{tool_name}{RESET}\n")
    print(f"{BOLD}Total: {GREEN}✓ PASSED: {passed}{RESET} | {YELLOW}⚠ WARNING: {warnings_cnt}{RESET} | {RED}✗ FAILED: {failed}{RESET}\n")

    for result in results:
        arch = result['architecture']
        log_p = result['log_file']

        if result["status"] == "PASSED":
            print(f"{arch}: {GREEN}✓ PASSED{RESET}")
        elif result["status"] == "WARNING":
            ref_msg = f"{result['unresolved_references']} unresolved references" if result['unresolved_references'] else "critical design warnings detected"
            print(f"{arch}: {YELLOW}⚠ WARNING{RESET} ({ref_msg})")
            combined_warnings = [f"Unresolved: {i}" for i in result["instances"]] + result["all_warnings"]
            for wrn in combined_warnings[:3]:
                print(f"    -> {YELLOW}{wrn}{RESET}")
            if len(combined_warnings) > 3:
                remaining = len(combined_warnings) - 3
                print(f"    -> {BOLD}{YELLOW}{remaining} more warning(s).... please check the log{RESET}")
            print(f"Maybe your Design will not be synthesized correctly. For more info, check log: {BOLD}{MAGENTA}{log_p}{RESET}")
        else:
            print(f"{arch}: {RED}✗ FAILED{RESET}")
            error_msg = result['error']
            if "Error:" in error_msg or "%Error" in error_msg:
                print(f"    -> {RED}{error_msg}{RESET}")
            elif ":" in error_msg:
                prefix, symbol = error_msg.split(":", 1)
                print(f"    -> {prefix}:{RED}{symbol}{RESET}")
            else:
                print(f"    -> {RED}{error_msg}{RESET}")
                
            tool_label = TOOL_NAMES.get(result['tool'], "Tool").title()
            print(f"    -> {result['error_count']} {tool_label} error(s)")
            print(f"For more info, check log: {BOLD}{MAGENTA}{log_p}{RESET}")

    print(f"\nAnalysis written to: {output_file}\n")

    return {
        "tool": tool, "total": total, "passed": passed, "PASSED": passed,
        "warnings": warnings_cnt, "WARNINGS": warnings_cnt, "failed": failed, "FAILED": failed,
        "results": results
    }


if __name__ == "__main__":
    target_tool = "genus" 
    generate_analysis_summary(
        root_dir="work/analysis/genus",
        output_file="analysis_report.txt",
        tool=target_tool
    )