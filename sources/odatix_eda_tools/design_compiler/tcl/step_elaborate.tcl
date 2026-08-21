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

# Step "elaborate": elaboration, resolution of references and uniquification.
#
# The RTL has been analyzed by analyze_script.tcl in the same process. What this
# step leaves behind is the elaborated database the "synthesis" step reads back,
# so changing the target frequency only replays the compilation.

if {[catch {

    set signature "<grey>\[step_elaborate.tcl\]<end>"

    source scripts/settings.tcl
    source scripts/step_common.tcl

    report_progress 0 $synth_statusfile

    odatix_dc_elaborate $signature

    report_progress 60 $synth_statusfile

    puts "<bold>"
    puts "**************************************"
    puts "  Save Database for further loading"
    puts "**************************************"
    puts "<end>"

    odatix_write_ddc "${top_level_module}.ddc" $signature

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
