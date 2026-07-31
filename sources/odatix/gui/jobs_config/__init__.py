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

"""
Building blocks of the "Run jobs" page (odatix/gui/pages/jobs_config.py).

The page is split by concern:
    common        : page path, shared constants and small shared helpers
    prepare_state : the module-level state of a run (threads, log, status, ...)
    checks        : the check/prepare phases run in background threads
    run_popup     : rendering of the run plan popup
    arch_widgets  : the parameter-domain / preview widgets of an architecture
    pnr           : the place & route cards (built from the work tree)
    simulation    : the simulation cards (architectures nested in a simulation)
    context       : what differs between job types, resolved from the url
    settings_io   : reading the page state back into a settings dict
    settings_form : the "Job Settings" form
    callbacks_*   : the callbacks, grouped the same way
    layout        : the page layout
"""
