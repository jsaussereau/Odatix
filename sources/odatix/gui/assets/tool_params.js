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
 * The parameters of the flows of a tool (/tool_editor), kept in step while
 * they are typed.
 *
 * Every flow but the default one shows the values it inherits from the default
 * flow, and the head of a flow shows the values it sets. Both are only read by
 * the reader: the server writes them whenever it rebuilds the section, and in
 * between they are refreshed here, on the document, without a round trip --
 * the same way assets/folds.js answers the folds.
 */

(function() {
    // The types of a parameter, in the order of PARAM_TYPES in
    // gui/pages/tool_editor.py: the inputs of a dcc.RadioItems carry no value,
    // the one checked is told by its position.
    const TYPES = ["text", "bool", "list"];

    function rowType(row) {
        const inputs = Array.from(row.querySelectorAll(".odx-param-type input"));
        const index = inputs.findIndex(function(input) { return input.checked; });
        return TYPES[index] || "text";
    }

    // A parameter value as it reads where it is not edited, and whether it is
    // empty. Kept in step with param_display() in gui/pages/tool_editor.py.
    function rowValue(row) {
        const kind = rowType(row);
        if (kind === "bool") {
            const box = row.querySelector(".odx-param-bool input[type=checkbox]");
            return [box && box.checked ? "on" : "off", false];
        }
        if (kind === "list") {
            const area = row.querySelector("textarea.odx-param-list");
            const words = (area ? area.value : "").split("\n")
                .map(function(item) { return item.trim(); })
                .filter(function(item) { return item !== ""; })
                .join(" ");
            return words ? [words, false] : ["empty list", true];
        }
        const input = row.querySelector("input.odx-param-text");
        const text = input ? input.value : "";
        return text !== "" ? [text, false] : ["empty", true];
    }

    // Dash (React) owns these elements: their text node is changed in place,
    // never replaced, so the next render of the section still finds the node
    // it wrote and puts the server's value back in it.
    function setText(element, text) {
        const node = element.firstChild;
        if (node && node.nodeType === Node.TEXT_NODE) {
            node.nodeValue = text;
        } else if (!node) {
            element.appendChild(document.createTextNode(text));
        }
    }

    function show(element, value) {
        setText(element, value[0]);
        element.title = value[0];
    }

    function rowName(row) {
        const input = row.querySelector("input.odx-param-name");
        return input ? input.value.trim() : "";
    }

    function refresh(event) {
        const target = event.target;
        if (!target || !target.closest) {
            return;
        }
        const row = target.closest(".odx-param-row.declared");
        if (!row) {
            return;
        }
        const card = row.closest(".odx-flow-card");
        if (!card) {
            return;
        }

        // The head of the card: what the flow sets, readable while folded.
        const chip = card.querySelector('.odx-flow-param-chip[data-row="' + row.dataset.row + '"]');
        if (chip) {
            const value = rowValue(row);
            const name = chip.querySelector(".odx-flow-param-chip-name");
            const text = chip.querySelector(".odx-flow-param-chip-value");
            if (name) {
                setText(name, rowName(row));
            }
            if (text) {
                setText(text, value[0]);
            }
            chip.title = rowName(row) + " = " + value[0];
        }

        if (!card.classList.contains("default")) {
            return;
        }

        // What the default flow holds is what the other ones inherit.
        const values = {};
        card.querySelectorAll(".odx-param-row").forEach(function(other) {
            if (other.classList.contains("declared")) {
                const name = rowName(other);
                if (name) {
                    values[name] = rowValue(other);
                }
            } else if (other.dataset.param) {
                const span = other.querySelector(".odx-param-inherited-value");
                if (span) {
                    values[other.dataset.param] = [span.textContent, span.classList.contains("empty")];
                }
            }
        });

        const container = card.parentElement;
        if (!container) {
            return;
        }
        container.querySelectorAll(".odx-flow-card:not(.default)").forEach(function(other) {
            other.querySelectorAll("[data-inherits]").forEach(function(element) {
                const value = values[element.dataset.inherits];
                if (value) {
                    show(element, value);
                }
            });
        });
    }

    document.addEventListener("input", refresh, true);
    document.addEventListener("change", refresh, true);
})();
