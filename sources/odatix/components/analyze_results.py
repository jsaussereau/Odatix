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


ERROR_PRIORITY = [
    "Undeclared signal",
    "Module not found",
    "RTL Elaboration failed",
    "synth_design failed",
    "Reference to undeclared variable",
    "VER-956",
    "Parsing error",
    "Instance name required for module instance",
    "unresolved references",
    "Could not find an HDL design",
    "Cannot find the design",
]


def get_analysis_errorsrs(log_file):

    errors = []

    if not os.path.exists(log_file):
        return errors

    with open(log_file, "r", errors="ignore") as f:

        lines = f.readlines()

    i = 0

    while i < len(lines):

        line = lines[i].strip()

        #
        # Genus: Undeclared variable
        #
        if "Reference to undeclared variable" in line:

            symbol = ""

            for j in range(i + 1, min(i + 5, len(lines))):

                match = re.search(
                    r"Symbol '([^']+)'",
                    lines[j]
                )

                if match:

                    symbol = match.group(1)
                    break

            if symbol:

                errors.append(
                    f"Undeclared variable: {symbol}"
                )

            else:

                errors.append(
                    "Reference to undeclared variable"
                )

        #
        # DC: VER-956
        #
        elif "VER-956" in line:

            match = re.search(
                r"The symbol '([^']+)' is not defined",
                line
            )

            if match:

                errors.append(
                    f"Undeclared variable: {match.group(1)}"
                )

            else:

                errors.append(
                    "VER-956"
                )


        #
        # DC: Compilation failed
        #
        elif "Presto compilation terminated" in line:

            errors.append(
                "Compilation failed"
            )

        #
        # Parsing error
        #
        elif "Parsing error" in line:

            errors.append(
                "Parsing error"
            )

        #
        # Missing instance name
        #
        elif "Instance name required for module instance" in line:

            errors.append(
                "Missing instance name"
            )

        #
        # Missing HDL design
        #
        elif "Could not find an HDL design" in line:

            errors.append(
                "Could not find HDL design"
            )

        #
        # Vivado: undeclared signal
        #
        elif "is not declared" in line:

            match = re.search(
                r"'([^']+)' is not declared",
                line
            )

            if match:
                errors.append(
                    f"Undeclared signal: {match.group(1)}"
                )
            else:
                errors.append(
                    "Undeclared signal"
                )

        #
        # Vivado: module not found
        #
        elif "module '" in line and "not found" in line:

            match = re.search(
                r"module '([^']+)' not found",
                line
            )

            if match:
                errors.append(
                    f"Module not found: {match.group(1)}"
                )
            else:
                errors.append(
                    "Module not found"
                )

        #
        # Vivado: RTL elaboration failed
        #
        elif "RTL Elaboration failed" in line:

            errors.append(
                "RTL Elaboration failed"
            )

        #
        # Vivado: synth_design failed
        #
        elif "synth_design failed" in line:

            errors.append(
                "synth_design failed"
            )

        #
        # Generic Error
        #
        elif line.startswith("Error"):

            errors.append(
                line
            )

        i += 1

    #
    # Remove duplicates
    #
    unique_errors = []

    for error in errors:

        if error not in unique_errors:
            unique_errors.append(error)

    return unique_errors

    

def get_most_relevant_error(errors):

    for priority in ERROR_PRIORITY:

        for error in errors:

            if priority in error:
                return error

    if len(errors) > 0:
        return errors[0]

    return ""


def get_unresolved_info(unresolved_file):

    unresolved_count = 0
    unresolved_instances = []

    if not os.path.exists(unresolved_file):
        return unresolved_count, unresolved_instances

    with open(unresolved_file, "r", errors="ignore") as f:

        for line in f:

            line = line.strip()

            if line.startswith("hinst:"):

                unresolved_instances.append(
                    line.replace("hinst:", "")
                )

            match = re.search(
                r"Total number of unresolved references.*:\s*(\d+)",
                line
            )

            if match:
                unresolved_count = int(match.group(1))

    return unresolved_count, unresolved_instances

def get_dc_unresolved_info(log_file):

    unresolved_instances = []

    if not os.path.exists(log_file):
        return 0, []

    with open(log_file, "r", errors="ignore") as f:

        for line in f:

            match = re.search(
                r"Unable to resolve reference '([^']+)' in '([^']+)'",
                line
            )

            if match:

                instance = match.group(1)

                if instance not in unresolved_instances:
                    unresolved_instances.append(instance)

    unresolved_count = len(unresolved_instances)

    return unresolved_count, unresolved_instances


def generate_analysis_summary(root_dir, output_file, tool):

    results = []

    for root, dirs, files in os.walk(root_dir):

        #
        # Architecture folders contain genus.log
        #
        if "analysis.log" not in files:
            continue
        
        log_file = os.path.join(
            root,
            "analysis.log"
        )



        architecture = os.path.relpath(
            root,
            root_dir
        )


        unresolved_file = os.path.join(
            root,
            "report",
            "unresolved.rep"
        )
        errors = get_analysis_errorsrs(
            log_file
        )

        if tool == "design_compiler":
            unresolved_count, unresolved_instances = \
                get_dc_unresolved_info(
                    log_file
                )

        else:
            unresolved_count, unresolved_instances = \
                get_unresolved_info(
                    unresolved_file
                )

        if len(errors) > 0:
            status = "FAILED"
            error_message = get_most_relevant_error(
                errors
            )

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

    status_order = {
        "FAILED": 0,
        "WARNING": 1,
        "PASSED": 2
    }

    results.sort(
        key=lambda x: (
            status_order[x["status"]],
            x["architecture"]
        )
    )

    total = len(results)
    passed = sum(
        1 for r in results
        if r["status"] == "PASSED"
    )
    warnings = sum(
        1 for r in results
        if r["status"] == "WARNING"
    )
    failed = sum(
        1 for r in results
        if r["status"] == "FAILED"
    )

    with open(output_file, "w") as f:
        f.write(
            "=========================================\n"
        )
        f.write(
            "         ANALYSIS SUMMARY\n"
        )
        f.write(
            "=========================================\n\n"
        )

        f.write(
            f"Total: {total} | "
            f"PASSED: {passed} | "
            f"WARNING: {warnings} | "
            f"FAILED: {failed}\n\n"
        )

        for result in results:

            if result["status"] == "PASSED":
                f.write(
                    f"{result['architecture']}: PASSED\n"
                )

            elif result["status"] == "WARNING":
                f.write(
                    f"{result['architecture']}: WARNING "
                    f"({result['unresolved_references']} unresolved references)\n"
                )

                for inst in result["instances"]:
                    f.write(
                        f"    -> {inst}\n"
                    )

            else:
                f.write(
                    f"{result['architecture']}: FAILED\n"
                )
                f.write(
                    f"    -> {result['error']}\n"
                )


                if result["tool"] == "genus":
                    f.write(
                        f"    -> {result['error_count']} Genus error(s)"
                    )

                elif result["tool"] == "design_compiler":
                    f.write(
                        f"    -> {result['error_count']} Design Compiler error(s)"
                    )
                

        f.write("\n")

    print("")
    print(
        f"{CYAN}========================================={RESET}"
    )
    print(
        f"{BOLD}{CYAN}         ANALYSIS SUMMARY{RESET}"
    )
    print(
        f"{CYAN}========================================={RESET}"
    )

    tool_name = results[0].get("tool")

    if tool_name == "design_compiler":
        tool_name = "SYNOPSYS DESIGN COMPILER"

    elif tool_name == "genus":
        tool_name = "CADENCE GENUS"
    
    elif tool_name == "vivado":
        tool_name = "XILINX VIVADO"

    print(
        f"{CYAN}TOOL:{RESET} "
        f"{BOLD}{BLUE}{tool_name}{RESET}"
    )
    print("")

    print(
        f"{BOLD}Total: "
        f"{BOLD}{GREEN}PASSED: {passed}{RESET} | "
        f"{BOLD}{YELLOW}WARNING: {warnings}{RESET} | "
        f"{BOLD}{RED}FAILED: {failed}{RESET}"
    )

    print("")

    for result in results:
        if result["status"] == "PASSED":
            print(
                f"{result['architecture']}: {GREEN} PASSED{RESET}"
            )
        elif result["status"] == "WARNING":
            print(
                f"{result['architecture']}: {YELLOW} WARNING {RESET}"
                f"({result['unresolved_references']} unresolved references)"
            )
            for inst in result["instances"]:
                print(
                    f"    -> {inst}"
                )
            print( f"Maybe your Design will not be synthesized correctly, for more info, please check the {BOLD}{MAGENTA}.log{RESET} file: {BOLD}{result['log_file']}{RESET}")
        else:

            print(
                f"{result['architecture']}: {RED} FAILED{RESET}"
            )
            print(
                f"    -> {result['error']}"
            )
            if result.get("tool") == "genus":
                print(
                    f"    -> {result['error_count']} Genus error(s)"
                )
                print( f"For more info, please check the {BOLD}{MAGENTA}.log{RESET} file: {BOLD}{result['log_file']}{RESET}")

            elif result.get("tool") == "design_compiler":
                print( f"    -> {result['error_count']} Design Compiler error(s)" )
                print( f"For more info, please check the {BOLD}{MAGENTA}.log{RESET} file: {BOLD}{result['log_file']}{RESET}" )

            elif result.get("tool") == "vivado":
                print( f"    -> {result['error_count']} Vivado error(s)" )
                print( f"For more info, please check the {BOLD}{MAGENTA}.log{RESET} file: {BOLD}{result['log_file']}{RESET}" )



    print("")
    print(
        f"Analysis written to: {output_file}"
    )
    print("")

    return {
        "total": total,
        "passed": passed,
        "warnings": warnings,
        "failed": failed
    }


if __name__ == "__main__":

    generate_analysis_summary(
        root_dir="work/analysis/genus",
        output_file="analysis.yml",
        tool=tool
    )