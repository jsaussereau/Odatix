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
 * Client-side behaviour of the architectures page (odatix.gui.pages.architectures).
 */

window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.odatix_architectures = window.dash_clientside.odatix_architectures || {};

window.dash_clientside.odatix_architectures.scroll_to_simulations = function(href) {
    if (!href || href.indexOf("#simulations") === -1) {
        return "";
    }
    // A navigation supersedes the wait started by the previous one.
    const token = (window.__odatixScrollToken || 0) + 1;
    window.__odatixScrollToken = token;

    let frames = 0;
    const maxFrames = 90;  // ~1.5 s, then scroll to wherever it is
    const attempt = function() {
        if (window.__odatixScrollToken !== token) {
            return;
        }
        const target = document.getElementById("simulations");
        const archCards = document.getElementById("arch-cards-matrix");
        const rendered = target && archCards && archCards.childElementCount > 0;
        if (target && (rendered || frames >= maxFrames)) {
            target.scrollIntoView({behavior: "smooth", block: "start"});
            return;
        }
        if (frames++ < maxFrames) {
            window.requestAnimationFrame(attempt);
        }
    };
    window.requestAnimationFrame(attempt);
    return "";
};
