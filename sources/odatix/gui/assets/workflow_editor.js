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
 * Client-side behaviour of the workflow editor
 * (odatix.gui.pages.workflow_editor). Everything here answers keystrokes, so
 * none of it is worth a server round-trip: on a workflow of forty tasks, the
 * form weighs over a hundred kilobytes.
 */

window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.odatix_workflow_editor = window.dash_clientside.odatix_workflow_editor || {};

(function() {
    const ns = window.dash_clientside.odatix_workflow_editor;

    const CLEAN = ["color-button disabled icon-button tooltip delay bottom small", "Nothing to save"];
    const DIRTY = ["color-button warning icon-button tooltip bottom small", "Unsaved changes!"];
    const SAVING = ["color-button disabled icon-button tooltip bottom small odx-saving", "Saving..."];

    function error(message) {
        return ["color-button error-status icon-button tooltip bottom", message];
    }

    // A field as text: Dash hands back null for an empty number input, a
    // number once it has been typed into, a list for a switch.
    function normalize(value) {
        if (value === null || value === undefined) {
            return "";
        }
        if (Array.isArray(value)) {
            return JSON.stringify(value.map(normalize));
        }
        return String(value).trim();
    }

    // Every field of the form, by component id and property: a card added,
    // deleted or renamed shows as a field appearing or disappearing.
    function formValues(context, skip) {
        const values = {};
        function add(entry) {
            if (!entry || !entry.id) {
                return;
            }
            const key = (typeof entry.id === "string" ? entry.id : JSON.stringify(entry.id)) + "." + entry.property;
            if (skip.indexOf(entry.id) >= 0) {
                return;
            }
            values[key] = normalize(entry.value);
        }
        (context.inputs_list || []).concat(context.states_list || []).forEach(function(entry) {
            if (Array.isArray(entry)) {
                entry.forEach(add);
            } else {
                add(entry);
            }
        });
        return values;
    }

    function sameValues(a, b) {
        const keysA = Object.keys(a);
        if (keysA.length !== Object.keys(b).length) {
            return false;
        }
        for (let i = 0; i < keysA.length; i++) {
            if (!(keysA[i] in b) || a[keysA[i]] !== b[keysA[i]]) {
                return false;
            }
        }
        return true;
    }

    /*
     * Whether there is anything to save. The form as it was filled (or last
     * saved) is kept in a snapshot, renewed whenever the server hands a new
     * token: what differs from it is unsaved. The arguments are read from the
     * callback context rather than by position, there are as many as fields.
     */
    ns.save_status = function(_scope, token, _request, result) {
        const dc = window.dash_clientside;
        const args = Array.prototype.slice.call(arguments);
        const invalidChars = args[args.length - 1] || [];
        const loadedName = args[args.length - 2];
        const snapshot = args[args.length - 3];
        const context = dc.callback_context;
        const values = formValues(context, [
            "page-anchor-workflow_editor", "workflow-form-token", "workflow-save-request", "workflow-save-result",
            "workflow-form-edit", "wf-task-slots", "wf-variable-slots",
            "workflow-snapshot", "workflow-loaded-name", "workflow-invalid-chars",
        ]);
        let title = null;
        (context.states_list || []).forEach(function(entry) {
            if (entry && entry.id === "workflow-title") {
                title = entry.value;
            }
        });
        const triggers = (context.triggered || []).map(function(t) { return t.prop_id || ""; });
        function triggeredBy(id) {
            return triggers.indexOf(id + ".data") >= 0;
        }

        if (token === null || token === undefined) {
            // Not filled yet.
            return [CLEAN[0], CLEAN[1], dc.no_update];
        }
        if (!snapshot || snapshot.token !== token) {
            return [CLEAN[0], CLEAN[1], {token: token, values: values}];
        }
        // The server could not save: the reason stays on the button until the
        // next change (it is also written in the feedback line).
        if (triggeredBy("workflow-save-result") && result && result.error) {
            const e = error(result.error);
            return [e[0], e[1], dc.no_update];
        }

        const name = title === null || title === undefined ? "" : String(title);
        if (name === "") {
            const e = error("Workflow name cannot be empty");
            return [e[0], e[1], dc.no_update];
        }
        for (let i = 0; i < invalidChars.length; i++) {
            if (name.indexOf(invalidChars[i]) >= 0) {
                const label = invalidChars[i] === " " ? "' ' (space)" : "'" + invalidChars[i] + "'";
                const e = error("Unauthorized character in workflow name: " + label);
                return [e[0], e[1], dc.no_update];
            }
        }
        if (name !== (loadedName || "") || !sameValues(values, snapshot.values)) {
            if (triggeredBy("workflow-save-request")) {
                // Said on the button as soon as it is clicked; the server
                // answers once the file is written.
                return [SAVING[0], SAVING[1], dc.no_update];
            }
            return [DIRTY[0], DIRTY[1], dc.no_update];
        }
        return [CLEAN[0], CLEAN[1], dc.no_update];
    };

    /*
     * Typing in the form, handed to save_status once the keys have rested
     * (EDIT_DELAY ms). The fields typed into are States of save_status: were
     * they Inputs, each key would dispatch a callback over every field.
     */
    const EDIT_DELAY = 200;
    let editTimer = null;
    document.addEventListener("input", function(event) {
        const target = event.target;
        if (!target || !target.id || !document.getElementById("workflow-title")) {
            return;
        }
        if (target.id.indexOf("wf-") < 0 && target.id !== "workflow-title") {
            return;
        }
        clearTimeout(editTimer);
        editTimer = setTimeout(function() {
            editTimer = null;
            if (document.getElementById("workflow-title")) {
                window.dash_clientside.set_props("workflow-form-edit", {data: Date.now()});
            }
        }, EDIT_DELAY);
    }, true);

    // A click on the save button, handed to save_status.
    ns.save_request = function(_scope, nClicks) {
        if (!nClicks) {
            return window.dash_clientside.no_update;
        }
        return {clicks: nClicks, stamp: Date.now()};
    };

    /*
     * Show the fields the type of each variable uses. A field already in the
     * state it should be in is left alone: the cards come from the server with
     * the right fields shown, so on load this changes nothing.
     */
    ns.field_visibility = function(_scope, types, visibility) {
        const dc = window.dash_clientside;
        const fields = (visibility && visibility.fields) || [];
        const byType = (visibility && visibility.types) || {};
        const current = Array.prototype.slice.call(arguments, 3);
        return fields.map(function(field, f) {
            const styles = current[f] || [];
            return (types || []).map(function(type, i) {
                const visible = (byType[type] || []).indexOf(field) >= 0;
                const style = styles[i];
                const shown = !!(style && style.display && style.display !== "none");
                if (shown === visible) {
                    return dc.no_update;
                }
                return visible ? {"display": "flex"} : {"display": "none"};
            });
        });
    };
})();
