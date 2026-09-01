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
 * Client-side behaviour of the configuration editor
 * (odatix.gui.pages.config_editor). Everything here answers keystrokes or reads
 * class names, so none of it is worth a server round-trip.
 */

window.dash_clientside = window.dash_clientside || {};

// `_scope` is the page anchor injected by odatix.gui.page_scope: it keeps these
// handlers from running on the other pages of the app. Ignore its value.
window.dash_clientside.odatix_config_editor = window.dash_clientside.odatix_config_editor || {};

window.dash_clientside.odatix_config_editor.debounce_content = function(_scope, _contents) {
    const state = window.__odatixPreviewDebounce = window.__odatixPreviewDebounce
        || {domains: {}, all: false, timer: null};
    const context = window.dash_clientside.callback_context;
    (context.triggered || []).forEach(function(trigger) {
        const raw = trigger.prop_id || "";
        const cut = raw.lastIndexOf(".");
        let id = null;
        if (cut > 0) {
            try { id = JSON.parse(raw.slice(0, cut)); } catch (error) { id = null; }
        }
        if (id && id.domain_uuid) {
            state.domains[id.domain_uuid] = true;
        } else {
            state.all = true;
        }
    });
    if (state.timer) {
        clearTimeout(state.timer);
    }
    state.timer = setTimeout(function() {
        const payload = {
            stamp: Date.now(),
            domains: state.all ? null : Object.keys(state.domains),
        };
        state.domains = {};
        state.all = false;
        state.timer = null;
        window.dash_clientside.set_props("config-content-debounce", {data: payload});
    }, 400);
    return window.dash_clientside.no_update;
};

/*
 * Fill the preview config selector of each domain with its configs. Renaming a
 * configuration retitles its entry as it is typed, so this answers every
 * keystroke of every title: it is a relabelling of data the client already
 * holds, and it stays there.
 */
window.dash_clientside.odatix_config_editor.sync_preview_select = function(_section, titles, metadata, domains, currentValues) {
    const optionsOut = [];
    const valuesOut = [];
    (domains || []).forEach(function(domain, i) {
        const domainUuid = (domain && domain.domain_uuid) || "";
        const options = [];
        (metadata || []).forEach(function(config, j) {
            if (!config || (config.domain_uuid || "") !== domainUuid) {
                return;
            }
            const title = (titles && titles[j]) ? titles[j] : (config.config_name || "");
            options.push({label: title, value: config.config_uuid || ""});
        });
        let current = i < (currentValues || []).length ? currentValues[i] : null;
        const known = options.some(function(option) { return option.value === current; });
        if (!known) {
            current = options.length ? options[0].value : null;
        }
        optionsOut.push(options);
        valuesOut.push(current);
    });
    return [optionsOut, valuesOut];
};

/*
 * The dirty state of a card is nothing but string comparisons, and it is the one
 * thing that has to answer every keystroke. Run on the client: a domain with a
 * few hundred configurations would otherwise send every title and every content
 * to the server, and take back a class name per card, on every character typed.
 */
window.dash_clientside.odatix_config_editor.save_status = function(_section, titles, contents, initialTitles, initialContents, invalidChars) {
    // Passed in from odatix.lib.hard_settings through the cfg-invalid-chars store
    // rather than baked in here, so both sides always agree on the list.
    const invalid = invalidChars || [];
    const base = "icon-button tooltip delay bottom small";
    const context = window.dash_clientside.callback_context;
    const outputs = (context && context.outputs_list && context.outputs_list[0]) || [];
    // Names are only taken within their own domain: two domains can each have a "12"
    const domains = outputs.map(function(output) {
        return (output && output.id && output.id.domain_uuid) || "";
    });
    const takenByDomain = {};
    for (let i = 0; i < initialTitles.length; i++) {
        const domain = domains[i] === undefined ? "" : domains[i];
        (takenByDomain[domain] = takenByDomain[domain] || []).push(initialTitles[i]);
    }
    const classes = [];
    const tooltips = [];
    for (let i = 0; i < titles.length; i++) {
        const title = titles[i];
        const initialTitle = initialTitles[i];
        let error = null;
        if (!title) {
            error = "Configuration name cannot be empty";
        } else {
            for (let c = 0; c < invalid.length; c++) {
                if (title.indexOf(invalid[c]) !== -1) {
                    const shown = invalid[c] === " " ? "' ' (space)" : "'" + invalid[c] + "'";
                    error = "Unauthorized character in configuration name: " + shown;
                    break;
                }
            }
            if (!error && title !== initialTitle
                    && (takenByDomain[domains[i]] || []).indexOf(title) !== -1) {
                error = "A configuration with this name already exists in the domain.";
            }
        }
        if (error) {
            classes.push("color-button error-status " + base);
            tooltips.push(error);
        } else if (title !== initialTitle || contents[i] !== initialContents[i]) {
            classes.push("color-button warning " + base);
            tooltips.push("Unsaved changes!");
        } else {
            classes.push("color-button disabled " + base);
            tooltips.push("Nothing to save");
        }
    }
    return [classes, tooltips];
};

/*
 * Clicking a filter stat only flips the origin it names, and only for its own
 * domain: the strips of the other domains keep whatever they were filtering.
 */
window.dash_clientside.odatix_config_editor.filter_toggle = function(_scope, clicks, states, stateIds) {
    const dc = window.dash_clientside;
    const context = dc.callback_context;
    const trigger = context.triggered && context.triggered[0];
    if (!trigger || !trigger.value) {
        return dc.no_update;
    }
    const id = JSON.parse(trigger.prop_id.substring(0, trigger.prop_id.lastIndexOf(".")));
    return (states || []).map(function(state, i) {
        const stateId = (stateIds || [])[i] || {};
        if ((stateId.domain_uuid || "") !== (id.domain_uuid || "")) {
            return dc.no_update;
        }
        const filtered = (state || []).slice();
        const at = filtered.indexOf(id.origin);
        if (at >= 0) {
            filtered.splice(at, 1);
        } else {
            filtered.push(id.origin);
        }
        return filtered;
    });
};

/*
 * Filtered cards are hidden rather than dropped: what a card holds is unsaved
 * work as often as not, and its style is the one thing the layout switch does
 * not rewrite, so the two never fight over the same property.
 */
window.dash_clientside.odatix_config_editor.filter_apply = function(_scope, states, metadata, stateIds, styles) {
    const dc = window.dash_clientside;
    const filtered = {};
    (stateIds || []).forEach(function(stateId, i) {
        filtered[(stateId && stateId.domain_uuid) || ""] = (states || [])[i] || [];
    });
    return (metadata || []).map(function(config, i) {
        config = config || {};
        const hidden = filtered[config.domain_uuid || ""] || [];
        const away = hidden.indexOf(config.origin || "manual") >= 0;
        // A card already in the state it should be in is left alone: rewriting
        // the style of hundreds of untouched cards is what made a filter click
        // slow, and Dash re-renders a card for every style it is handed.
        const style = (styles || [])[i];
        if (style && (style.display === "none") === away) {
            return dc.no_update;
        }
        if (!style && !away) {
            return dc.no_update;
        }
        return away ? {"display": "none"} : {};
    });
};

window.dash_clientside.odatix_config_editor.save_all_status = function(_scope, configClasses, paramsClasses, rulesClasses) {
    const base = "icon-button tooltip bottom auto caution";
    const all = [].concat(configClasses || [], paramsClasses || [], rulesClasses || []);
    const dirty = all.some(function(name) {
        return typeof name === "string" && name.indexOf("warning") !== -1;
    });
    if (dirty) {
        return ["color-button warning " + base, "Save all changes"];
    }
    return ["color-button disabled " + base, "Nothing to save"];
};

/*
 * Folding a panel away is a property of the page: nothing outside the browser
 * reads it, and no other callback reads the style or the class it writes. So
 * it is done here, on the document, without going through Dash at all --
 * neither the server nor the renderer. Dash answering a fold means walking
 * every component the pattern matches, which on a page holding hundreds of
 * configuration cards costs about a second whether the answer comes from the
 * server or from a clientside callback; this costs nothing.
 *
 * A row rebuilt by Dash (a variable added, duplicated or deleted) comes back
 * folded the way it was built, which is what the server versions did too.
 */
(function() {
    // Which fold each button owns: the panel it opens shares its id, under
    // another type, the way Dash pattern ids are paired everywhere on this page.
    const FOLDS = {
        "cfg-variable-collapse": {panel: "cfg-variable-fields-container", shown: "", icon: "cfg-variable-collapse-icon"},
        "cfg-advanced-toggle": {panel: "cfg-advanced-panel", shown: "12px", icon: "cfg-advanced-icon"},
        "cfg-help-toggle": {panel: "cfg-help-panel", shown: "", icon: "cfg-help-icon"},
    };

    // Dash writes a pattern id as JSON with its keys sorted: to name the panel
    // of a button, swap the type and write it back the same way.
    function siblingId(id, type) {
        const other = Object.assign({}, id, {type: type});
        const keys = Object.keys(other).sort();
        return JSON.stringify(other, keys);
    }

    // The click lands on whatever is inside the button -- the glyph carries a
    // pattern id of its own -- so every ancestor is looked at until one of them
    // is a fold button, not just the first one that happens to be named.
    function foldOf(node) {
        while (node && node !== document) {
            const raw = node.id || "";
            if (raw.charAt(0) === "{") {
                let id = null;
                try {
                    id = JSON.parse(raw);
                } catch (error) {
                    id = null;
                }
                const fold = id && FOLDS[id.type];
                if (fold) {
                    return {id: id, fold: fold};
                }
            }
            node = node.parentNode;
        }
        return null;
    }

    document.addEventListener("click", function(event) {
        const found = foldOf(event.target);
        if (!found) {
            return;
        }
        const panel = document.getElementById(siblingId(found.id, found.fold.panel));
        if (!panel) {
            return;
        }
        const hidden = panel.style.display === "none";
        panel.style.display = hidden ? "" : "none";
        // The panel of the advanced section carries a margin of its own, which
        // hiding it takes away and showing it has to give back.
        if (found.fold.shown) {
            panel.style.marginTop = hidden ? found.fold.shown : "";
        }
        const glyph = document.getElementById(siblingId(found.id, found.fold.icon));
        if (glyph) {
            glyph.classList.toggle("rotated", hidden);
        }
    }, true);
})();
