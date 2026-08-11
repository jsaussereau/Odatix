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

# Helpers shared by the steps of a stepped flow.
#
# The steps of a single run share one Vivado process (see the
# "*_session" keys of tool.yml): the design stays in memory from one step to the
# next, and nothing has to be written and read back. A run that stops, and a
# later one that resumes it, are two processes though — so each step still hands
# its design over through a design checkpoint, and a step starting a process
# opens the checkpoint the previous one left instead of starting from the RTL.

source scripts/settings.tcl

proc odatix_checkpoint_path {name} {
    global result_path
    return [file join $result_path $name]
}

proc odatix_write_checkpoint {name signature} {
    global result_path
    file mkdir $result_path
    set path [odatix_checkpoint_path $name]
    if {[catch {
        write_checkpoint -force $path
    } errmsg]} {
        puts "$signature <bold><red>error: failed writing checkpoint $name<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        exit -1
    }
    # What this process holds in memory, so that the next step of the same
    # session continues from it instead of reading the checkpoint back.
    set ::odatix_design_in_memory $name
    puts "$signature <cyan>wrote checkpoint $path<end>"
}

proc odatix_open_checkpoint {name signature previous_step} {
    if {[info exists ::odatix_design_in_memory] && $::odatix_design_in_memory eq $name} {
        puts "$signature <cyan>continuing from the \"$previous_step\" step, in the same session<end>"
        return
    }
    set path [odatix_checkpoint_path $name]
    if {![file exists $path]} {
        puts "$signature <bold><red>error: missing checkpoint $name<end>"
        puts "$signature <cyan>note: this step continues the \"$previous_step\" step, which has to run first<end>"
        exit -1
    }
    if {[catch {
        open_checkpoint $path
    } errmsg]} {
        puts "$signature <bold><red>error: failed opening checkpoint $name<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        exit -1
    }
    set ::odatix_design_in_memory $name
    puts "$signature <cyan>opened checkpoint $path<end>"
}

# Metrics are exported when the run ends, whichever step it ended on, so every
# step that produces meaningful numbers writes the reports the metrics are read
# from. The standard files always hold the latest numbers; a copy is kept per
# step so the post-synthesis estimates survive place & route.
proc odatix_write_reports {stage signature} {
    global report_path utilization_rep utilization_h_rep timing_rep power_rep

    if {[catch {
        report_utilization > $utilization_rep
        report_utilization -hierarchical > $utilization_h_rep
        report_timing > $timing_rep
        report_power > $power_rep
    } errmsg]} {
        puts "$signature <bold><red>error: failed report, skipping...<end>"
        puts -nonewline "$signature tool says -> $errmsg"
        return
    }

    set stage_path [file join $report_path $stage]
    file mkdir $stage_path
    foreach report [list $utilization_rep $utilization_h_rep $timing_rep $power_rep] {
        catch {file copy -force $report $stage_path}
    }
}

proc odatix_single_thread {signature} {
    global single_thread
    if {$single_thread != 1} {
        return
    }
    if {[catch {
        set_param synth.maxThreads 1
        set_param general.maxThreads 1
    } errmsg]} {
        puts "$signature <bold><red>error: failed setting vivado to single thread<end>"
        puts -nonewline "$signature tool says -> $errmsg"
    }
}
