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

function resizeTextarea(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = (textarea.scrollHeight-20) + "px";
}

document.addEventListener("input", function(e) {
    if (e.target.classList && e.target.classList.contains("auto-resize-textarea")) {
        resizeTextarea(e.target);
    }
});

window.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll(".auto-resize-textarea").forEach(resizeTextarea);
});

/*
 * Textareas added to the page are sized once they are laid out. Only the
 * added ones: resizing every textarea of the page at each mutation forced a
 * layout per textarea, at each keystroke, on a big form.
 */
let pendingTextareas = new Set();
let resizeTimer = null;

function resizePending() {
    resizeTimer = null;
    const textareas = pendingTextareas;
    pendingTextareas = new Set();
    textareas.forEach(function(textarea) {
        if (textarea.isConnected) {
            resizeTextarea(textarea);
        }
    });
}

const textarea_observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        mutation.addedNodes.forEach(function(node) {
            if (node.nodeType !== 1) {
                return;
            }
            if (node.classList.contains("auto-resize-textarea")) {
                pendingTextareas.add(node);
            }
            node.querySelectorAll(".auto-resize-textarea").forEach(function(textarea) {
                pendingTextareas.add(textarea);
            });
        });
        // A textarea shown again (its fold opened) has to be measured anew.
        if (mutation.type === "attributes" && mutation.target.nodeType === 1 && mutation.target.querySelectorAll) {
            mutation.target.querySelectorAll(".auto-resize-textarea").forEach(function(textarea) {
                pendingTextareas.add(textarea);
            });
        }
    });
    if (pendingTextareas.size && resizeTimer === null) {
        // small delay to ensure layout has updated
        resizeTimer = setTimeout(resizePending, 100);
    }
});
textarea_observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class", "open"] });
