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
 * Back arrows go back to where the user came from, not to a fixed page.
 *
 * Every back arrow of the GUI and of Odatix Explorer is a link wearing the
 * "back-button" icon. Its href stays the fallback: the page to go to when this
 * tab has no in-app page to go back to (URL opened directly, new tab, reload
 * of the first page).
 *
 * Each in-app navigation (dcc.Link / dcc.Location both go through
 * history.pushState) is tagged in history.state with "odxBack": how many
 * entries back the previous *page* is. A query names a page of its own (the DSE
 * campaign list and a campaign editor share their path), but a move within the
 * same page -- a hash change, or the URL a save rewrites when it renames the
 * edited item -- adds to the count of the entry it comes from, so the arrow
 * skips those and leaves the page.
 * A count of 0 means no page to go back to: the link is followed.
 *
 * The unsaved-changes guard (unsaved_changes_guard.js) has the first say: while
 * the page is dirty this script lets the click through to it, and acts on the
 * click the guard replays once the user confirmed.
 */

(function () {
  "use strict";

  var KEY = "odxBack";

  function backCount(state) {
    return state && typeof state[KEY] === "number" ? state[KEY] : 0;
  }

  function tag(state, count) {
    var tagged = {};
    if (state && typeof state === "object") {
      for (var k in state) {
        if (Object.prototype.hasOwnProperty.call(state, k)) tagged[k] = state[k];
      }
    }
    tagged[KEY] = count;
    return tagged;
  }

  function samePage(url) {
    if (url == null) return true;
    var target;
    try {
      target = new URL(url, window.location.href);
    } catch (e) {
      return true;
    }
    if (target.pathname !== window.location.pathname) return false;
    if (target.search === window.location.search) return true; // hash only
    var guard = window.__odatixUnsavedGuard;
    return !!(guard && guard.inSaveGrace()); // a save renaming the item
  }

  var pushState = window.history.pushState;
  var replaceState = window.history.replaceState;

  window.history.pushState = function (state, title, url) {
    var current = backCount(window.history.state);
    var count = samePage(url) ? (current > 0 ? current + 1 : 0) : 1;
    return pushState.call(window.history, tag(state, count), title, url);
  };

  // Replacing an entry keeps where it goes back to.
  window.history.replaceState = function (state, title, url) {
    var count = backCount(window.history.state);
    return replaceState.call(window.history, tag(state, count), title, url);
  };

  function isBackLink(anchor) {
    return !!(anchor && anchor.querySelector(".back-button"));
  }

  function onClickCapture(e) {
    if (e.defaultPrevented) return;
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
      return; // open in a new tab etc.: follow the link
    }
    var anchor = e.target.closest ? e.target.closest("a") : null;
    if (!isBackLink(anchor)) return;
    var guard = window.__odatixUnsavedGuard;
    if (guard && !guard.bypassing() && guard.isDirty()) return; // the guard asks first
    var count = backCount(window.history.state);
    if (count <= 0) return; // nothing to go back to: follow the link
    e.preventDefault();
    e.stopPropagation();
    window.history.go(-count);
  }

  document.addEventListener("click", onClickCapture, true);
})();
