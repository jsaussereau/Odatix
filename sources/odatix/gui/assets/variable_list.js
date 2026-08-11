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
 * The variables dropdown (see odatix.gui.builtin_variables.variable_list) is a
 * <details> element, which the browser only closes when its own summary is
 * clicked again. It drops over the page like a menu, so it should behave like
 * one: close as soon as the attention goes elsewhere.
 */

(function () {
  var PANEL_SELECTOR = "details.odx-varlist-panel";

  function closeAll(except) {
    document.querySelectorAll(PANEL_SELECTOR + "[open]").forEach(function (panel) {
      if (panel !== except) {
        panel.removeAttribute("open");
      }
    });
  }

  // Pointerdown rather than click: closing on the way down means the click that
  // dismisses the panel still reaches whatever was clicked under it.
  document.addEventListener("pointerdown", function (event) {
    var panel = event.target && event.target.closest ? event.target.closest(PANEL_SELECTOR) : null;
    closeAll(panel);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeAll(null);
    }
  });

  // Only one open at a time, and none left open behind a page change.
  document.addEventListener("toggle", function (event) {
    var panel = event.target;
    if (panel && panel.matches && panel.matches(PANEL_SELECTOR) && panel.hasAttribute("open")) {
      closeAll(panel);
    }
  }, true);
})();
