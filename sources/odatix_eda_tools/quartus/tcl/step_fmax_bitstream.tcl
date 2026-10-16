# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#


# Step "bitstream" of an fmax search: implement at the frequency it found and
# write the programming file.
#
# A binary search leaves no implemented design behind -- its last iteration is
# whichever frequency it probed last, not the one it converged to -- so this step
# compiles the design once more. The constraints file is the one the search
# left, already set to the frequency it found, so nothing else has to be passed
# between the two.
#
# Note that "init_script.tcl" is deliberately not sourced here: it would reset
# those constraints to the settings file's target frequency.

if {[catch {

    set signature "<grey>\[step_fmax_bitstream.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/quartus_common.tcl

    set ::odatix_synth_depth "pnr"

    source scripts/analyze_script.tcl
    source scripts/synth_script.tcl

    # (synth_script.tcl sets its own)
    set signature "<grey>\[step_fmax_bitstream.tcl\]<end>"

    odatix_quartus_open $signature
    set succeeded [odatix_quartus_assemble $signature]
    odatix_quartus_close
    if {!$succeeded} {
        exit -1
    }

    report_progress 100 $synth_statusfile

} gblerrmsg ]} {
    puts "$signature <bold><red>error: unhandled tcl error, exiting<end>"
    puts "$signature <cyan>note: if you did not edit the tcl script, this should not append, please report this with the information bellow<end>"
    catch {
        puts "$signature <cyan>tcl error detail:<red>"
        puts "$gblerrmsg"
    }
    puts "<cyan>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<end>"
    exit -1
}
