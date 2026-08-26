#################################################################################
# OPEN GENUS PHYSICAL DESIGN IN INNOVUS
#################################################################################

puts "=========================================="
puts "Opening physical design in Innovus"
puts "=========================================="

#################################################################################
# FIND GENUS -> INNOVUS HANDOFF DIRECTORY
#################################################################################

set handoff_dirs [glob -nocomplain -type d ./genus2invs__*]

if {[llength $handoff_dirs] == 0} {
    error "No genus2invs__* directory found in [pwd]"
}

# Normally there should be only one directory
# If several exist, use the newest one
set handoff_dir [lindex $handoff_dirs 0]

if {[llength $handoff_dirs] > 1} {

    set newest_time 0

    foreach dir $handoff_dirs {

        set mtime [file mtime $dir]

        if {$mtime > $newest_time} {
            set newest_time $mtime
            set handoff_dir $dir
        }
    }
}

set handoff_dir [file normalize $handoff_dir]

puts "Using handoff directory:"
puts "  $handoff_dir"

#################################################################################
# GENUS -> INNOVUS SETUP
#################################################################################

set invs_setup "$handoff_dir/genus2invs.invs_setup.tcl"

if {![file exists $invs_setup]} {
    error "Innovus setup file not found: $invs_setup"
}

puts "Loading Innovus setup:"
puts "  $invs_setup"

source $invs_setup

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
    puts "Only the initial Genus -> Innovus state will be displayed."
}

#################################################################################
# INFORMATION
#################################################################################

set total_insts [llength [get_db insts]]

set placed_insts 0
set unplaced_insts 0

foreach status [get_db insts .place_status] {

    if {$status eq "placed"} {
        incr placed_insts
    }

    if {$status eq "unplaced"} {
        incr unplaced_insts
    }
}

puts "=========================================="
puts "Design loaded"
puts "=========================================="
puts "Total instances : $total_insts"
puts "Placed instances: $placed_insts"
puts "Unplaced        : $unplaced_insts"
puts "=========================================="

#################################################################################
# GUI
#################################################################################
gui_show 

gui_fit