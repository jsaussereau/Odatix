#################################################################################
# OPEN PHYSICAL DESIGN IN GENUS WITH ISPATIAL
#################################################################################

puts "=========================================="
puts "Opening physical design in Genus"
puts "=========================================="

#################################################################################
# LOAD SETTINGS
#################################################################################

if {![file exists scripts/settings.tcl]} {
    error "scripts/settings.tcl not found. Run this script from the synthesis result directory."
}

source scripts/settings.tcl

#################################################################################
# LOAD TECHNOLOGY / MMMC SETUP
#################################################################################

if {![file exists scripts/genus_setup.tcl]} {
    error "scripts/genus_setup.tcl not found."
}

puts "Loading Genus technology/MMMC setup..."

source scripts/genus_setup.tcl

#################################################################################
# FIND GENUS -> INNOVUS HANDOFF DIRECTORY
#################################################################################

set handoff_dirs [glob -nocomplain -type d ./genus2invs__*]

if {[llength $handoff_dirs] == 0} {
    error "No genus2invs__* directory found in [pwd]"
}

# If several directories exist, select the newest one
set handoff_dir [lindex $handoff_dirs 0]
set newest_time 0

foreach dir $handoff_dirs {

    set mtime [file mtime $dir]

    if {$mtime > $newest_time} {
        set newest_time $mtime
        set handoff_dir $dir
    }
}

set handoff_dir [file normalize $handoff_dir]

puts "Using handoff directory:"
puts "  $handoff_dir"

#################################################################################
# LOAD GENUS DATABASE
#################################################################################

set genus_db "$result_path/physical/genus_physical.db"

if {![file exists $genus_db]} {
    error "Genus database not found: $genus_db"
}

puts "Loading Genus database:"
puts "  $genus_db"

read_db $genus_db

#################################################################################
# LOAD FINAL iSPATIAL PLACEMENT
#################################################################################

set final_def "$handoff_dir/invs2genus.def.gz"

if {[file exists $final_def]} {

    puts "Loading final iSpatial placement:"
    puts "  $final_def"

    read_def $final_def

} else {

    puts "WARNING: invs2genus.def.gz not found."
    puts "Using placement stored in the Genus database."
}

#################################################################################
# DESIGN INFORMATION
#################################################################################

puts "=========================================="
puts "Design loaded"
puts "=========================================="

puts "Current design:"
puts "  [get_db designs .name]"

puts "Library domains:"
puts "  [get_db library_domains .name]"

set total_insts [llength [get_db insts]]

puts "Total instances:"
puts "  $total_insts"

#################################################################################
# PLACEMENT INFORMATION
#################################################################################

set placed_insts   0
set unplaced_insts 0
set fixed_insts    0

foreach status [get_db insts .place_status] {

    if {$status eq "placed"} {
        incr placed_insts
    }

    if {$status eq "unplaced"} {
        incr unplaced_insts
    }

    if {$status eq "fixed"} {
        incr fixed_insts
    }
}

puts "Placed instances:"
puts "  $placed_insts"

puts "Fixed instances:"
puts "  $fixed_insts"

puts "Unplaced instances:"
puts "  $unplaced_insts"

puts "=========================================="
puts "Genus physical design loaded successfully"
puts "=========================================="

#################################################################################
# GUI
#################################################################################

gui_show