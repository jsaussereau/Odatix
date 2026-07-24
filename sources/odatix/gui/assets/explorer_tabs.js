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
