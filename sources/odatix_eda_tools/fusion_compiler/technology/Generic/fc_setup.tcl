################################################################################
# Fusion Compiler technology setup (template)
################################################################################
#
# Copied into the job by Odatix (target_fusion_compiler.yml), then sourced by
# the Fusion Compiler scripts, which create the design library from it. It only
# sets variables:
#
#   TECH_FILE   technology file (.tf)
#   REF_LIBS    reference libraries (.ndm), as a list
#   TLUP_MAX    TLU+ file of the worst RC corner  \
#   TLUP_MIN    TLU+ file of the best RC corner    } physical synthesis and
#   TLUP_MAP    layer map of the TLU+ files        /  place and route only
#
# This is a template: replace every <...> with the files of your process
# design kit and standard cell library.

set LIB_DIR "<path/to/your/standard_cell_library>"
set PDK_DIR "<path/to/your/pdk>"

set TECH_FILE "$LIB_DIR/<technology_file>.tf"

# Frame and timing library, generated from the cell library with Library
# Manager: point this at where you generated it.
set REF_LIBS [list "$LIB_DIR/<frame_timing_library>.ndm"]

set TLUP_MAX "$PDK_DIR/<worst_rc_corner>.tluplus"
set TLUP_MIN "$PDK_DIR/<best_rc_corner>.tluplus"
set TLUP_MAP "$PDK_DIR/<tluplus_layer_map>.map"
