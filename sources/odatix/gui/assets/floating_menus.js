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
 * Keep the menus that open over the page whole and on screen, in the GUI and
 * in Odatix Explorer (both serve this assets folder).
 *
 * Dropdown menus (dcc.Dropdown): the menu always opens downward and lives
 * inside its control, so near the bottom of the window, or of a panel that
 * scrolls (the Explorer side bar), it was cut. When it opens, it is measured:
 *   - not enough room below but more above: it opens upward (`odx-menu-up`);
 *   - option labels wider than the control: the menu widens to show them,
 *     up to the room left in the window, and shifts left if needed.
 *
 * Step pickers (`.odx-steps-pop`, flows of the tool cards of "Select a tool"):
 * the popover opens on the right of its flow; on the last card of a row it
 * opens on the left when the right side has no room (`odx-pop-left`).
 *
 * No observer runs in the background: measures happen right after the
 * gestures that can open a menu (press, key, focus, hover of a card).
 */
(function () {
  "use strict";

  var MARGIN = 6;
  var MAX_MENU_WIDTH = 520;

  function viewport() {
    return {
      left: 0,
      top: 0,
      right: document.documentElement.clientWidth || window.innerWidth,
      bottom: window.innerHeight
    };
  }

  // The visible area for `el`: the window, cut by every ancestor that clips
  // its content (scrolling panels, rounded cards with overflow hidden).
  function clipArea(el) {
    var area = viewport();
    for (var a = el.parentElement; a && a !== document.body && a !== document.documentElement; a = a.parentElement) {
      var cs = window.getComputedStyle(a);
      if (cs.overflowY !== "visible" || cs.overflowX !== "visible") {
        var r = a.getBoundingClientRect();
        if (cs.overflowY !== "visible") {
          area.top = Math.max(area.top, r.top);
          area.bottom = Math.min(area.bottom, r.bottom);
        }
        if (cs.overflowX !== "visible") {
          area.left = Math.max(area.left, r.left);
          area.right = Math.min(area.right, r.right);
        }
      }
    }
    return area;
  }

  function fitMenu(select) {
    var menu = select.querySelector(".Select-menu-outer");
    var control = select.querySelector(".Select-control") || select;
    if (!menu) {
      return;
    }
    var area = clipArea(select);
    var c = control.getBoundingClientRect();

    // Vertical side. Measured from the control, whatever side it has now.
    var height = menu.offsetHeight;
    var below = area.bottom - c.bottom - MARGIN;
    var above = c.top - area.top - MARGIN;
    var up = height > below && above > below;
    select.classList.toggle("odx-menu-up", up);

    // Width: widen to the longest label among the options drawn.
    var needed = 0;
    var options = menu.querySelectorAll(".Select-option, .VirtualizedSelectOption");
    for (var i = 0; i < options.length && i < 60; i++) {
      var o = options[i];
      if (o.scrollWidth > o.clientWidth + 1) {
        needed = Math.max(needed, o.scrollWidth + (o.offsetWidth - o.clientWidth) + 4);
      }
    }
    var current = menu.getBoundingClientRect();
    if (needed > current.width) {
      var room = (area.right - area.left) - 2 * MARGIN;
      var width = Math.min(needed, MAX_MENU_WIDTH, room);
      if (width > current.width) {
        menu.style.minWidth = Math.round(width) + "px";
      }
    }
    // Keep it inside horizontally: anchor it to the control's right edge
    // when it would overflow on the right.
    current = menu.getBoundingClientRect();
    if (current.right > area.right - MARGIN && !select.classList.contains("odx-menu-right")) {
      select.classList.add("odx-menu-right");
    }
  }

  function fitOpenMenus() {
    var open = document.querySelectorAll(".Select.is-open");
    for (var i = 0; i < open.length; i++) {
      fitMenu(open[i]);
    }
    // Forget the adjustments of the menus that closed.
    var stale = document.querySelectorAll(".Select.odx-menu-up:not(.is-open), .Select.odx-menu-right:not(.is-open)");
    for (var j = 0; j < stale.length; j++) {
      stale[j].classList.remove("odx-menu-up", "odx-menu-right");
    }
  }

  var pending = false;
  function soon() {
    if (pending) {
      return;
    }
    pending = true;
    // After React has drawn the menu (or filtered it).
    setTimeout(function () {
      window.requestAnimationFrame(function () {
        pending = false;
        fitOpenMenus();
      });
    }, 0);
  }

  document.addEventListener("mousedown", soon, true);
  document.addEventListener("touchend", soon, true);
  document.addEventListener("keydown", soon, true);
  document.addEventListener("focusin", soon, true);

  // ---- step pickers of the tool cards
  function fitPopover(block) {
    var pop = block.querySelector(".odx-steps-pop");
    if (!pop) {
      return;
    }
    block.classList.remove("odx-pop-left");
    var r = pop.getBoundingClientRect();
    if (!r.width) {
      return;
    }
    var area = viewport();
    var b = block.getBoundingClientRect();
    // Flip only when the left side has more room than the right one.
    if (r.right > area.right - MARGIN && b.left - area.left > area.right - b.right) {
      block.classList.add("odx-pop-left");
    }
  }

  function onCard(event) {
    var t = event.target;
    var block = t && t.closest ? t.closest(".odx-flow-block") : null;
    // Synchronous: the popover is measured in the same frame it appears in.
    if (block) {
      fitPopover(block);
    }
  }
  document.addEventListener("mouseover", onCard, true);
  document.addEventListener("focusin", onCard, true);
})();
