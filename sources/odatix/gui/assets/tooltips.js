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
 * Tooltips of the GUI and of Odatix Explorer (both serve this assets folder).
 *
 * Any element with the `tooltip` class and a non-empty `data-tooltip`
 * attribute shows that text on hover, and on keyboard focus. One bubble
 * (`.odx-tooltip`, styled in style.css) serves the whole page: it lives at the
 * end of the theme wrapper, in fixed position, so no scrolling or rounded
 * container can clip it, it passes over the top bar and the dialogs, and it is
 * placed against the window:
 *   - above the element, or below it with the `bottom` class, flipping to the
 *     other side when there is no room;
 *   - centered on the element, shifted to stay 6px inside the window.
 * Hidden, it is `display: none`: it never widens the page.
 *
 * The same bubble also shows the full text of an element cut by an ellipsis
 * (`text-overflow: ellipsis`) that has no tooltip or title of its own.
 *
 * Pressing on the element hides the bubble until the pointer leaves it, so a
 * tooltip never covers the menu its dropdown just opened.
 */
(function () {
  "use strict";

  var MARGIN = 6;      // minimum distance to the window edges (px)
  var GAP = 8;         // distance between the element and the bubble (px)
  var SHOW_DELAY = 120;
  var LONG_DELAY = 500; // hosts with the `delay` class
  var PASS_CLASSES = ["small", "large", "auto", "primary", "secondary", "warning", "caution", "error-status"];

  var bubble = null;
  var host = null;       // element the bubble describes (shown or pending)
  var muted = null;      // element pressed: no bubble until the pointer leaves it
  var showTimer = null;
  var watchTimer = null;

  function themeRoot() {
    return document.getElementById("theme") || document.querySelector(".theme") || document.body;
  }

  function getBubble() {
    if (!bubble) {
      bubble = document.createElement("div");
      bubble.id = "odx-tooltip";
      bubble.className = "odx-tooltip";
      bubble.setAttribute("role", "tooltip");
    }
    // Inside the theme wrapper, to inherit its tokens. Dash may rebuild the
    // wrapper: re-attach when needed.
    var root = themeRoot();
    if (bubble.parentNode !== root) {
      root.appendChild(bubble);
    }
    return bubble;
  }

  function isTruncated(el) {
    if (!el || el.nodeType !== 1 || el.clientWidth <= 0) {
      return false;
    }
    if (el.scrollWidth <= el.clientWidth + 1) {
      return false;
    }
    return window.getComputedStyle(el).textOverflow === "ellipsis";
  }

  // The element whose tooltip applies at `el`: the closest tooltip host, or an
  // element cut by an ellipsis (itself or one of its two parents).
  function findHost(el) {
    for (var e = el; e && e.nodeType === 1; e = e.parentElement) {
      if (e.classList.contains("tooltip") && e.getAttribute("data-tooltip")) {
        return e;
      }
      if (e === bubble || e.classList.contains("js-plotly-plot")) {
        return null;
      }
    }
    for (var d = 0, t = el; d < 3 && t && t.nodeType === 1; d++, t = t.parentElement) {
      if (t.hasAttribute("title")) {
        return null;
      }
      if (isTruncated(t)) {
        return t;
      }
    }
    return null;
  }

  function hostText(el) {
    var text = el.getAttribute("data-tooltip");
    if (text) {
      return text;
    }
    // A truncated element: its own full text.
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
      return el.value || "";
    }
    return (el.innerText || el.textContent || "").trim();
  }

  function place(tip, el) {
    var r = el.getBoundingClientRect();
    var vw = document.documentElement.clientWidth || window.innerWidth;
    var vh = window.innerHeight;
    tip.style.left = "0px";
    tip.style.top = "0px";
    var w = tip.offsetWidth;
    var h = tip.offsetHeight;

    var above = r.top - GAP - h;
    var below = r.bottom + GAP;
    var fitsAbove = above >= MARGIN;
    var fitsBelow = below + h <= vh - MARGIN;
    var preferBelow = el.classList.contains("bottom") || !el.classList.contains("tooltip");
    var top;
    if (preferBelow) {
      top = (fitsBelow || !fitsAbove) ? below : above;
    } else {
      top = (fitsAbove || !fitsBelow) ? above : below;
    }
    if (!fitsAbove && !fitsBelow) {
      // Taller than the room on either side: keep it on screen.
      top = Math.max(MARGIN, Math.min(top, vh - h - MARGIN));
    }
    var left = r.left + r.width / 2 - w / 2;
    left = Math.max(MARGIN, Math.min(left, vw - w - MARGIN));

    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
    tip.setAttribute("data-side", top >= r.bottom ? "bottom" : "top");
  }

  function clearTimers() {
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }
    if (watchTimer) {
      clearInterval(watchTimer);
      watchTimer = null;
    }
  }

  function hide() {
    clearTimers();
    if (host && host.getAttribute("aria-describedby") === "odx-tooltip") {
      host.removeAttribute("aria-describedby");
    }
    host = null;
    if (bubble) {
      bubble.classList.remove("visible", "shown");
    }
  }

  function show(el) {
    if (host !== el || !document.contains(el)) {
      return;
    }
    var text = hostText(el);
    if (!text) {
      hide();
      return;
    }
    var tip = getBubble();
    tip.textContent = text;
    tip.className = "odx-tooltip shown";
    if (el.classList.contains("tooltip")) {
      PASS_CLASSES.forEach(function (cls) {
        if (el.classList.contains(cls)) {
          tip.classList.add(cls);
        }
      });
    } else {
      tip.classList.add("auto");
    }
    place(tip, el);
    tip.classList.add("visible");
    if (!el.hasAttribute("aria-describedby")) {
      el.setAttribute("aria-describedby", "odx-tooltip");
    }
    // The element can vanish or move without any event reaching us (page
    // change, re-render): drop the bubble then.
    watchTimer = setInterval(function () {
      if (!host || !document.contains(host) || !host.getClientRects().length) {
        hide();
      }
    }, 400);
  }

  function schedule(el, immediate) {
    if (el === host) {
      return;
    }
    hide();
    if (!el || el === muted) {
      return;
    }
    host = el;
    var delay = immediate ? 0 : (el.classList.contains("delay") ? LONG_DELAY : SHOW_DELAY);
    showTimer = setTimeout(function () {
      showTimer = null;
      show(el);
    }, delay);
  }

  document.addEventListener("mouseover", function (event) {
    var el = findHost(event.target);
    if (muted && !(el === muted || (muted.contains && muted.contains(event.target)))) {
      muted = null;
    }
    if (el) {
      schedule(el, false);
    } else if (host) {
      hide();
    }
  }, true);

  document.addEventListener("mouseout", function (event) {
    if (!host) {
      return;
    }
    var to = event.relatedTarget;
    if (!to || !(host === to || host.contains(to))) {
      if (event.target === host || host.contains(event.target)) {
        hide();
      }
    }
  }, true);

  document.addEventListener("focusin", function (event) {
    var target = event.target;
    var keyboard = true;
    try {
      keyboard = target.matches(":focus-visible");
    } catch (e) {
      keyboard = true;
    }
    if (!keyboard) {
      return;
    }
    var el = findHost(target);
    if (el && el.classList.contains("tooltip")) {
      schedule(el, true);
    }
  }, true);

  document.addEventListener("focusout", function (event) {
    if (host && (event.target === host || host.contains(event.target))) {
      hide();
    }
  }, true);

  document.addEventListener("pointerdown", function (event) {
    var el = findHost(event.target);
    if (el) {
      muted = el;
    }
    hide();
  }, true);

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && host) {
      muted = host;
      hide();
    }
  }, true);

  // Follow the element when something scrolls (the page, a panel, a log that
  // scrolls itself): cheaper and calmer than hiding at each tick.
  var placing = false;
  function follow() {
    if (placing || !host || !bubble || !bubble.classList.contains("shown")) {
      return;
    }
    placing = true;
    window.requestAnimationFrame(function () {
      placing = false;
      if (host && bubble.classList.contains("shown")) {
        place(bubble, host);
      }
    });
  }
  window.addEventListener("scroll", follow, true);
  window.addEventListener("resize", follow);
  window.addEventListener("blur", hide);
})();
