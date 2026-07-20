// ********************************************************************** //
//                                Odatix                                  //
// ********************************************************************** //
//
// Draggable divider for the monitor dashboard split view.
//
// - In "split" mode the divider is vertical: dragging left/right updates the
//   `--monitor-cols` custom property (grid-template-columns) on #monitor-split.
// - In "stacked" mode the divider is horizontal: dragging up/down updates the
//   `--monitor-rows` custom property (grid-template-rows).
// Both ratios are persisted separately in localStorage. The divider is a no-op
// (and hidden by CSS) when a single panel is shown or on small screens.

(function () {
  var SPLIT_ID = "monitor-split";
  var DIVIDER_ID = "monitor-divider";
  var COLS_KEY = "odatixMonitorColsRatio";
  var ROWS_KEY = "odatixMonitorRowsRatio";
  var MIN_RATIO = 0.15;
  var MAX_RATIO = 0.85;

  var dragging = false;

  function splitEl() {
    return document.getElementById(SPLIT_ID);
  }

  function isVertical(split) {
    return !!split && split.classList.contains("stacked");
  }

  function isResizable(split) {
    if (!split) return false;
    var c = split.classList;
    if (c.contains("list-collapsed") || c.contains("log-collapsed")) return false;
    return c.contains("split") || c.contains("stacked");
  }

  function clamp(r) {
    return Math.max(MIN_RATIO, Math.min(MAX_RATIO, r));
  }

  function applyCols(ratio) {
    var split = splitEl();
    if (!split) return;
    var left = clamp(ratio);
    split.style.setProperty(
      "--monitor-cols",
      "minmax(0, " + left + "fr) 12px minmax(0, " + (1 - left) + "fr)"
    );
  }

  function applyRows(ratio) {
    var split = splitEl();
    if (!split) return;
    var top = clamp(ratio);
    split.style.setProperty(
      "--monitor-rows",
      "minmax(0, " + top + "fr) 14px minmax(0, " + (1 - top) + "fr)"
    );
  }

  function restoreRatios() {
    var cols = parseFloat(window.localStorage.getItem(COLS_KEY));
    if (!isNaN(cols)) applyCols(cols);
    var rows = parseFloat(window.localStorage.getItem(ROWS_KEY));
    if (!isNaN(rows)) applyRows(rows);
  }

  function onMouseMove(e) {
    if (!dragging) return;
    var split = splitEl();
    if (!split) return;
    var rect = split.getBoundingClientRect();

    if (isVertical(split)) {
      if (rect.height <= 0) return;
      var ry = clamp((e.clientY - rect.top) / rect.height);
      applyRows(ry);
      window.localStorage.setItem(ROWS_KEY, String(ry));
    } else {
      if (rect.width <= 0) return;
      var rx = clamp((e.clientX - rect.left) / rect.width);
      applyCols(rx);
      window.localStorage.setItem(COLS_KEY, String(rx));
    }
    e.preventDefault();
  }

  function endDrag() {
    if (!dragging) return;
    dragging = false;
    var divider = document.getElementById(DIVIDER_ID);
    if (divider) divider.classList.remove("dragging");
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
  }

  // Delegated mousedown so we do not depend on the divider existing at load.
  document.addEventListener("mousedown", function (e) {
    var divider = e.target.closest ? e.target.closest("#" + DIVIDER_ID) : null;
    if (!divider) return;
    var split = splitEl();
    if (!isResizable(split)) return;
    dragging = true;
    divider.classList.add("dragging");
    document.body.style.userSelect = "none";
    document.body.style.cursor = isVertical(split) ? "row-resize" : "col-resize";
    e.preventDefault();
  });

  document.addEventListener("mousemove", onMouseMove, { passive: false });
  document.addEventListener("mouseup", endDrag);

  // Pages are client-side routed; restore the saved ratios once the split mounts.
  var restored = false;
  setInterval(function () {
    var split = splitEl();
    if (split && !restored) {
      restored = true;
      restoreRatios();
    } else if (!split) {
      restored = false;
    }
  }, 500);
})();
