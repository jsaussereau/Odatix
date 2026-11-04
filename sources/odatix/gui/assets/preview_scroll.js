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

// Each pane is brought to its start delimiter once, when it is built: any
// later mutation of the page (a dropdown opening, a tooltip, the replaced
// section written back) must leave where the user scrolled alone.
const scrolledPanes = new WeakSet();

function scrollNewPanes() {
    document.querySelectorAll(".preview-pane").forEach(function(pre) {
        if (scrolledPanes.has(pre)) {
            return;
        }
        // A hidden pane has no layout yet: it is scrolled once it shows.
        if (pre.clientHeight === 0) {
            return;
        }
        scrolledPanes.add(pre);
        // The start delimiter is the first highlight: the commented-out notice
        // heads the pane, so its first span is not it.
        const delimiter = pre.querySelector(".text-highlight.primary");
        if (!delimiter) {
            return;
        }
        const preRect = pre.getBoundingClientRect();
        const spanRect = delimiter.getBoundingClientRect();
        pre.scrollTop = spanRect.top - preRect.top + pre.scrollTop - 29;
    });
}

document.addEventListener("DOMContentLoaded", scrollNewPanes);
new MutationObserver(scrollNewPanes).observe(document.body, { childList: true, subtree: true });
