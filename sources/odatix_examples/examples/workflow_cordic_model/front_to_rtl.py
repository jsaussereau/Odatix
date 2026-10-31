# **********************************************************************
#                                Odatix
# **********************************************************************
#
# The bridge between the two levels of the exploration: read the front an
# exploration of the CORDIC model found, keep the designs inside an accuracy
# window, and get them ready to run as RTL.
#
# For each of them, the configurations of the architecture that are missing
# are added (one file per value, holding nothing but the value), and the
# selection to give to "odatix sim" and "odatix synth" is printed. The
# architecture is the one described in the workshop, My_Cordic_sv by default.
#
#   python3 examples/workflow_cordic_model/front_to_rtl.py --snr-min 44 --snr-max 54
#   python3 examples/workflow_cordic_model/front_to_rtl.py --snr-min 44 --snr-max 54 --architecture My_Cordic_vhdl

import argparse
import os
import sys

import yaml

parser = argparse.ArgumentParser(description="Get the front of the CORDIC model ready to run as RTL")
parser.add_argument("--archive", default="results/dse/cordic_model_front.yml",
                    help="archive of the exploration of the model")
parser.add_argument("--snr-min", type=float, default=0.0, help="lowest SNR to keep, in dB")
parser.add_argument("--snr-max", type=float, default=1000.0, help="highest SNR to keep, in dB")
parser.add_argument("--workspace", default=".", help="the Odatix workspace")
parser.add_argument("--architecture", default="My_Cordic_sv",
                    help="architecture to add the configurations to (its domains must be named width and iterations)")
args = parser.parse_args()

archive_path = os.path.join(args.workspace, args.archive)
if not os.path.isfile(archive_path):
    sys.exit('No archive at "%s": run "odatix dse -p cordic_model_front" first.' % archive_path)
with open(archive_path) as f:
    archive = yaml.safe_load(f)

kept = [design for design in archive.get("front") or []
        if args.snr_min <= design["metrics"]["snr"] <= args.snr_max]
kept.sort(key=lambda design: design["metrics"]["adder_bits"])
if not kept:
    sys.exit("No design of the front between %g and %g dB." % (args.snr_min, args.snr_max))

arch_dir = os.path.join(args.workspace, "odatix_userconfig", "architectures", args.architecture)
if not os.path.isdir(arch_dir):
    sys.exit('No architecture at "%s": describe it first, or name another one with --architecture.' % arch_dir)
selections = []
print("%d designs of the front between %g and %g dB:" % (len(kept), args.snr_min, args.snr_max))
for design in kept:
    width = int(design["parameters"]["width"])
    iterations = int(design["parameters"]["iterations"])
    for domain, value in (("width", width), ("iterations", iterations)):
        path = os.path.join(arch_dir, domain, "%d.txt" % value)
        if not os.path.isfile(path):
            with open(path, "w") as f:
                f.write("%d\n" % value)
            print("  added %s" % os.path.relpath(path, args.workspace))
    print("  width %2d, %2d stages: %6.2f dB, %4d adder bits"
          % (width, iterations, design["metrics"]["snr"], design["metrics"]["adder_bits"]))
    selections.append('"%s + iterations/%d + width/%d"' % (args.architecture, iterations, width))

print("\nSelection, for odatix sim and odatix synth:")
print("  -a " + " ".join(selections))
