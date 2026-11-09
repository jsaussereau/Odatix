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

if {[catch {

    source scripts/settings.tcl

    set signature "<grey>\[elaborate_script.tcl\]<end>"

    # Sources read (analyze_script.tcl): the elaboration is what takes long.
    # analyze_script.tcl reports nothing itself, as synthesis steps source it too
    report_progress 30 $synth_statusfile

    synth_design -rtl -top ${top_level_module} {*}[odatix_vivado_hdl_options]

    report_progress 100 $synth_statusfile

} ]} {
    puts "$signature <bold><red>error: Vivado RTL analysis terminated with errors<end>"
    report_progress 100 $synth_statusfile
    exit -1
}