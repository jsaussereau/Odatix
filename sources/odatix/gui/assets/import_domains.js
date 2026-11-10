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
 * Parameter domains of the "Import an existing project" popup
 * (odatix.gui.project_import): parameters are dragged from the list of the
 * top level onto domains, onto the "new domain" zone, or back to the list.
 * A click on a parameter of the list gives it a domain of its own; the cross
 * of a parameter in a domain sends it back.
 *
 * The state is the "import-domains" store: {"domains": [{"name", "names",
 * "auto"}]}. This file only turns gestures into a new state (set_props); the
 * server renders it. "auto" marks a name Odatix chose, which follows the
 * parameters of the domain until the user renames it.
 *
 * Events are delegated to the document, so that they survive the renders.
 */

(function() {
    var STORE = "import-domains";
    var state = {domains: []};
    var dragged = null;

    window.dash_clientside = window.dash_clientside || {};
    window.dash_clientside.odatix_import = window.dash_clientside.odatix_import || {};

    // Keeps the state this file works on in step with the store.
    window.dash_clientside.odatix_import.sync = function(data) {
        state = data && data.domains ? data : {domains: []};
        state.values = state.values || {};
        return window.dash_clientside.no_update;
    };

    function copy() {
        return {domains: state.domains.map(function(d) {
            return {name: d.name, names: d.names.slice(), auto: d.auto};
        }), values: Object.assign({}, state.values || {})};
    }

    // "p_icache_size_pw2" + "p_icache_ways" -> "icache": the words they share,
    // without a one-letter prefix (p_, i_, o_...).
    function autoName(names) {
        if (names.length === 1) {
            return names[0];
        }
        var words = names.map(function(n) { return n.split("_"); });
        var common = [];
        for (var i = 0; i < words[0].length; i++) {
            var word = words[0][i];
            if (words.every(function(w) { return w[i] === word; })) {
                common.push(word);
            } else {
                break;
            }
        }
        if (common.length && common[0].length === 1) {
            common.shift();
        }
        return common.join("_") || "group";
    }

    function uniqueName(name, domains, self) {
        var taken = domains.filter(function(d) { return d !== self; }).map(function(d) { return d.name; });
        if (taken.indexOf(name) < 0) {
            return name;
        }
        for (var i = 2; ; i++) {
            if (taken.indexOf(name + "_" + i) < 0) {
                return name + "_" + i;
            }
        }
    }

    function tidy(next) {
        next.domains = next.domains.filter(function(d) { return d.names.length > 0; });
        next.domains.forEach(function(d) {
            if (d.auto) {
                d.name = uniqueName(autoName(d.names), next.domains, d);
            }
        });
        return next;
    }

    function publish(next) {
        state = tidy(next);
        window.dash_clientside.set_props(STORE, {data: state});
    }

    function without(next, name) {
        next.domains.forEach(function(d) {
            d.names = d.names.filter(function(n) { return n !== name; });
        });
        return next;
    }

    // target: a domain index, "new", or "pool"
    function move(name, target) {
        var next = without(copy(), name);
        if (target === "new") {
            next.domains.push({name: name, names: [name], auto: true});
        } else if (target !== "pool") {
            var domain = next.domains[target];
            if (!domain) {
                return;
            }
            domain.names.push(name);
        }
        publish(next);
    }

    function zoneOf(element) {
        return element && element.closest ? element.closest("[data-drop]") : null;
    }

    function targetOf(zone) {
        var drop = zone.getAttribute("data-drop");
        return drop === "new" || drop === "pool" ? drop : parseInt(drop, 10);
    }

    document.addEventListener("dragstart", function(event) {
        var chip = event.target.closest && event.target.closest("[data-param]");
        if (!chip) {
            return;
        }
        dragged = chip.getAttribute("data-param");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", dragged);
        chip.classList.add("dragging");
        document.body.classList.add("odx-import-dragging");
    });

    document.addEventListener("dragend", function(event) {
        dragged = null;
        document.body.classList.remove("odx-import-dragging");
        document.querySelectorAll(".dragging, .drag-over").forEach(function(e) {
            e.classList.remove("dragging", "drag-over");
        });
    });

    document.addEventListener("dragover", function(event) {
        var zone = zoneOf(event.target);
        if (!zone || !dragged) {
            return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        document.querySelectorAll(".drag-over").forEach(function(e) {
            if (e !== zone) {
                e.classList.remove("drag-over");
            }
        });
        zone.classList.add("drag-over");
    });

    document.addEventListener("dragleave", function(event) {
        var zone = zoneOf(event.target);
        if (zone && !zone.contains(event.relatedTarget)) {
            zone.classList.remove("drag-over");
        }
    });

    document.addEventListener("drop", function(event) {
        var zone = zoneOf(event.target);
        if (!zone || !dragged) {
            return;
        }
        event.preventDefault();
        zone.classList.remove("drag-over");
        move(dragged, targetOf(zone));
    });

    document.addEventListener("click", function(event) {
        var remove = event.target.closest && event.target.closest("[data-remove]");
        if (remove) {
            move(remove.getAttribute("data-remove"), "pool");
            return;
        }
        // a click on a parameter of the list: a domain of its own
        var chip = event.target.closest && event.target.closest(".odx-import-pool [data-param]");
        if (chip) {
            move(chip.getAttribute("data-param"), "new");
        }
    });

    document.addEventListener("keydown", function(event) {
        var chip = event.target.closest && event.target.closest(".odx-import-pool [data-param]");
        if (chip && (event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            move(chip.getAttribute("data-param"), "new");
        }
    });

    // Filter of the list: hides what does not match, nothing more. Applied
    // again after each render, which brings the chips back.
    function applyFilter() {
        var input = document.getElementById("import-param-filter");
        var text = input ? input.value.trim().toLowerCase() : "";
        document.querySelectorAll(".odx-import-pool [data-param]").forEach(function(chip) {
            var match = !text || chip.getAttribute("data-param").toLowerCase().indexOf(text) >= 0;
            chip.style.display = match ? "" : "none";
        });
    }

    // Values of a parameter, as workspace.detect.values_variable reads them:
    // how many they are, or why they are none (null: its current value).
    function countValues(text) {
        text = text.trim();
        if (!text) {
            return null;
        }
        var m = text.match(/^(-?\d+)\s*\.\.\s*(-?\d+)(?:\s*(?:step|:|\/)\s*(\d+)|\s+(pow2|power_of_two|x2))?$/i);
        if (m) {
            var low = parseInt(m[1], 10), high = parseInt(m[2], 10);
            if (low > high) { return {error: "bounds reversed"}; }
            if (m[4]) {
                if (low <= 0) { return {error: "positive bounds"}; }
                return {count: Math.max(0, Math.floor(Math.log2(high)) - Math.ceil(Math.log2(low)) + 1)};
            }
            var step = m[3] ? parseInt(m[3], 10) : 1;
            if (step === 0) { return {error: "step 0"}; }
            return {count: Math.floor((high - low) / step) + 1};
        }
        if (text.indexOf("..") >= 0) {
            return {error: "a..b [step s | pow2]"};
        }
        return {count: text.split(/[,;\s]+/).filter(function(v) { return v; }).length};
    }

    function showCount(input) {
        var name = input.name;
        var badge = document.querySelector('[data-count="' + name + '"]');
        if (!badge) {
            return;
        }
        var result = countValues(input.value);
        badge.classList.toggle("invalid", !!(result && result.error));
        input.classList.toggle("invalid", !!(result && result.error));
        var text = !result ? "current only" : result.error ? result.error
            : result.count + " value" + (result.count > 1 ? "s" : "");
        // only when it changes: writing it is a mutation the observer below sees
        if (badge.textContent !== text) {
            badge.textContent = text;
        }
    }

    function showCounts() {
        document.querySelectorAll("input.odx-import-values").forEach(showCount);
    }

    document.addEventListener("input", function(event) {
        if (!event.target.matches) {
            return;
        }
        if (event.target.matches("#import-param-filter")) {
            applyFilter();
        } else if (event.target.matches("input.odx-import-values")) {
            // kept here, sent with the next move: no render while typing
            state.values = state.values || {};
            state.values[event.target.name] = event.target.value;
            showCount(event.target);
        }
    });

    new MutationObserver(function(mutations) {
        for (var i = 0; i < mutations.length; i++) {
            var target = mutations[i].target;
            if (target.closest && target.closest(".odx-import-board, .odx-import-pool, .odx-import-domains")) {
                applyFilter();
                showCounts();
                return;
            }
        }
    }).observe(document.documentElement, {childList: true, subtree: true});
})();
