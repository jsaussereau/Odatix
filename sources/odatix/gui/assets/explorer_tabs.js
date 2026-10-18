// Sidebar tab switching for Odatix Explorer, done client-side so every control
// stays mounted (the figure callbacks need a stable set of inputs). See
// explorer/callbacks/controls.py and explorer/ui/sidebar.py.
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.xp_tabs = {
  // Map a tab-button click to the active tab key (the clicked button's id).
  select: function () {
    const keys = ["data", "filters", "export"];
    const ctx = window.dash_clientside.callback_context;
    if (!ctx || !ctx.triggered || !ctx.triggered.length) {
      return window.dash_clientside.no_update;
    }
    const id = ctx.triggered[0].prop_id.split(".")[0];
    const key = id.replace("xp-tab-btn-", "");
    return keys.indexOf(key) >= 0 ? key : window.dash_clientside.no_update;
  },

  // Reflect the active tab into the sidebar content class and button classes.
  apply: function (active) {
    const keys = ["data", "filters", "export"];
    active = keys.indexOf(active) >= 0 ? active : "data";
    const content = "xp-sidebar-content xp-tab-active-" + active;
    const buttons = keys.map(function (k) {
      return "xp-tab-label" + (k === active ? " xp-tab-active" : "");
    });
    return [content].concat(buttons);
  },
};

// "Download image" button of the Save tab: the same export as the camera button
// of the chart toolbar (format, file name and scale come from the graph config
// written by explorer/callbacks/figure.py), without having to find that button,
// which only shows on hover.
window.dash_clientside.xp_export = {
  download_image: function (clicks) {
    const no_update = window.dash_clientside.no_update;
    if (!clicks || !window.Plotly) return no_update;
    const gd = document.querySelector("#xp-graph .js-plotly-plot");
    if (!gd) return no_update;
    const options = Object.assign(
      { format: "svg", filename: "Odatix", scale: 3 },
      (gd._context && gd._context.toImageButtonOptions) || {}
    );
    window.Plotly.downloadImage(gd, options);
    return clicks;
  },
};

// Explorer page guards, outside of Dash: they act on what the page shows.
(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Escape must not empty a multi dropdown of the sidebar. The dropdown
  // component clears its whole value on Escape when its menu is closed, which
  // is exactly what a second Escape press (meant to close the menu) does: the
  // chart silently lost its "Color by". Intercepted before React sees it,
  // only when the menu is already closed (the first press still closes it).
  // ---------------------------------------------------------------------------
  window.addEventListener(
    "keydown",
    function (event) {
      if (event.key !== "Escape" && event.key !== "Esc") return;
      const target = event.target;
      if (!target || !target.closest || !target.closest("#xp-sidebar")) return;
      const select = target.closest(".Select, .dash-dropdown");
      if (!select) return;
      const open =
        select.classList.contains("is-open") ||
        select.querySelector(".Select-menu-outer, [role='listbox']") !== null ||
        target.getAttribute("aria-expanded") === "true";
      if (!open) event.stopPropagation();
    },
    true
  );

  // ---------------------------------------------------------------------------
  // Chart guard. A chart request lost on its way (a busy server, a request
  // cancelled while the page was being built) left the page on its placeholder
  // for good: nothing asks for the figure again until a control changes. When a
  // chart page stays undrawn while no callback is running, ask for it again
  // (the hidden "xp-redraw" button is an input of the chart callbacks), a few
  // times, then show the Retry bar.
  // ---------------------------------------------------------------------------
  const CHECK_MS = 1000;
  const IDLE_MS = 2500; // undrawn and idle this long: the answer is not coming
  const MAX_RETRIES = 3;
  let state = { path: null, retries: 0, idleSince: null };

  function drawn() {
    if (!document.getElementById("xp-graph-area")) return null; // not a chart page
    const error = document.getElementById("xp-error");
    if (error && error.children.length) return true; // an error says it all
    const overview = document.getElementById("xp-overview-area");
    if (overview) return overview.children.length > 0;
    const table = document.getElementById("xp-table-area");
    if (table) return table.children.length > 0;
    const gd = document.querySelector("#xp-graph .js-plotly-plot");
    // Figures of the chart engine carry layout.meta.odatix, the placeholder does not
    return !!(gd && gd.layout && gd.layout.meta && gd.layout.meta.odatix);
  }

  function busy() {
    return document.hidden || document.querySelector("[data-dash-is-loading='true']") !== null;
  }

  function showBar(visible) {
    const bar = document.getElementById("xp-redraw-bar");
    if (bar) bar.classList.toggle("xp-redraw-visible", visible);
  }

  setInterval(function () {
    if (window.location.pathname !== state.path) {
      state = { path: window.location.pathname, retries: 0, idleSince: null };
      showBar(false);
    }
    const done = drawn();
    if (done !== false) {
      state.idleSince = null;
      if (done) showBar(false);
      return;
    }
    if (busy()) {
      state.idleSince = null;
      return;
    }
    if (state.idleSince === null) {
      state.idleSince = Date.now();
      return;
    }
    if (Date.now() - state.idleSince < IDLE_MS) return;
    state.idleSince = null;
    if (state.retries < MAX_RETRIES) {
      state.retries += 1;
      const button = document.getElementById("xp-redraw");
      if (button) button.click();
    } else {
      showBar(true);
    }
  }, CHECK_MS);
})();
