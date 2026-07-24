// ********************************************************************** //
//                                Odatix                                  //
// ********************************************************************** //
//
// Warn the user before leaving a page that has unsaved changes. Pure vanilla
// JS, self-contained, loaded on every Odatix GUI page (the assets folder is
// shared, but this guard is GUI-only: the explorer has no save buttons, so it
// is simply inert there).
//
// The GUI is a Dash single-page app: navigation happens through dcc.Link
// anchors that swap the page without a full reload, so window.beforeunload is
// not enough. We intercept in-app link clicks in the capture phase (before
// Dash/React handles them) and, if the current page is dirty, hold navigation
// behind a confirmation popup. beforeunload still covers tab close / refresh.
//
// Dirty state is read straight from the DOM: every savable page renders a
// "save-all" button whose class becomes "warning" exactly while there are
// unsaved changes (and "disabled" when clean). No per-page wiring needed.

(function () {
  "use strict";

  var overlay = null;
  var bypass = false; // set while we replay a click the user confirmed

  // ------------------------------------------------------------------ dirty
  function isDirty() {
    var els = document.querySelectorAll('[id*="save-all"]');
    for (var i = 0; i < els.length; i++) {
      var cls = els[i].className;
      if (typeof cls !== "string") cls = (cls && cls.baseVal) || ""; // SVG nodes
      // The save-all <button> carries "color-button ... warning" while dirty;
      // its inner icon shares the id fragment but never the "warning" class.
      if (cls.indexOf("color-button") !== -1 && cls.indexOf("warning") !== -1) {
        return true;
      }
    }
    return false;
  }

  // ------------------------------------------------------------------ popup
  function buildOverlay() {
    overlay = document.createElement("div");
    overlay.className = "overlay-odatix";
    overlay.id = "unsaved-changes-overlay";

    var popup = document.createElement("div");
    popup.className = "popup-odatix";

    var title = document.createElement("h3");
    title.textContent = "Unsaved changes";

    var message = document.createElement("p");
    message.style.color = "var(--theme-text-color)";
    message.style.margin = "12px 0 24px";
    message.textContent =
      "You have unsaved changes on this page. Leave without saving?";

    var buttons = document.createElement("div");
    buttons.style.display = "flex";
    buttons.style.justifyContent = "center";
    buttons.style.gap = "10px";

    var stayBtn = document.createElement("button");
    stayBtn.className = "color-button secondary";
    stayBtn.textContent = "Stay on page";

    var leaveBtn = document.createElement("button");
    leaveBtn.className = "color-button caution";
    leaveBtn.textContent = "Leave without saving";

    buttons.appendChild(stayBtn);
    buttons.appendChild(leaveBtn);
    popup.appendChild(title);
    popup.appendChild(message);
    popup.appendChild(buttons);
    overlay.appendChild(popup);
    // Mount inside the #theme container so the theme CSS variables (defined on
    // .theme / .theme.<name>) cascade into the popup; fall back to <body>.
    (document.getElementById("theme") || document.body).appendChild(overlay);

    overlay._stayBtn = stayBtn;
    overlay._leaveBtn = leaveBtn;
    return overlay;
  }

  function hideOverlay() {
    if (overlay) overlay.classList.remove("visible");
  }

  function confirmLeave(anchor) {
    if (!overlay) buildOverlay();

    overlay._stayBtn.onclick = function () {
      hideOverlay();
    };
    overlay._leaveBtn.onclick = function () {
      hideOverlay();
      // Replay the original click so Dash performs its normal navigation
      // (SPA route swap for dcc.Link, plain load otherwise). The guard lets it
      // through because `bypass` is set.
      bypass = true;
      try {
        anchor.click();
      } finally {
        bypass = false;
      }
    };
    overlay.classList.add("visible");
  }

  // -------------------------------------------------------------- intercept
  function currentPath() {
    return window.location.pathname;
  }

  function isInternalNav(anchor) {
    if (!anchor) return false;
    if (anchor.target && anchor.target !== "_self") return false; // new tab
    if (anchor.hasAttribute("download")) return false;
    var href = anchor.getAttribute("href");
    if (!href) return false;
    if (href.charAt(0) === "#") return false; // in-page anchor
    // Only guard same-origin, in-app navigation.
    var url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (e) {
      return false;
    }
    if (url.origin !== window.location.origin) return false;
    if (url.pathname === currentPath()) return false; // staying on this page
    return true;
  }

  function onClickCapture(e) {
    if (bypass) return;
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
      return; // let modified clicks (open in new tab, ...) through
    }
    var anchor = e.target.closest ? e.target.closest("a") : null;
    if (!isInternalNav(anchor)) return;
    if (!isDirty()) return;

    e.preventDefault();
    e.stopPropagation();
    confirmLeave(anchor);
  }

  function onBeforeUnload(e) {
    if (bypass) return; // confirmed leave via popup should not double-prompt
    if (isDirty()) {
      e.preventDefault();
      e.returnValue = ""; // triggers the browser's native confirm dialog
    }
  }

  function start() {
    // Capture phase: run before Dash/React's own click handling so we can
    // cancel the navigation entirely when the page is dirty.
    document.addEventListener("click", onClickCapture, true);
    window.addEventListener("beforeunload", onBeforeUnload);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
