#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#


source scripts/settings.tcl

set signature "<grey>\[synth_script.tcl\]<end>"

# report_progress 0 $synth_statusfile

set chan [open "|/bin/sh -c \"/openlane/flow.tcl -tag asterism -overwrite\"" r]
while {[gets $chan line] >= 0} {
    puts $line
}
close $chan

# report_progress 98 $synth_statusfile
