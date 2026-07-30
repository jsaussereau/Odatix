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
 * Topbar links pointing at a fragment of the page they are already on (e.g.
 * "RTL Simulations" -> "/architectures#simulations") leave the url unchanged,
 * so dcc.Link navigates nowhere and no Dash callback fires: the scroll has to
 * be triggered from the click itself.
 *
 * Navigating from another page is handled by a clientside callback on the url
 * instead (see architectures.py), because the target then still has to be
 * waited for.
 */
document.addEventListener("click", function(event) {
    const link = event.target.closest("a[href*='#']");
    if (!link) {
        return;
    }
    const href = link.getAttribute("href") || "";
    const hashIndex = href.indexOf("#");
    const id = href.slice(hashIndex + 1);
    if (!id) {
        return;
    }
    // Only same-page fragments: anything else is a real navigation, which the
    // url callback takes care of once the target page has rendered.
    const path = href.slice(0, hashIndex);
    if (path && path !== window.location.pathname) {
        return;
    }
    const target = document.getElementById(id);
    if (target) {
        target.scrollIntoView({behavior: "smooth", block: "start"});
    }
}, true);
