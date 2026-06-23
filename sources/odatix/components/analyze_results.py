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
    "vivado": "XILINX VIVADO"
}

ERROR_PRIORITY = [
    "Undeclared signal",
    "Module not found",
    "RTL Elaboration failed",
    "synth_design failed",
    "Reference to undeclared variable",
    "VER-956",
    "VLOGPT-1",
    "VER-294",
    "VER-964",
    "Instance name required for module instance",
    "unresolved references",
    "Could not find an HDL design",
    "Cannot find the design",
    "Parsing error",

]


def get_analysis_errors(log_file):
    errors = []

    if not os.path.exists(log_file):
        return errors

    genus_lookahead_lines_left = 0
    genus_error_pending = False

    with open(log_file, "r", errors="ignore") as f:
        for line in f:
            line_str = line.strip()

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
                    errors.append(line_str) # Save full line context
                
            # Genus: VLOGPT-1
            elif "VLOGPT-1" in line_str:
                errors.append(line_str) # Save the complete detailed Genus string

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

            # Generic Error (Catches VER-294, VER-964, etc. cleanly)
            elif line_str.startswith("Error"):
                errors.append(line_str)

    if genus_error_pending:
        errors.append("Reference to undeclared variable")

    return list(dict.fromkeys(errors))


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
        if "analysis.log" not in files:
            continue
        
        log_file = os.path.join(root, "analysis.log")
        architecture = os.path.relpath(root, root_dir)
        analysis_dir = os.path.dirname(root)
        unresolved_file = os.path.join(analysis_dir, "report", "unresolved.rep")

        errors = get_analysis_errors(log_file)

        if tool == "design_compiler":
            unresolved_count, unresolved_instances = get_dc_unresolved_info(log_file)
        else:
            unresolved_count, unresolved_instances = get_genus_unresolved_info(unresolved_file)

        if errors:
            status = "FAILED"
            error_message = get_most_relevant_error(errors)
        elif unresolved_count > 0:
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
            "error_count": len(errors),
            "unresolved_references": unresolved_count,
            "instances": unresolved_instances
        })

    if not results:
        print(f"{YELLOW}⚠ No analysis logs found in the specified directory.{RESET}")
        return {}

    status_order = {"FAILED": 0, "WARNING": 1, "PASSED": 2}
    results.sort(key=lambda x: (status_order[x["status"]], x["architecture"]))

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASSED")
    warnings = sum(1 for r in results if r["status"] == "WARNING")
    failed = sum(1 for r in results if r["status"] == "FAILED")

    # Generate File Report
    with open(output_file, "w") as f:
        f.write("=========================================\n")
        f.write("         ANALYSIS SUMMARY\n")
        f.write("=========================================\n\n")
        f.write(f"Total: {total} | PASSED: {passed} | WARNING: {warnings} | FAILED: {failed}\n\n")

        for result in results:
            if result["status"] == "PASSED":
                f.write(f"{result['architecture']}: ✓ PASSED\n")
            elif result["status"] == "WARNING":
                f.write(f"{result['architecture']}: ⚠ WARNING ({result['unresolved_references']} unresolved references)\n")
                for inst in result["instances"]:
                    f.write(f"    -> {inst}\n")
            else:
                f.write(f"{result['architecture']}: ✗ FAILED\n")
                f.write(f"    -> {result['error']}\n")
                tool_label = TOOL_NAMES.get(result['tool'], "Tool").title()
                f.write(f"    -> {result['error_count']} {tool_label} error(s)\n")

    # Console Output
    print(f"\n{CYAN}========================================={RESET}")
    print(f"{BOLD}{CYAN}         ANALYSIS SUMMARY{RESET}")
    print(f"{CYAN}========================================={RESET}")

    current_tool = results[0].get("tool")
    tool_name = TOOL_NAMES.get(current_tool, str(current_tool).upper())

    print(f"{CYAN}TOOL:{RESET} {BOLD}{BLUE}{tool_name}{RESET}\n")
    print(f"{BOLD}Total: {GREEN}✓ PASSED: {passed}{RESET} | {YELLOW}⚠ WARNING: {warnings}{RESET} | {RED}✗ FAILED: {failed}{RESET}\n")

    for result in results:
        arch = result['architecture']
        log_p = result['log_file']

        if result["status"] == "PASSED":
            print(f"{arch}: {GREEN}✓ PASSED{RESET}")
        elif result["status"] == "WARNING":
            print(f"{arch}: {YELLOW}⚠ WARNING{RESET} ({result['unresolved_references']} unresolved references)")
            for inst in result["instances"]:
                print(f"    -> {BOLD}{YELLOW}{inst}{RESET}")
            print(f"Maybe your Design will not be synthesized correctly. For more info, check log: {BOLD}{MAGENTA}{log_p}{RESET}")
        else:
            print(f"{arch}: {RED}✗ FAILED{RESET}")
            
            error_msg = result['error']
            # Cleanly highlight tool specifics if string formatting matches
            if "Error:" in error_msg:
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
        "tool": tool,
        "total": total,
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "results": results
    }


if __name__ == "__main__":
    # Change target_tool to "genus" or "design_compiler" as needed for local testing
    target_tool = "design_compiler" 
    
    generate_analysis_summary(
        root_dir="work/analysis/design_compiler",
        output_file="analysis_report.txt",
        tool=target_tool
    )