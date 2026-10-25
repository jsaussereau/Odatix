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
 * Home page "New to Odatix?" banner: the close button hides it for this visit,
 * "Don't show again" also sets a cookie that home.py reads to skip it.
 */
(function () {
    function close(banner) {
        banner.classList.add("is-closing");
        setTimeout(function () { banner.style.display = "none"; }, 400);
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest(".odx-home-start-close, .odx-home-start-never");
        if (!button) return;
        var banner = button.closest(".odx-home-start");
        if (!banner) return;
        if (button.classList.contains("odx-home-start-never")) {
            document.cookie = "odatix_hide_home_start=1; path=/; max-age=31536000; SameSite=Lax";
        }
        close(banner);
    });
})();
