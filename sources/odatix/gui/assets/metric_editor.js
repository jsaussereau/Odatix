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
 * Client-side behaviour of the metric editor (odatix.gui.pages.metric_editor).
 * Which fields an extraction type uses, and whether the extra fields of a card
 * are folded away, are properties of the page: nothing outside the browser
 * reads them, so neither is worth a server round-trip.
 */

window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.odatix_metric_editor = window.dash_clientside.odatix_metric_editor || {};

// Kept in step with FIELD_VISIBILITY in odatix/gui/pages/metric_editor.py: the
// cards are already built with the right fields shown, this only follows the
// type dropdown afterwards.
const ODATIX_METRIC_FIELDS = ["file", "pattern", "group_id", "key", "op"];
const ODATIX_FIELD_VISIBILITY = {
    "regex":     ["file", "pattern", "group_id"],
    "csv":       ["file", "key"],
    "yaml":      ["file", "key"],
    "json":      ["file", "key"],
    "xml":       ["file", "key"],
    "operation": ["op"],
};

/*
 * Show the fields the selected extraction type uses. A field already in the
 * state it should be in is left alone: the cards come from the server with the
 * right fields shown, so on load this returns no_update everywhere instead of
 * making Dash re-render every field of every card -- which is what made the
 * fields of a card flash in and out while the page was settling.
 */
window.dash_clientside.odatix_metric_editor.field_visibility = function(_scope, types) {
    const dc = window.dash_clientside;
    const current = Array.prototype.slice.call(arguments, 2);
    return ODATIX_METRIC_FIELDS.map(function(field, f) {
        const styles = current[f] || [];
        return (types || []).map(function(type, i) {
            const visible = (ODATIX_FIELD_VISIBILITY[type] || []).indexOf(field) >= 0;
            const style = styles[i];
            const shown = !!(style && style.display && style.display !== "none");
            if (shown === visible) {
                return dc.no_update;
            }
            return visible ? {"display": "flex"} : {"display": "none"};
        });
    });
};

/*
 * Folding the extra fields of a card away, done on the document rather than
 * through Dash -- same reasoning (and same mechanics) as the folds of the
 * configuration editor, see assets/config_editor.js.
 *
 * A card rebuilt by Dash (a metric added, duplicated or deleted) comes back
 * folded the way it was built, which is what the server version did too.
 */
(function() {
    // The button, the panel it opens and its glyph share an id, under three
    // types, the way Dash pattern ids are paired everywhere on this page. Only
    // the sections of this page are listed: other pages have folds of their own
    // (wf-more-fields, dm-more-fields...) that their own callbacks answer.
    const PREFIXES = ["metric", "metadata", "metric3"];

    function siblingId(id, type) {
        const other = Object.assign({}, id, {type: type});
        return JSON.stringify(other, Object.keys(other).sort());
    }

    // The click lands on whatever is inside the button -- the glyph carries a
    // pattern id of its own -- so every ancestor is looked at.
    function buttonOf(node) {
        while (node && node !== document) {
            const raw = node.id || "";
            if (raw.charAt(0) === "{") {
                let id = null;
                try {
                    id = JSON.parse(raw);
                } catch (error) {
                    id = null;
                }
                for (let i = 0; id && i < PREFIXES.length; i++) {
                    if (id.type === PREFIXES[i] + "-more-fields") {
                        return {id: id, prefix: PREFIXES[i]};
                    }
                }
            }
            node = node.parentNode;
        }
        return null;
    }

    document.addEventListener("click", function(event) {
        const found = buttonOf(event.target);
        if (!found) {
            return;
        }
        const panel = document.getElementById(siblingId(found.id, found.prefix + "-more-field-div"));
        if (!panel) {
            return;
        }
        const hidden = panel.style.display === "none";
        panel.style.display = hidden ? "flex" : "none";
        const glyph = document.getElementById(siblingId(found.id, found.prefix + "-more-fields-icon"));
        if (glyph) {
            glyph.classList.toggle("rotated", hidden);
        }
    }, true);
})();
