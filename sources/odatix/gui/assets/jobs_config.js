/**********************************************************************\
*                                Odatix                                *
************************************************************************
*
* Copyright (C) 2022 Jonathan Saussereau
*
* This file is part of Odatix.
* Odatix is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* Odatix is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with Odatix. If not, see <https://www.gnu.org/licenses/>.
*
*/

/*
 * Client-side behaviour of the job selection page (odatix.gui.jobs_config).
 */

window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.odatix_jobs = window.dash_clientside.odatix_jobs || {};

window.dash_clientside.odatix_jobs.skip_unsaved_guard = function(n_clicks) {
    if (n_clicks) {
        window.__odatixSkipUnsavedGuard = true;
    }
    return "";
};

window.dash_clientside.odatix_jobs.restore_unsaved_guard = function(run_status) {
    var status = run_status && run_status.status;
    if (status === "error" || status === "canceled") {
        window.__odatixSkipUnsavedGuard = false;
    }
    return "";
};
