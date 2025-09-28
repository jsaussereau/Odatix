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

document.addEventListener("input", function(e) {
    if (e.target.classList.contains("auto-resize-textarea")) {
        e.target.style.height = "auto";
        e.target.style.height = (e.target.scrollHeight-20) + "px";
    }
});

window.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll(".auto-resize-textarea").forEach(function(textarea) {
        textarea.style.height = "auto";
        textarea.style.height = (textarea.scrollHeight-20) + "px";
    });
});

const textarea_observer = new MutationObserver(() => {
    document.querySelectorAll(".auto-resize-textarea").forEach(function(textarea) {
        textarea.style.height = "auto";
        textarea.style.height = (textarea.scrollHeight-20) + "px";
    });
});
textarea_observer.observe(document.body, { childList: true, subtree: true });

const dropdown_observer = new MutationObserver(() => {
    setTimeout(function() {
        document.querySelectorAll(".auto-resize-textarea").forEach(function(textarea) {
            textarea.style.height = "auto";
            textarea.style.height = (textarea.scrollHeight-20) + "px";
        });
    }, 100); // small delay to ensure layout has updated
});
dropdown_observer.observe(document.body, { childList: true, subtree: true });
