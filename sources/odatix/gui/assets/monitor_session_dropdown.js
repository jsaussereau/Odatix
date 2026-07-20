// ********************************************************************** //
//                                Odatix                                  //
// ********************************************************************** //
//
// Track the open/closed state of the monitor session dropdown.
//
// Rescanning running daemons is expensive (it scans /proc and pings every
// candidate daemon over HTTP). Doing it on every polling tick freezes the UI,
// so instead we only refresh the dropdown while the user actually has it open.
// This script mirrors the react-select focus state into a dcc.Store the
// server-side callback can gate on.

(function () {
  var DROPDOWN_ID = "session-dropdown";
  var STORE_ID = "session-dropdown-open";

  function setOpen(open) {
    var ds = window.dash_clientside;
    if (ds && typeof ds.set_props === "function") {
      ds.set_props(STORE_ID, { data: !!open });
    }
  }

  function inDropdown(target) {
    var el = document.getElementById(DROPDOWN_ID);
    return !!(el && target && el.contains(target));
  }

  // Delegated listeners so we do not depend on the element existing yet.
  document.addEventListener("focusin", function (e) {
    if (inDropdown(e.target)) {
      setOpen(true);
    }
  });

  document.addEventListener("focusout", function (e) {
    // Ignore focus moving within the dropdown (e.g. into its menu/input).
    if (inDropdown(e.target) && !inDropdown(e.relatedTarget)) {
      setOpen(false);
    }
  });
})();
