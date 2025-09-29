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

document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll(".preview-pane").forEach(function(pre) {
        // Get first span as it is the span of the start delimiter
        const firstSpan = pre.querySelector("span");
        if (firstSpan) {
            const preRect = pre.getBoundingClientRect();
            const spanRect = firstSpan.getBoundingClientRect();
            const offset = spanRect.top - preRect.top + pre.scrollTop - 29;
            pre.scrollTop = offset;
        }
    });
});

// Si le contenu change dynamiquement
const previewObserver = new MutationObserver(() => {
    document.querySelectorAll(".preview-pane").forEach(function(pre) {
        // Get first span as it is the span of the start delimiter
        const firstSpan = pre.querySelector("span");
        if (firstSpan) {
            const preRect = pre.getBoundingClientRect();
            const spanRect = firstSpan.getBoundingClientRect();
            const offset = spanRect.top - preRect.top + pre.scrollTop - 29;
            pre.scrollTop = offset;
        }
    });
});
previewObserver.observe(document.body, { childList: true, subtree: true });
