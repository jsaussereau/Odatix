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
 * Top-bar behaviour shared by every page: the mobile burger menu and the
 * theme cookie. Registered from odatix.gui.navigation.
 */

window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.odatix_nav = window.dash_clientside.odatix_nav || {};

window.dash_clientside.odatix_nav.toggle_burger_menu = function(n_clicks, pathname, cls) {
    const ctx = window.dash_clientside.callback_context;
    const trigger = (ctx.triggered && ctx.triggered.length) ? ctx.triggered[0].prop_id : "";
    const open = trigger.startsWith("nav-burger") && !(cls || "").includes("open");
    return [open ? "nav-menu open" : "nav-menu", open ? "nav-burger open" : "nav-burger"];
};

/*
 * Persist the chosen theme in a cookie so it survives page refreshes and app
 * restarts (read back server-side by odatix.gui.themes.theme_from_cookie). The
 * cookie name comes from the theme-cookie-name store rather than being repeated
 * here, so Python stays the single source of truth.
 */
window.dash_clientside.odatix_nav.persist_theme = function(theme, cookieName) {
    if (cookieName) {
        document.cookie = cookieName + "=" + theme + ";path=/;max-age=31536000;samesite=Lax";
    }
    return window.dash_clientside.no_update;
};
