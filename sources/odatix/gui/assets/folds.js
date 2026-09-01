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
 * Every fold of the interface, answered here.
 *
 * Folding a panel away is a property of the page: nothing outside the browser
 * reads it, and no other callback reads the style or the class it writes. So it
 * is done on the document, without going through Dash at all -- neither the
 * server nor the renderer. Dash answering a fold means walking every component
 * the pattern matches, which on a page holding hundreds of cards costs about a
 * second whether the answer comes from the server or from a clientside
 * callback; this costs nothing.
 *
 * A row rebuilt by Dash (a card added, duplicated or deleted) comes back folded
 * the way it was built, which is what the server versions did too. The two
 * folds that the server *does* have to know about -- an architecture card and a
 * flow card, whose folded state is written back into the entry -- keep their
 * hidden input in step through `set_props`, so a re-render of the section still
 * finds every card as the reader left it.
 *
 * The folds of the configuration editor live in assets/config_editor.js and
 * those of the metric editor in assets/metric_editor.js: same idea, tables of
 * their own.
 */

(function() {
    // Keyed by the id type of the button. `panel`, `icon`, `card` and `state`
    // name components sharing that id under another type, the way Dash pattern
    // ids are paired everywhere in this app.
    //
    //   style   -- the panel is shown by its display style ("shown"), hidden by
    //              display:none. Extra fields of a card.
    //   section -- the panel is an "animated-section", folded by the "hide"
    //              class it carries.
    //   card    -- an animated-section too, but the whole card is marked
    //              "collapsed" and the state is written back to a hidden input
    //              the server reads when it rebuilds the section.
    const FOLDS = {
        // Extra fields of a target (select_targets)
        "target-more": {
            kind: "style", panel: "target-extra-div", icon: "target-more-icon", shown: "block",
        },
        // Extra fields of a derived metric (derived_metrics)
        "dm-more-fields": {
            kind: "style", panel: "dm-more-field-div", icon: "dm-more-fields-icon", shown: "flex",
        },
        // Extra fields of a task (sim_editor, workflow_editor)
        "sim-more-fields-task": {
            kind: "style", panel: "sim-more-task-field-div", icon: "sim-more-task-fields-icon", shown: "flex",
        },
        "wf-more-fields-task": {
            kind: "style", panel: "wf-more-task-field-div", icon: "wf-more-task-fields-icon", shown: "flex",
        },
        // Whitelist and blacklist of the design path (architecture_editor).
        // Plain string ids, not a pattern: there is one of these on the page.
        "more-fields-design-path-filters-toggle": {
            kind: "section",
            panel: "more-fields-design-path-filters",
            icon: "more-fields-design-path-filters-toggle-icon",
        },
        // Job Settings, folded away once it is set up (jobs_config). This one
        // says what it does in words rather than with a rotating glyph.
        "jobs-settings-toggle": {
            kind: "section", panel: "jobs-settings-body", label: {open: "Hide", folded: "Show"},
        },
        // A whole architecture card (sim_editor) or flow card (tool_editor),
        // folded down to its head.
        "sim-arch-toggle": {
            kind: "card", panel: "sim-arch-body", icon: "sim-arch-toggle-icon",
            card: "sim-arch-card", state: "sim-arch-collapsed",
        },
        "tool-flow-toggle": {
            kind: "card", panel: "tool-flow-body", icon: "tool-flow-toggle-icon",
            card: "tool-flow-card", state: "tool-flow-collapsed",
        },
    };

    // Dash writes a pattern id as JSON with its keys sorted: to name the panel
    // of a button, swap the type and write it back the same way. A button named
    // by a plain string has siblings named by plain strings too.
    function sibling(id, type) {
        if (typeof id === "string") {
            return document.getElementById(type);
        }
        const other = Object.assign({}, id, {type: type});
        return document.getElementById(JSON.stringify(other, Object.keys(other).sort()));
    }

    // The click lands on whatever is inside the button -- the glyph carries an
    // id of its own -- so every ancestor is looked at until one of them is a
    // fold button, not just the first one that happens to be named.
    function foldOf(node) {
        while (node && node !== document) {
            const raw = node.id || "";
            let id = null;
            if (raw.charAt(0) === "{") {
                try {
                    id = JSON.parse(raw);
                } catch (error) {
                    id = null;
                }
            } else if (raw) {
                id = raw;
            }
            if (id) {
                const type = typeof id === "string" ? id : id.type;
                if (FOLDS[type]) {
                    return {id: id, fold: FOLDS[type]};
                }
            }
            node = node.parentNode;
        }
        return null;
    }

    function rotate(id, fold, open) {
        const glyph = sibling(id, fold.icon);
        if (glyph) {
            glyph.classList.toggle("rotated", open);
        }
    }

    document.addEventListener("click", function(event) {
        const found = foldOf(event.target);
        if (!found) {
            return;
        }
        const fold = found.fold;
        const panel = sibling(found.id, fold.panel);
        if (!panel) {
            return;
        }
        if (fold.kind === "style") {
            const open = panel.style.display === "none";
            panel.style.display = open ? fold.shown : "none";
            rotate(found.id, fold, open);
            return;
        }
        // section and card are both folded by the "hide" class of an
        // animated-section, so the transition plays either way.
        const open = panel.classList.contains("hide");
        panel.classList.toggle("hide", !open);
        rotate(found.id, fold, open);
        if (fold.label) {
            const button = sibling(found.id, typeof found.id === "string" ? found.id : found.id.type);
            if (button) {
                button.textContent = open ? fold.label.open : fold.label.folded;
            }
        }
        if (fold.kind !== "card") {
            return;
        }
        const card = sibling(found.id, fold.card);
        if (card) {
            card.classList.toggle("collapsed", !open);
        }
        // The server reads this back when it rebuilds the section, so it is set
        // through Dash rather than on the DOM: a value written on the input
        // element never reaches the renderer's own state.
        const dc = window.dash_clientside;
        if (dc && dc.set_props) {
            const state = Object.assign({}, found.id, {type: fold.state});
            dc.set_props(state, {value: open ? "" : "1"});
        }
    }, true);
})();
