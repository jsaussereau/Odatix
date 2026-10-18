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

// An instance card follows its switch: its body unfolds and the card is
// highlighted while it is selected to run (same classes as the server renders).
window.dash_clientside.odatix_jobs.toggle_card = function(_scope, switch_value) {
    var enabled = Array.isArray(switch_value) ? switch_value.length > 0 : !!switch_value;
    return [
        "jobs-arch-body animated-section" + (enabled ? "" : " hide"),
        "jobs-arch-card" + (enabled ? " enabled" : ""),
    ];
};

// Filter the instance cards by name and, optionally, hide the ones that are not
// selected to run.
window.dash_clientside.odatix_jobs.filter_cards = function(search_text, filter_value, switch_values, section_ids) {
    var needle = (search_text || "").trim().toLowerCase();
    var only_enabled = (filter_value || []).indexOf("enabled") !== -1;
    var enabled = {};
    var ctx = window.dash_clientside.callback_context;
    var switch_ids = [];
    // The ids of the switches come with their values in the inputs list.
    (ctx && ctx.inputs_list && ctx.inputs_list[2] || []).forEach(function(item) {
        switch_ids.push(item.id);
    });
    (switch_values || []).forEach(function(value, index) {
        var sid = switch_ids[index];
        if (sid && sid.arch !== undefined) {
            enabled[sid.arch] = Array.isArray(value) ? value.length > 0 : !!value;
        }
    });
    return (section_ids || []).map(function(sid) {
        var arch = String((sid && sid.arch) || "");
        var visible = (!needle || arch.toLowerCase().indexOf(needle) !== -1)
            && (!only_enabled || enabled[arch] === true);
        return visible ? {} : {"display": "none"};
    });
};

// "Select all" / "Clear" over every instance switch.
window.dash_clientside.odatix_jobs.select_all = function(all_clicks, none_clicks, switch_values) {
    var ctx = window.dash_clientside.callback_context;
    var triggered = ctx && ctx.triggered && ctx.triggered.length ? ctx.triggered[0].prop_id : "";
    var values = switch_values || [];
    if (triggered.indexOf("jobs-select-all.") === 0) {
        return values.map(function() { return [true]; });
    }
    if (triggered.indexOf("jobs-select-none.") === 0) {
        return values.map(function() { return []; });
    }
    return window.dash_clientside.no_update;
};

// The same for an architecture card nested in a simulation (or place & route) card.
window.dash_clientside.odatix_jobs.toggle_nested_card = function(_scope, switch_value) {
    var enabled = Array.isArray(switch_value) ? switch_value.length > 0 : !!switch_value;
    return [
        "jobs-arch-body animated-section" + (enabled ? "" : " hide"),
        "jobs-arch-card nested" + (enabled ? " enabled" : ""),
    ];
};
